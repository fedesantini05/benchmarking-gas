"""Run PDF extraction and compare with frozen, independently approved reference."""
import argparse
import csv
import json
import html
import sys
from pathlib import Path
from extractor import BASE, extract, digest
from control_planilla import Book, compare

def source_checks(record):
    facts=record['facts']
    def v(key):
        if facts[key]['value'] is None: raise ValueError(f'Falta control requerido: {key}')
        return facts[key]['value']
    op=v('gas_operating_revenue')-v('gas_cost')-v('operations_maintenance')-v('da')-v('taxes_other_income')
    checks={'operating_income':op-v('operating_income'),
            'pretax':op-v('interest_deductions')+v('other_income_deductions')-v('pretax'),
            'net_income':v('pretax')-v('income_tax')-v('net_income'),
            'plant':v('gas_plant_gross')-v('accumulated_depreciation')+v('construction_work_progress')-v('net_utility_plant'),
            'assets':v('current_assets')+v('net_utility_plant')+v('other_property_investments')+v('goodwill')+v('deferred_other_assets')-v('assets'),
            'balance':v('current_liabilities')+v('long_debt')+v('deferred_tax_credits')+v('removal_costs')+v('other_long_liabilities')+v('equity')-v('assets')}
    categories=sum(v(k) for k in ('residential','small_commercial','large_commercial','industrial_other','transportation','alternative_revenue','other_revenue'))
    return {'year':record['year'],'checks':checks,'revenue_note_difference':categories-v('gas_operating_revenue'),
            'status':'PASS' if all(x==0 for x in checks.values()) else 'FAIL'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--years', nargs='+', type=int, default=list(range(2020,2026)))
    args = parser.parse_args()
    folder = BASE.parent / 'Southwest Gas Corporation' / 'Estados contables'
    output = BASE / 'resultados'
    output.mkdir(exist_ok=True)
    records = []
    for year in args.years:
        print(f'Extrayendo {year}...', flush=True)
        records.append(extract(folder / f'Southwest Gas Corporation - informe contable - {year}.pdf', year, BASE / 'cache'))
        (output / f'extraccion_{year}.json').write_text(json.dumps(records[-1], ensure_ascii=False, indent=2), encoding='utf-8')
    reference = json.loads((BASE / 'referencia' / 'datos_aprobados.json').read_text(encoding='utf-8'))
    approved_path=BASE / 'referencia' / 'SGC_aprobada_2020_2025.xlsx'
    book=Book(approved_path)
    expected = {r['year']:r['facts'] for r in reference}
    comparisons = []
    for record in records:
        for key, old in expected[record['year']].items():
            actual = record['facts'][key]
            status = actual['status'] if actual['value'] is None else ('PASS' if actual['value'] == old['value'] else 'DIFFERENCE')
            comparisons.append({'year':record['year'], 'concept':key, 'expected':old['value'], 'extracted':actual['value'], 'status':status, 'page':actual.get('page')})
    with (output / 'comparacion.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader(); writer.writerows(comparisons)
    counts = {status:sum(r['status']==status for r in comparisons) for status in sorted({r['status'] for r in comparisons})}
    cells=[row for r in records for row in compare(r,book)]
    controls=[source_checks(r) for r in records]
    # Baseline zeros do not authorize filling absent concepts with zero.
    absent=[r for r in comparisons if r['status']=='MISSING']
    failures=[r for r in comparisons if r['status'] in ('DIFFERENCE','REVIEW') or (r['status']=='MISSING' and r['expected']!=0)]
    failed=bool(failures or any(c['status']!='PASS' for c in cells) or any(c['status']!='PASS' for c in controls))
    result={'status':'FAIL' if failed else 'PASS_WITH_DISCLOSURES','counts':counts,
            'approved_workbook_sha256':digest(approved_path),'cell_checks':cells,'source_controls':controls,
            'missing':absent,'failures':failures,'note':'Partidas ausentes permanecen null. Diferencias entre nota y estado se reportan sin asignarlas automaticamente.'}
    (output/'validacion.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    def table(data,columns):
        return '<table><tr>'+''.join('<th>'+html.escape(c)+'</th>' for c in columns)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(row.get(c,'')))+'</td>' for c in columns)+'</tr>' for row in data)+'</table>'
    report='''<!doctype html><html lang="es"><meta charset="utf-8"><title>SGC: prueba de extracción automática</title>
<style>body{font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 20px;color:#17324d}table{border-collapse:collapse;width:100%;margin:20px 0;font-size:14px}td,th{border:1px solid #ccd4dd;text-align:left;padding:7px}th{background:#eaf0f6}h1{font-size:28px}</style>
<h1>SGC · Extracción automática 2020–2025</h1><p>Lectura local de PDF con Python, sin IA ni servicios externos. La referencia aprobada se utiliza exclusivamente para comparar.</p>'''
    report+=f'<p>Resultado: <strong>{result["status"]}</strong>. {counts.get("PASS",0)} importes coinciden. {len(cells)} controles de celdas. {len(absent)} conceptos sin renglón publicado, conservados como ausentes.</p>'
    report+='<h2>Conciliaciones con los estados originales</h2>'+table([{'año':c['year'],'estado':c['status'],'nota menos estado (miles USD)':c['revenue_note_difference']} for c in controls],['año','estado','nota menos estado (miles USD)'])
    report+='<p>La diferencia de ingresos de 2025 ya existía en la referencia aprobada. El lector la detecta y la informa; no genera un ajuste automático para futuros documentos. Los pilares PMSO siguen sin apertura por naturaleza en este piloto.</p>'
    report+='<h2>Datos no publicados por separado</h2>'+table(absent,['year','concept','expected','extracted','status'])
    report+='<details><summary>Ver los controles de la planilla aprobada</summary>'+table(cells,['year','sheet','cell','extracted','approved','status'])+'</details>'
    report+='<h2>Alcance</h2><p>Adaptador probado con los seis informes anuales de SGC. Un nuevo formato, entidad, moneda o concepto requiere validación. No modifica la planilla aprobada ni rellena información faltante. Los diccionarios se amplían mediante reglas revisadas.</p></html>'
    (output/'revision_sgc.html').write_text(report,encoding='utf-8')
    print(json.dumps(counts))
    print(f'{len(cells)} controles de celdas; resultado: {result["status"]}')
    print('Informe: '+str(output/'revision_sgc.html'))
    if failed: sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        output=BASE/'resultados'; output.mkdir(exist_ok=True)
        (output/'validacion.json').write_text(json.dumps({'status':'FAIL','error':str(error)},ensure_ascii=False,indent=2),encoding='utf-8')
        (output/'revision_sgc.html').write_text('<!doctype html><meta charset="utf-8"><h1>La extracción requiere revisión</h1><p>'+html.escape(str(error))+'</p><p>Los resultados anteriores no acreditan esta ejecución.</p>',encoding='utf-8')
        print(str(error),file=sys.stderr)
        sys.exit(1)
