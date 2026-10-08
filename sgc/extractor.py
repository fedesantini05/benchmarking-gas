"""Deterministic PDF reader. No model, network, reference amounts or fixed pages."""
import hashlib
import json
import logging
import re
from pathlib import Path
from pypdf import PdfReader

logging.getLogger('pypdf').setLevel(logging.ERROR)
BASE = Path(__file__).resolve().parent
NUM = r'\(?-?\d[\d,]*(?:\.\d+)?\)?|[—–-]'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def pages(path, cache):
    sha = digest(path)
    target = Path(cache) / (sha + '.json')
    if target.exists():
        return json.loads(target.read_text(encoding='utf-8')), sha
    result = [p.extract_text() or '' for p in PdfReader(path).pages]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result, sha

def rows(texts):
    return [(page, ' '.join(line.split())) for page, text in texts for line in text.splitlines() if line.strip()]

def statement(texts, entity, title, year):
    candidates = []
    for index, text in enumerate(texts):
        pattern = re.escape(entity) + r'\s+' + title
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        body = text[match.start():]
        if '(Unaudited)' in body[:350]:
            continue
        if re.search(r'As Reported.*Adjustments.*As Revised', body[:350], re.I):
            continue
        if 'income' in title.lower() and not re.search(r'Year Ended December 31', body[:250], re.I):
            continue
        if not re.search(r'\((?:Thousands of dollars|In thousands)\)', body, re.I):
            continue
        head = body[:body.lower().find('gas plant')] if 'balance' in title.lower() else body[:800]
        if 'equity' in title.lower(): head = body
        yrs = re.findall(r'\b20\d{2}\b', head)
        if not yrs or (str(year) not in yrs if 'equity' in title.lower() else int(yrs[0]) != year):
            continue
        selected = [(index + 1, body)]
        if 'balance' in title.lower() and 'Total capitalization and liabilities' not in body:
            selected.append((index + 2, texts[index + 1]))
        candidates.append(selected)
    if len(candidates) != 1:
        raise ValueError(f'{year}: {title}: {len(candidates)} candidatos; requiere revisión')
    return rows(candidates[0])

def parse_value(token):
    if token in ('—', '–', '-'):
        return 0
    negative = token.startswith('(')
    value = float(token.strip('()').replace(',', ''))
    return -value if negative else value

def extract_one(lines, pattern):
    matches = []
    for i, (page, line) in enumerate(lines):
        found = re.match('^' + pattern + r'(?=\s|$)', line, re.I)
        if not found:
            continue
        tail = line[found.end():].strip()
        # Some footnote markers and values are on the next text line.
        if not tail and i + 1 < len(lines):
            tail = lines[i + 1][1]
        tail = re.sub(r'^(?:\(\d\)\s*)+', '', tail).lstrip('$ ')
        tokens = re.findall(NUM, tail)
        if len(tokens) < 2 or not re.match(r'^[\s$\d(—–-]', tail):
            continue
        matches.append({'value': parse_value(tokens[0]), 'page': page,
                        'label': found.group(), 'source_line': line + (' ' + tail if not line[found.end():].strip() else ''),
                        'status': 'PUBLISHED'})
    if len(matches) != 1:
        return {'value': None, 'status': 'MISSING' if not matches else 'REVIEW', 'candidates': matches}
    return matches[0]

def extract(path, year, cache):
    glossary = json.loads((BASE / 'diccionario_us.json').read_text(encoding='utf-8'))
    texts, sha = pages(path, cache)
    inc = statement(texts, glossary['entity'], 'CONSOLIDATED STATEMENTS OF INCOME', year)
    bal = statement(texts, glossary['entity'], 'CONSOLIDATED BALANCE SHEETS', year)
    split = next(i for i, (_, line) in enumerate(bal) if line == 'CAPITALIZATION AND LIABILITIES')
    rev_pages = [(i+1, t) for i, t in enumerate(texts) if 'disaggregated by customer type' in t and re.search(r'Residential\s+\$', t)]
    if len(rev_pages) != 1:
        raise ValueError(f'{year}: tabla de clientes ambigua o ausente')
    revenue = rows(rev_pages)
    header = rev_pages[0][1].split('Residential')[0]
    years = re.findall(r'\b20\d{2}\b', header[header.rfind('December 31'):])
    if not years or int(years[0]) != year:
        raise ValueError('Año de tabla de clientes incorrecto')
    facts = {}
    for section, source in [('income', inc), ('balance', bal), ('revenue', revenue)]:
        for key, pattern in glossary[section].items():
            selected = source
            if key == 'deferred_gas_cost_asset': selected = bal[:split]
            if key == 'deferred_gas_cost_liability': selected = bal[split:]
            facts[key] = extract_one(selected, pattern)
    # Preserve raw signed values; normalize only the two expense magnitudes used by mapping.
    for key in ('interest_deductions', 'accumulated_depreciation'):
        fact = facts[key]
        if fact['value'] is not None:
            fact['raw_value'] = fact['value']
            fact['value'] = abs(fact['value'])
    eq = statement(texts, glossary['entity'], 'CONSOLIDATED STATEMENTS OF EQUITY', year)
    if any(re.match(r'Beginning and ending balances\s', line) for _, line in eq):
        pos = next(i for i, (_, line) in enumerate(eq) if line == 'Common stock shares')
        facts['shares_thousand'] = extract_one(eq[pos:pos+3], 'Beginning and ending balances')
    else:
        facts['shares_thousand'] = extract_one(eq, f'Balance, December 31, {year}')
    return {'year': year, 'path': str(path), 'sha256': sha, 'unit': 'thousands_USD',
            'facts': facts, 'pages': len(texts), 'engine': 'pypdf_regex_no_ai'}
