"""Inspect source completeness; does not map or write any financial values."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'cache/new_cases'
PATTERN = re.compile(r'estado.{0,35}(situaci[oó]n|resultado)|estados financieros|notas a los estados|ingresos de actividades|fusion|fusi[oó]n|subsidiaria|segmento', re.I)


def main():
    for path in sorted(BASE.glob('*_20*.json')):
        pages = json.loads(path.read_text(encoding='utf-8'))
        print('\nSOURCE', path.stem, 'readable pages', sum(len(p.strip()) > 100 for p in pages), '/', len(pages))
        for number, page in enumerate(pages, 1):
            if PATTERN.search(page):
                lines = [line.strip() for line in page.splitlines() if PATTERN.search(line)]
                meaningful = [line for line in lines if not re.search(r'^NOTAS A LOS ESTADOS|^estados financieros de la Sociedad', line, re.I)]
                if path.stem.startswith('efigas') or (number < 10) or any(re.search(r'fusi[oó]n|[uú]nico segmento|subsidiaria.*(nombre|Gas|100)|absor', line, re.I) for line in meaningful):
                    print('PAGE', number, ' | '.join(meaningful)[:400])
    inventory = json.loads((BASE / 'inventory.json').read_text(encoding='utf-8'))
    for key, item in inventory.items():
        print('\nTARGET', key)
        for part in (item['sheets'][1], item['sheets'][4]):
            targets = [c for c in part['cells'] if re.fullmatch(r'[JKLM](?:[2-9]|[1-4][0-9]|5[0-3])', c['cell'])]
            constants = [c for c in targets if c['value'] is not None and not c['formula']]
            print(part['part'], 'target nonformula cells', json.dumps(constants, ensure_ascii=False)[:850])


if __name__ == '__main__':
    main()
