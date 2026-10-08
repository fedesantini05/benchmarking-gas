"""Read-only compatibility probe; never author a workbook for an unvalidated entity."""
import json
import re
import argparse
from extractor import BASE, pages, rows, extract_one

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--year',type=int,default=2025)
    year=parser.parse_args().year
    path=BASE.parent/'Northwest gas corporation'/'Estados contables'/f'NGC - Informe contable - {year}.pdf'
    texts,sha=pages(path,BASE/'cache')
    dictionary=json.loads((BASE/'diccionario_us.json').read_text(encoding='utf-8'))
    candidates=[]
    for i,t in enumerate(texts):
        if t.startswith('NORTHWEST NATURAL GAS COMPANY\nCONSOLIDATED'):
            candidates.append({'page':i+1,'header':t[:700]})
    income=[(i+1,t) for i,t in enumerate(texts) if t.startswith('NORTHWEST NATURAL GAS COMPANY\nCONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME')]
    if len(income)!=1 or not re.search(r'In thousands '+str(year)+r'\s',income[0][1]):
        raise ValueError('No se pudo identificar la entidad/período de Northwest')
    source=rows(income)
    original={k:extract_one(source,pattern) for k,pattern in dictionary['income'].items()}
    aliases=json.loads((BASE/'diccionario_northwest.json').read_text(encoding='utf-8'))['income_aliases']
    adapted=dict(original)
    for key,pattern in aliases.items(): adapted[key]=extract_one(source,pattern)
    if any(f['value'] is None for f in adapted.values()): raise ValueError('Concepto requerido de Northwest no extraído')
    def v(k): return adapted[k]['value']
    operating=v('gas_operating_revenue')-sum(v(k) for k in ('gas_cost','operations_maintenance','environmental','taxes_other_income','revenue_taxes','da','other_operating_expenses'))
    controls={'operating_income':operating-v('operating_income'),'pretax':operating+v('other_income_deductions')-v('interest_deductions')-v('pretax'),'net_income':v('pretax')-v('income_tax')-v('net_income')}
    result={'source':str(path),'sha256':sha,'pages':len(texts),'candidate_tables':candidates,
            'status':'EXTRACTION_PASS_MAPPING_REVIEW' if all(v==0 for v in controls.values()) else 'FAIL',
            'unchanged_dictionary_matches':sum(f['value'] is not None for f in original.values()),'original_concepts':len(original),
            'adapter_aliases':aliases,'facts':adapted,'checks':controls,
            'reason':'Prueba de resultados de la entidad Northwest Natural Gas Company. La clasificación CIER y el alcance distribución requieren validación; no genera Excel.'}
    (BASE/'resultados'/f'northwest_{year}_compatibilidad.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'year':year,**{k:result[k] for k in ('status','unchanged_dictionary_matches','original_concepts','checks')}},ensure_ascii=False))
    if result['status']=='FAIL': raise ValueError('Conciliación de Northwest fallida')
if __name__=='__main__': main()
