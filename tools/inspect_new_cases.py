"""Read-only source/template inventory for the three newly requested cases."""
import json
import hashlib
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
CASES = {
    'ecogas_cuyo': ('Ecogas Cuyo', 'AR - Ecogas Cuyo - Planilla Info Pública - Datos Financieros.xlsx', [2023, 2024, 2025]),
    'efigas': ('Efigas', 'CO - Efigas - Planilla Info Pública - Datos Financieros.xlsx', [2023, 2024, 2025]),
    'metrogas_chile': ('Metrogas chile', 'CL - Metrogas Chile - Planilla Info Pública - Datos Financieros.xlsx', [2022, 2023, 2024, 2025]),
}
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def main():
    cache = ROOT / 'cache/new_cases'
    cache.mkdir(parents=True, exist_ok=True)
    summary = {}
    for key, (folder, template_name, years) in CASES.items():
        template = Path.home() / 'Downloads' / template_name
        item = {'template': str(template), 'years': years, 'reports': [], 'sheets': []}
        with ZipFile(template) as archive:
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                strings = [''.join(s.itertext()) for s in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
            workbook = ET.fromstring(archive.read('xl/workbook.xml'))
            item['sheet_names'] = [s.get('name') for s in workbook.findall('m:sheets/m:sheet', NS)]
            for name in archive.namelist():
                if not name.startswith('xl/worksheets/sheet') or not name.endswith('.xml'):
                    continue
                cells = []
                for c in ET.fromstring(archive.read(name)).findall('.//m:c', NS):
                    ref = c.get('r'); value = c.findtext('m:v', namespaces=NS)
                    if c.get('t') == 's' and value:
                        value = strings[int(value)]
                    elif c.get('t') == 'inlineStr':
                        value = ''.join(c.find('m:is', NS).itertext())
                    formula = c.findtext('m:f', namespaces=NS)
                    if value is not None or formula:
                        cells.append({'cell': ref, 'value': value, 'formula': formula})
                item['sheets'].append({'part': name, 'cells': cells})
        reports = WORK / folder / 'Estados contables'
        for year in years:
            matches = [p for p in reports.iterdir() if p.suffix.lower() == '.pdf' and str(year) in p.stem]
            if len(matches) != 1:
                raise ValueError(f'{key} {year}: ambiguous/missing annual report')
            pdf = matches[0]
            reader = PdfReader(pdf)
            pages = [p.extract_text() or '' for p in reader.pages]
            target = cache / f'{key}_{year}.json'
            target.write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
            item['reports'].append({'year': year, 'path': str(pdf), 'pages': len(pages),
                                    'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest()})
            print(f'\n{key} {year}: {len(pages)} páginas\n' + '\n'.join(pages[:2])[:2500])
        summary[key] = item
        headers = [[c for c in sheet['cells'] if c['cell'].endswith('1')] for sheet in item['sheets']]
        print('TEMPLATE', key, item['sheet_names'], json.dumps(headers, ensure_ascii=False)[:1700])
    (cache / 'inventory.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
