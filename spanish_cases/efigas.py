"""Conservative Efigas management-report adapter; no AI or residual allocation.

Load published aggregates throughout the template when detail is unavailable,
as explicitly requested by the user. Preserve calculable totals; keep unknown
details blank. User-approved exception: carry combined selling/financial costs
in row 16, visibly documented, never duplicate them in row 52.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import re
from zipfile import ZipFile
from lxml import etree as ET

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sgc'))
from control_planilla import Book, MissingInput, NS
from escritor_excel import write
from spanish_cases.source import Source, normalize
from spanish_cases.vocabulary import efigas_label

ER = 'Estado de Resultados'
BP = 'Balance Patrimonial'
ER_FORMULAS = {
    2:'{c}3+{c}13', 3:'SUM({c}4:{c}12)', 15:'{c}2+{c}14',
    17:'{c}15+{c}16', 18:'{c}19+{c}23+{c}27+{c}31',
    19:'SUM({c}20:{c}22)',23:'SUM({c}24:{c}26)',
    27:'SUM({c}28:{c}30)',31:'SUM({c}32:{c}34)',
    35:'SUM({c}36:{c}42)',43:'{c}17+{c}18+{c}35',
    45:'{c}43+{c}44',46:'{c}47+{c}48',49:'{c}45+{c}46',
    50:'{c}51+{c}52',53:'{c}49+{c}50',
}
BP_FORMULAS = {
    2:'{c}3+{c}7',3:'SUM({c}4:{c}6)',7:'{c}8+{c}9',
    10:'{c}11+{c}15',11:'SUM({c}12:{c}14)',15:'{c}16+{c}17',
    18:'SUM({c}19:{c}21)',26:'{c}27-{c}28',27:'{c}3-{c}4',
    28:'{c}11-{c}13',29:'{c}30-{c}31',
}


def published_formula(value, sign=1):
    """A source-only total, not a fictitious decomposition. Units already millions."""
    if type(value) is not int or sign not in (-1,1):
        raise ValueError('Se requiere un importe publicado entero y signo válido')
    return '='+str(sign*value)


def sales_inputs(income, column):
    """No customer split: one published aggregate, not nine fictitious zeroes.

Other income and sales deductions have no separate disclosure; they remain
blank because the published aggregate has already been included once. This
does not authorize imputing expense components or overriding other totals.
"""
    return {f'{column}3':income, **{f'{column}{row}':None for row in range(4,15)}}


def template_layout(template):
    """Match semantic row anchors; never apply standard row numbers blindly."""
    book=Book(template)
    with ZipFile(template) as archive:
        strings=[''.join(s.itertext()) for s in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
    def labels(sheet):
        result={}
        for ref,cell in book.sheets[sheet].items():
            if re.fullmatch('A[0-9]+',ref):
                raw=cell.findtext('m:v',namespaces=NS)
                text=strings[int(raw)] if cell.get('t')=='s' else ''.join(cell.itertext())
                result[int(ref[1:])]=normalize(text)
        return result
    erlabels=labels(ER); bplabels=labels(BP)
    if erlabels.get(39)!=normalize('Otros Gastos') or erlabels.get(57)!=normalize('Resultado Neto del ejercicio'):
        raise ValueError('Efigas: disposición de filas no reconocida; requiere revisión')
    if bplabels.get(27)!=normalize('Capital de Trabajo') or bplabels.get(32)!=normalize('Activo Inmovilizado Neto (asociado al negocio de Distrib.)'):
        raise ValueError('Efigas: balance no reconocido; requiere revisión')
    ermap={r:r if r<35 else r+4 for r in range(2,54)}
    bpmap={r:r if r<25 else r+1 for r in range(2,32)}
    def translate(formulas,mapping):
        return {mapping[row]:re.sub(r'\{c\}(\d+)',lambda m:'{c}'+str(mapping[int(m[1])]),formula)
                for row,formula in formulas.items()}
    erformulas=translate(ER_FORMULAS,ermap)
    # Existing template includes a separate CAOM subtotal, preserved as such.
    erformulas[35]='SUM({c}36:{c}38)'
    erformulas[47]='{c}17+{c}18+{c}35+{c}39'
    return ermap,bpmap,erformulas,translate(BP_FORMULAS,bpmap)


def extract(report, year):
    # Always reread the actual PDF, never trust a stale extraction cache.
    source = Source('efigas',year,pages=[page.extract_text() or '' for page in PdfReader(report).pages])
    erpage, bppage = {2023:(25,25),2024:(23,24),2025:(26,27)}[year]
    if 'millones' not in source.pages[erpage-1].lower():
        raise ValueError('No se pudo confirmar la unidad: millones de COP')
    def v(concept, page):
        return source.row(efigas_label(concept,year),[page],count=2,first=True)[1]
    facts = {
        'income':v('income',erpage),
        'sale_and_finance_cost' if year>2023 else 'sale_cost':v('sale_cost',erpage),
        'operating_expenses':v('operating_expenses',erpage),
        'pretax':v('pretax',erpage),
        'income_tax':v('income_tax',erpage),
        'net_income':v('net_income',erpage),
        'current_assets':v('current_assets',bppage),
        'noncurrent_assets':v('noncurrent_assets',bppage),
        'assets':v('assets',bppage),
        'current_liabilities':v('current_liabilities',bppage),
        'noncurrent_liabilities':v('noncurrent_liabilities',bppage),
        'liabilities':v('liabilities',bppage),
        'equity':v('equity',bppage),
    }
    return {'year':year,'file':str(report),'sha256':hashlib.sha256(report.read_bytes()).hexdigest(),
            'unit':'millones COP','facts':facts,'evidence':source.evidence,
            'er_page':erpage,'bp_page':bppage,
            'source_checks':{
                'assets_minus_components':facts['assets']-facts['current_assets']-facts['noncurrent_assets'],
                'assets_minus_liabilities_and_equity':facts['assets']-facts['liabilities']-facts['equity'],
                'net_minus_pretax_less_tax':facts['net_income']-(facts['pretax']-facts['income_tax']),
            }}


def build(template, reports, output):
    if output.exists():
        raise FileExistsError(f'No se sobrescribe una entrega existente: {output}')
    records = [extract(Path(reports[year]),year) for year in (2023,2024,2025)]
    ermap,bpmap,erformulas,bpformulas=template_layout(template)
    patches = {ER:{},BP:{}}; notes = {ER:{},BP:{}}
    checks=[]; overrides=[]
    def guarded(formula,c,refs):
        refs=','.join(f'{c}{r}' for r in refs)
        return f'=IF(COUNT({refs})={len(refs.split(","))},{formula.format(c=c)},"")'
    for record in records:
        year=record['year']; c=chr(ord('K')+year-2023); facts=record['facts']
        for sheet,last,formulas in ((ER,57,erformulas),(BP,32,bpformulas)):
            for row in range(2,last+1):
                if sheet==BP and row==22:
                    continue  # Shares section heading, not a monetary input.
                patches[sheet][f'{c}{row}']=None
                description='MISSING: no publicado o no reconstruible; celda vacía, no cero.'
                notes[sheet].setdefault(row,[]).append(f'{year}: {description}')
        patches[ER].update(sales_inputs(facts['income'],c))
        published={ER:{3:('income',1),18:('operating_expenses',-1),53:('pretax',1),56:('income_tax',-1)},
                   BP:{3:('current_assets',1),7:('noncurrent_assets',1),11:('current_liabilities',1),
                       15:('noncurrent_liabilities',1),18:('equity',1)}}
        published[ER][16]=('sale_cost' if year==2023 else 'sale_and_finance_cost',-1)
        for sheet,rows in published.items():
            for row,(key,sign) in rows.items():
                patches[sheet][f'{c}{row}']=published_formula(facts[key],sign)
                notes[sheet][row][-1]=f'{year}: total publicado ({key}), fórmula con el importe único de la fuente; sin sumandos adicionales informados. Millones COP, sin conversión. Subfilas sin apertura vacías.'
                overrides.append({'year':year,'sheet':sheet,'cell':f'{c}{row}','fact':key,'value':sign*facts[key]})
        notes[ER][3][-1]+=' Incluye gas y financiación no bancaria; no es venta exclusiva de gas. Criterio del usuario, como 2022.'
        notes[ER][18][-1]+=' Clasificación agregada como en 2022; no permite separar naturaleza, función ni depreciación. No estimar pilares PMSO sin base histórica.'
        for row in range(4,13):
            notes[ER][row][-1]=f'{year}: sin desglose publicado por tipo de cliente; celda vacía, agregado en fila 3.'
        for row in (13,14):
            notes[ER][row][-1]=f'{year}: sin apertura separada. Se deja vacío; los ingresos operacionales publicados ya están incluidos una sola vez en fila 3. No es un cero informado.'
        for row in (2,15,54,57):
            patches[ER][f'{c}{row}']='='+erformulas[row].format(c=c)
            notes[ER][row][-1]=f'{year}: CALCULATED: fórmula conservada sobre los agregados publicados; sin imputar apertura no informada.'
        notes[ER][54][-1]+=' Sólo impuesto a la renta publicado; no se informa amortización de valor llave separada.'
        erguards={17:[15,16],19:[20,21,22],23:[24,25,26],27:[28,29,30],31:[32,33,34],
                  35:[36,37,38],39:list(range(40,47)),47:[17,18,35,39,48],49:[47,48],50:[51,52]}
        bpguards={27:[28,29],28:[3,4],29:[11,13],30:[31,32]}
        for sheet,guards,formulas in ((ER,erguards,erformulas),(BP,bpguards,bpformulas)):
            for row,refs in guards.items():
                patches[sheet][f'{c}{row}']=guarded(formulas[row],c,refs)
                notes[sheet][row][-1]=f'{year}: fórmula conservada con control de datos ausentes. Vacío cuando faltan componentes, no cero. Filas requeridas: {refs}.'
        for row in (2,10):
            patches[BP][f'{c}{row}']='='+bpformulas[row].format(c=c)
            notes[BP][row][-1]=f'{year}: CALCULATED: suma de componentes agregados publicados.'
        if year>2023:
            notes[ER][16][-1]+=f' OBSERVADO: costo de venta & financiero combinado ({facts["sale_and_finance_cost"]:,} millones COP), cargado íntegro en esta fila por autorización del usuario. No es costo exclusivo de gas.'
            notes[ER][52][-1]=f'{year}: costo financiero incluido en el total combinado de fila 16; sin importe separado publicado. Vacío para no duplicarlo; no significa costo financiero cero.'
            notes[ER][17][-1]+=' Subtotal después del costo combinado de venta y financiero; no equivale al margen bruto exclusivamente operativo.'
        else:
            notes[ER][16][-1]+=' Costo de venta de todas las líneas, no exclusivamente de gas; criterio agregado como 2022.'
        notes[ER][53][-1]+=' Resultado antes de impuestos publicado; falta apertura para reconstruirlo desde EBIT y resultado financiero. No se usa una diferencia residual.'
        if record['source_checks']['assets_minus_components']:
            patches[BP][f'{c}2']=published_formula(facts['assets'])
            notes[BP][2][-1]=f'{year}: total activo publicado; los componentes publicados difieren en {record["source_checks"]["assets_minus_components"]} millones COP. Sin ajuste artificial.'
            overrides.append({'year':year,'sheet':BP,'cell':f'{c}2','fact':'assets','value':facts['assets']})
        if record['source_checks']['net_minus_pretax_less_tax']:
            patches[ER][f'{c}57']=published_formula(facts['net_income'])
            notes[ER][57][-1]=f'{year}: resultado neto publicado; pretax menos impuesto difiere en {record["source_checks"]["net_minus_pretax_less_tax"]} millones COP. Se usa el neto publicado sin crear una partida de ajuste.'
            overrides.append({'year':year,'sheet':ER,'cell':f'{c}57','fact':'net_income','value':facts['net_income']})
        checks.append({'year':year,'net_reconciliation':'PUBLISHED_AGGREGATE_OR_TAX_BRIDGE',
                       'detail_reconciliation':'NOT_AVAILABLE','status':'PARTIAL'})
        for sheet,rows in notes.items():
            for row,descriptions in rows.items():
                patches[sheet][f'N{row}']=' | '.join(descriptions)
    for sheet,rows in notes.items():
        for row in rows:
            patches[sheet][f'O{row}']=' | '.join(
                f'{r["year"]}: {Path(r["file"]).name}; PDF p. {r["er_page"] if sheet==ER else r["bp_page"]}; millones COP.'
                for r in records)
    result=write(template,output,patches,allow_missing=True)
    book=Book(output)
    for record in records:
        c=chr(ord('K')+record['year']-2023)
        targets={ER:{3:('income',1),18:('operating_expenses',-1),53:('pretax',1),56:('income_tax',-1),57:('net_income',1)},
                 BP:{2:('assets',1),3:('current_assets',1),7:('noncurrent_assets',1),10:('liabilities',1),
                     11:('current_liabilities',1),15:('noncurrent_liabilities',1),18:('equity',1)}}
        targets[ER][16]=('sale_cost' if record['year']==2023 else 'sale_and_finance_cost',-1)
        for sheet,rows in targets.items():
            for row,(fact,sign) in rows.items():
                if book.value(sheet,f'{c}{row}')!=sign*record['facts'][fact]:
                    raise ValueError(f'Total no coincide con fuente: {sheet}!{c}{row}')
        for sheet,values in patches.items():
            for ref,value in values.items():
                if ref.startswith(c) and isinstance(value,str) and value.startswith('='):
                    if book.sheets[sheet][ref].findtext('m:f',namespaces=NS)!=value[1:]:
                        raise ValueError(f'Fórmula no conservada: {sheet}!{ref}')
        for ref in (f'{c}27',f'{c}28',f'{c}29',f'{c}30'):
            if book.value(BP,ref)!='': raise ValueError('Capital de trabajo/inmovilizado incompleto aparenta ser un importe')
        if book.sheets[ER][f'{c}52'].findtext('m:v',namespaces=NS):
            raise ValueError('Costo financiero no separado se duplicó o se imputó')
    audit={'company':'Efigas S.A. E.S.P.','status':'PARTIAL','policy':'PUBLISHED_TOTALS_WITH_FORMULAS_AND_AUTHORIZED_COMBINED_COST',
           'combined_cost_approval':'2026-10-07: usuario autoriza costo de venta y financiero combinado en fila 16, observado, sin duplicación',
           'template':str(template),'template_sha256':hashlib.sha256(Path(template).read_bytes()).hexdigest(),
           'output':str(output),'records':records,'checks':checks,'writer_checks':result,'published_overrides':overrides,
           'layout':{'er_rows':ermap,'bp_rows':bpmap,'caom_subtotal_row':35},
           'limitations':['No contiene estados financieros y notas completos.',
                          'Ingresos incluyen gas y financiación no bancaria sin apertura suficiente.',
                          'Costo 2024/2025 combinado incluye financiero en fila 16; margen bruto no exclusivamente operativo.',
                          'No existen bases históricas suficientes para estimar pilares PMSO.',
                          'No se hicieron asignaciones por residuos ni ajustes para conciliar.']}
    output.with_suffix('.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    return audit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--template',required=True,type=Path)
    parser.add_argument('--reports-dir',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    reports={}
    for year in (2023,2024,2025):
        matches=[p for p in args.reports_dir.iterdir() if p.suffix.lower()=='.pdf' and str(year) in p.stem]
        if len(matches)!=1:
            raise ValueError(f'Fuente anual ambigua o inexistente: {year}')
        reports[year]=matches[0]
    audit=build(args.template,reports,args.output)
    print(json.dumps({'output':audit['output'],'status':audit['status'],'checks':audit['checks']},ensure_ascii=False))


if __name__=='__main__':
    main()
