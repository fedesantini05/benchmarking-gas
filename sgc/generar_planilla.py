"""PDF -> concepts -> formulas -> Excel; approved workbook is validation only."""
import argparse
import json
from pathlib import Path
from extractor import BASE, extract, digest
from control_planilla import Book, compare
from probar_extraccion import source_checks
from escritor_excel import write

ER='Estado de Resultados'; BP='Balance Patrimonial'
GROUP_ASSET=['accrued_utility_revenue','income_tax_receivable','deferred_gas_cost_asset','receivable_parent','inventory','prepaid_other_current','held_for_sale']
GROUP_LIAB=['customer_deposits','accrued_taxes','accrued_interest','deferred_gas_cost_liability','payable_parent','dividends_declared','other_current_liabilities']
REVENUE=['residential','small_commercial','large_commercial','industrial_other','transportation','alternative_revenue','other_revenue']

def make_patches(records):
    patches={ER:{},BP:{}}; observations={ER:{},BP:{}}; sources={ER:{},BP:{}}; evidence=[]
    for rec in records:
        y=rec['year']; c=chr(ord('H')+y-2020); facts=rec['facts']
        controls=source_checks(rec)
        if controls['status']!='PASS': raise ValueError(f'{y}: falla conciliación de fuente')
        def value(key):
            f=facts[key]
            if f['status']!='PUBLISHED' or f['value'] is None: raise ValueError(f'{y}: falta {key}')
            return f['value']
        def disclosed(keys):
            for k in keys:
                if facts[k]['status']=='REVIEW': raise ValueError(f'{y}: ambiguo {k}')
            return [k for k in keys if facts[k]['value'] is not None]
        current=disclosed(GROUP_ASSET)
        liabilities=disclosed(GROUP_LIAB)
        debt=disclosed(['current_debt_maturities','short_debt'])
        if value('cash')+value('receivables')+sum(value(k) for k in current)!=value('current_assets'):
            raise ValueError(f'{y}: activo corriente incompleto')
        if value('suppliers')+sum(value(k) for k in debt+liabilities)!=value('current_liabilities'):
            raise ValueError(f'{y}: pasivo corriente incompleto')
        def put(sheet,row,formula,keys=(),note='Fórmula de la plantilla.'):
            ref=f'{c}{row}'; patches[sheet][ref]=formula
            observations[sheet].setdefault(row,[]).append(f'{y}: {note}')
            pages=sorted({facts[k]['page'] for k in keys if facts[k].get('page')})
            sources[sheet].setdefault(row,[]).append(f'{y}: informe anual original, PDF pp. '+', '.join(map(str,pages)) if pages else f'{y}: referencias internas de la planilla.')
            evidence.append({'year':y,'sheet':sheet,'cell':ref,'formula':formula,'keys':list(keys),'pages':pages})
        def aggregate(sheet,row,keys,expense=False,note=None):
            expression='+'.join(str(int(value(k))) if value(k)>=0 else '('+str(int(value(k)))+')' for k in keys)
            formula=('=-(' if expense else '=(')+(expression or '0')+')/1000'
            put(sheet,row,formula,keys,note or ' + '.join(facts[k]['label'] for k in keys))
        def calc(sheet,row,formula): put(sheet,row,formula)
        for row,formula in {2:f'{c}3+{c}13',3:f'SUM({c}4:{c}12)',15:f'{c}2+{c}14',17:f'{c}15+{c}16',19:f'SUM({c}20:{c}22)',23:f'SUM({c}24:{c}26)',27:f'SUM({c}28:{c}30)',31:f'SUM({c}32:{c}34)',35:f'SUM({c}36:{c}42)',43:f'{c}17+{c}18+{c}35',45:f'{c}43+{c}44',46:f'{c}47+{c}48',49:f'{c}45+{c}46',50:f'{c}51+{c}52',53:f'{c}49+{c}50'}.items(): calc(ER,row,'='+formula)
        aggregate(ER,4,['residential']); aggregate(ER,5,['small_commercial','large_commercial']); aggregate(ER,6,['industrial_other'])
        delta=value('gas_operating_revenue')-sum(value(k) for k in REVENUE)
        if delta:
            # Exact exception already present in the user-approved workbook; never generalized.
            if y!=2025 or rec['sha256']!='d47d4ac35e75f3b61fa3254e36e5fa9a2eb7463db0d58dd358a8477f1fcc607d' or delta!=2100:
                raise ValueError('Diferencia de ingresos nueva: REVIEW; no se crea ajuste')
            expr='+'.join(str(int(value(k))) for k in ['transportation','alternative_revenue','other_revenue'])
            put(ER,12,f'=({expr}+({int(value("gas_operating_revenue"))}-{int(sum(value(k) for k in REVENUE))}))/1000',REVENUE+['gas_operating_revenue'],'Incluye diferencia nota/estado de 2,1 millones ya aprobada en SGC; excepción exclusiva de este PDF.')
        else: aggregate(ER,12,['transportation','alternative_revenue','other_revenue'])
        other=value('other_income_deductions')
        aggregate(ER,13,['other_income_deductions'] if other>0 else [],note='Otros ingresos positivos según criterio aprobado; deducciones negativas en fila 48.')
        for row,key in [(16,'gas_cost'),(18,'operations_maintenance'),(37,'taxes_other_income'),(44,'da'),(52,'income_tax')]:
            aggregate(ER,row,[key],expense=True,note='O&M total publicado, sin apertura PMSO por naturaleza ni base histórica para estimarla.' if row==18 else None)
        aggregate(ER,48,['interest_deductions'],expense=True)
        if other<0: put(ER,48,f'=-({int(value("interest_deductions"))}+{int(-other)})/1000',['interest_deductions','other_income_deductions'],'Interés neto más otras deducciones negativas.')
        for row in (14,47,51): put(ER,row,None,(), 'Sin renglón separado en la presentación publicada; celda vacía.')
        for row in (19,23,27,31):
            observations[ER][row][-1]=f'{y}: apertura PMSO no publicada; total disponible en fila 18. Fórmula preservada, sin estimación.'
        for row,formula in {2:f'{c}3+{c}7',3:f'SUM({c}4:{c}6)',7:f'{c}8+{c}9',10:f'{c}11+{c}15',11:f'SUM({c}12:{c}14)',15:f'{c}16+{c}17',18:f'SUM({c}19:{c}21)',23:f'{c}18*1000000/{c}25',24:f"'{ER}'!{c}53*1000000/{c}25",26:f'{c}27-{c}28',27:f'{c}3-{c}4',28:f'{c}11-{c}13',29:f'{c}30-{c}31'}.items(): calc(BP,row,'='+formula)
        for row,keys in {4:['cash'],5:['receivables'],6:current,8:['net_utility_plant','other_property_investments'],9:['goodwill','deferred_other_assets'],12:['suppliers'],14:liabilities,16:['long_debt'],17:['deferred_tax_credits','removal_costs','other_long_liabilities'],19:['equity'],30:['gas_plant_gross','construction_work_progress'],31:['net_utility_plant']}.items(): aggregate(BP,row,keys)
        if debt: aggregate(BP,13,debt)
        else: put(BP,13,None,(),'Sin deuda corriente separada; los componentes publicados concilian con el pasivo corriente.')
        for row in (20,21): put(BP,row,None,(),'Patrimonio total informado en fila 19; sin apertura adicional en este mapeo.')
        put(BP,25,'='+str(int(value('shares_thousand'))),['shares_thousand'],'Cantidad publicada en miles de acciones.')
    for sheet in patches:
        for row,notes in observations[sheet].items():
            patches[sheet][f'N{row}']='; '.join(notes)
            patches[sheet][f'O{row}']='; '.join(sources[sheet][row])
    return patches,evidence

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--config',type=Path,required=True)
    args=ap.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8-sig'))
    years=sorted(int(y) for y in config['reports'])
    if years!=list(range(2020,2026)):
        raise ValueError('SGC: este mapeo sólo está validado para 2020-2025 completos')
    template=Path(config['template'])
    records=[extract(Path(config['reports'][str(y)]),y,BASE/'cache') for y in years]
    patches,evidence=make_patches(records)
    out=Path(config['output_dir'])/config['output_filename']
    if out.resolve()==template.resolve() or out.exists():
        raise ValueError('Elija una salida nueva; no se sobrescribe plantilla ni resultado existente')
    out.parent.mkdir(parents=True,exist_ok=True)
    package=write(template,out,patches)
    new=Book(out)
    approved=Book(config['reference']) if config.get('reference') else None
    differences=[]; count=0
    for sheet,limit in ([(ER,53),(BP,31)] if approved else []):
        for col in 'HIJKLM':
            for row in range(2,limit+1):
                ref=f'{col}{row}'; a=new.value(sheet,ref); b=approved.value(sheet,ref); count+=1
                if abs(a-b)>1e-8: differences.append({'sheet':sheet,'cell':ref,'new':a,'approved':b})
    direct=[check for rec in records for check in compare(rec,new)]
    audit={'status':'PASS' if not differences and all(c['status']=='PASS' for c in direct) else 'FAIL',
           'numeric_cells_compared':count,'differences':differences,'source_checks':direct,'package':package,
           'reference_comparison':'PASS' if approved and not differences else ('FAIL' if approved else 'NOT_RUN'),
           'template_sha256':digest(template),'output_sha256':digest(out),'sources':[{'year':r['year'],'sha256':r['sha256']} for r in records],
           'cells':evidence,'missing':[{'year':r['year'],'key':k} for r in records for k,f in r['facts'].items() if f['value'] is None]}
    (out.parent/'generacion.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    if audit['status']!='PASS': raise ValueError('Planilla generada requiere revisión: ver auditoría')
    print(json.dumps({'status':audit['status'],'numeric_cells_compared':count,'output':str(out)},ensure_ascii=False))

if __name__=='__main__': main()
