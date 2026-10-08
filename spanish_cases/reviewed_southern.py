"""Reproducible, reviewed AR/CL pilot mappings, not a general PDF extractor.

Runtime is Python only. Disclosed operands below were reviewed against the
original annual PDFs (including OCR images). SHA-256 gates prevent silently
reusing these mappings for a changed source or another year. No residual plugs,
AI services, downloads, or inferred customer allocations are used.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'sgc'))
from control_planilla import Book, NS
from escritor_excel import write
from spanish_cases.efigas import ER_FORMULAS, BP_FORMULAS
from spanish_cases.source import Source, normalize

ER='Estado de Resultados'
BP='Balance Patrimonial'
AR_HASHES={
 2023:'d3a2ce1613df352d4b9b1e74006addce31fbe7754e495022b3b42506647e778b',
 2024:'ab7e097ab055ffd08f5ded97d7c83d7fc1bef6c2ec87e2d03bc14c2981e329d8',
 2025:'2848ea06896a24509f7e874d937ffd96248c82d16fad6c0a401ae394e7b847a9',
}

# Columns: distribution, administration, commercialization. Capitalized expenses
# are intentionally excluded. All amounts are thousands of local currency.
LABELS=['Remuneraciones y cargas sociales','Honorarios directores y síndicos',
 'Honorarios por servicios profesionales','Juicios y reclamos',
 'Gastos de facturación y cobranzas','Alquileres varios','Primas de seguros',
 'Viajes y estadías','Gastos de correos y telecomunicaciones',
 'Depreciación de propiedades, planta y equipo','Amortización de activos intangibles',
 'Servidumbres de paso','Mantenimiento y reparación','Impuestos, tasas y contribuciones',
 'Impuesto a los Ingresos Brutos','Tasa ENARGAS','Deudores incobrables',
 'Publicidad y propaganda','Limpieza y vigilancia','Gastos y comisiones bancarias',
 'Servicios y suministros de terceros','Convenios de atención comercial y técnica',
 'Costo de fletes','Gastos diversos']
NATURE={
 2023:[(4112710,1175060,2056355),(0,36966,0),(228934,1334397,271361),
 (2297414,171449,0),(0,0,2403841),(15581,36649,8058),(55902,31743,436),
 (107639,13489,12692),(7033,83785,21082),(5617720,105710,168323),
 (230546,0,0),(279172,0,0),(811496,2128129,70096),(1322,26038,61768),
 (0,0,1506948),(735384,333258,424010),(0,0,-254294),(0,0,46938),
 (181719,40040,86240),(0,57856,0),(208114,162487,57000),(15768,0,196078),
 (1411403,0,0),(99289,144920,89236)],
 2024:[(7941395,3328655,3657126),(0,67761,0),(87070,2458821,570369),
 (628947,952429,0),(0,0,7340349),(32521,75740,24622),(165404,82233,1149),
 (186053,22392,29718),(19028,185256,47856),(11046823,236794,1034554),
 (111535,67700,325622),(133426,0,0),(2810280,781839,2891077),(30444,31483,138199),
 (0,0,5116173),(1266773,574070,730399),(0,0,1695031),(0,0,144379),
 (399481,88021,189584),(0,81060,0),(600064,190650,282746),(91373,0,543823),
 (2972062,0,0),(241662,304740,237302)],
 2025:[(11582081,4014825,5418498),(0,68634,0),(456927,5611391,603804),
 (35796,905416,0),(0,0,10196323),(69262,118133,46301),(240463,99945,1706),
 (399898,55526,88359),(25282,251063,62105),(14719449,339264,1486147),
 (170196,103307,496881),(266580,0,0),(5916300,1105450,4254366),(79564,105015,323165),
 (0,0,6858301),(1418241,642711,817733),(0,0,2315605),(0,0,246221),
 (595317,131171,282523),(0,80604,0),(1191422,300615,103055),(142353,0,1130437),
 (4038238,0,0),(381093,450986,410357)],
}
AR={
 2023:dict(pages=[2,3,26,27,28,31,32],gas=66365780,other_sales=1102548,
  gas_cost=[32906988,7605261],materials=[214196,1129229,-149276],
  other_income=[2059028,46846,63056,10222,277171,351299],
  other_expense=[123227,9435,322155,169786],investment_da=49305,
  finance_income=25187745,associate=66095,interest=880899,finance_tax=120050,
  recpam=15345802,tax=671868,net=6605575,pretax=7277443,
  nature_totals=[16417146,5881976,7226168],cash=3389427,receivable=8069863,
  current_other=[149276,645732,221678,24236633,1217971],
  fixed=[84144622,517856,2264308],noncurrent_other=[248545,6505,9790,29],
  suppliers=6374256,current_liab_other=[1150626,257552,754780,278282,16710725,2347273],
  long_liab=[31659,1615,3831,19244466],capital=[202351,62826285],
  reserves=[4076045,4256914,6605575],gross=215274968,net_ppe=84144622,
  assets=125122235,current_assets=37930580,current_liab=27873494,equity=77967170),
 2024:dict(pages=[15,16,39,40,41,42,44,45],gas=225111567,other_sales=4890002,
  gas_cost=[86028645,29210331],materials=[325068,1097054,-276501],
  other_income=[2432193,12274,179086,3569,386389,113906],
  other_expense=[72281,23350,1737572,88568],investment_da=107369,
  finance_income=2485150,associate=420272,interest=2440459,finance_tax=118756,
  recpam=15691056,tax=18289104,net=17787233,pretax=36076337,
  nature_totals=[28764341,9529644,25000078],cash=12290013,receivable=39376708,
  current_other=[276501,469013,41563913,2706852],
  fixed=[178179091,1237284,4823470],noncurrent_other=[961513,33036,29],
  suppliers=27651705,current_liab_other=[2073073,2505533,16609980,1543420,511142,3376887],
  long_liab=[22269,8875,40043170],capital=[202351,137051093],
  reserves=[9595370,22935322,17787233],gross=475472657,net_ppe=178179091,
  assets=281917423,current_assets=96683000,current_liab=54271740,equity=187571369),
 2025:dict(pages=[18,19,40,41,42,43,46,47],gas=318160652,other_sales=7968941,
  gas_cost=[118195293,39844135],materials=[363733,1103965,-570845],
  other_income=[2356457,135852,224979,2958084,358791],
  other_expense=[381268,11406,2583311,68561],investment_da=141242,
  finance_income=8300177,associate=827148,interest=38534,finance_tax=222471,
  recpam=10229725,tax=24535998,net=52887879,pretax=77423877,
  nature_totals=[41728462,14384056,35141887],cash=12572367,receivable=77170139,
  current_other=[570845,264316,9620415,4614895],
  fixed=[238063216,1509877,6203974],noncurrent_other=[2092006,65390,29],
  suppliers=63603163,current_liab_other=[3355,1124935,13501754,2243666,634260,1488839],
  long_liab=[12044308,12513,51993167],capital=[202351,180352853],
  reserves=[13792535,0,11749770],gross=642509804,net_ppe=238063216,
  assets=352747469,current_assets=104812977,current_liab=82599972,equity=206097509),
}
CL={
 2024:dict(pages=[3,6,7,8,29,64,73,84,90,91,92,93],gas=662303136,
  gas_cost=[438587967],personal=[16991256,1504744,859164,344428,1832440],
  admin=23069540,marketing=1930092,om=[11028256,2377243],
  da=[33450025,4695461,1629094],other_income=[14856,2501467,42692041,107922141,60941950,95134],
  other_expense=[120411,3919,39901],baddebt=0,finance_income=[11700206],
  finance_expense=[8141652,9520729,162747,220454,447171,24648610,5279770,24735],
  tax=79963717,net=221297405,pretax=301261122,
  cash=87425394,receivable=81621531,current_other=[9409,163971,213564,4837922],
  fixed=[1302996590,20395347,2677123],noncurrent_other=[271206],
  suppliers=36845539,short_debt=[57475750,727204],
  current_liab_other=[30661732,2733441,794804,3618741,1158395],
  long_debt=[69902703,136524859],long_liab=[118703271,274569692,2766407,1830859],
  capital=[186201688,21162206],reserves=[470769904,84164862],
  gross=1627208132,net_ppe=1302996590,assets=1500612057,current_assets=174271791,
  current_liab=134015606,equity=762298660),
 2025:dict(pages=[9,10,11,63,72,85,91,92,93,94,95],gas=652420499,
  gas_cost=[412194941],personal=[19645701,2535549,463967,386754,2218724],
  admin=21810321,marketing=2132800,om=[10357406,2874060],
  da=[37716832,4261910,1545422],other_income=[33307,879949,18748084],
  other_expense=[270424,7194,28916],baddebt=362572,finance_income=[9258211,4452417],
  finance_expense=[23775585,4609667],tax=38354704,net=100239018,pretax=138593722,
  cash=104316956,receivable=77380304,current_other=[78325,1316642,10868,6171723,8540755],
  fixed=[1305650387,23429815,1615354],noncurrent_other=[4753459,71581],
  suppliers=74298946,short_debt=[41411442,143934406],
  current_liab_other=[5840477,24359440,278962,5712221,554703],
  long_debt=[84843675,118830183],long_liab=[305538244,3650655,1346351],
  capital=[186201688,21162206],reserves=[457923178,57449392],
  gross=1666999866,net_ppe=1305650387,assets=1533336169,current_assets=197815573,
  current_liab=296390597,equity=722736464),
}

def formula(values, sign=1):
    if isinstance(values,int): values=[values]
    # Keep exact disclosed operands rather than the precomputed aggregate.
    values=[v for v in values if v != 0]
    if not values: return None
    return ('=-' if sign<0 else '=')+'('+'+'.join(map(str,values))+')/1000'

def layout(template):
    book=Book(template)
    with ZipFile(template) as z:
        strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    def label(sheet,row):
        cell=book.sheets[sheet][f'A{row}']
        return normalize(strings[int(cell.findtext('m:v',namespaces=NS))])
    assert label(ER,39)=='otrosgastos' and label(ER,57)=='resultadonetodelejercicio'
    assert label(BP,26)=='capitaldetrabajo' and label(BP,29)=='activoinmovilizado'
    mapping={r:r if r<35 else r+4 for r in range(2,54)}
    er={mapping[r]:re.sub(r'\{c\}(\d+)',lambda m:'{c}'+str(mapping[int(m[1])]),f)
        for r,f in ER_FORMULAS.items()}
    er.update({35:'SUM({c}36:{c}38)',47:'{c}17+{c}18+{c}35+{c}39'})
    return er,BP_FORMULAS

def income_ar(year,d):
    n=NATURE[year]
    totals=[sum(row[i] for row in n) for i in range(3)]
    # Permit a one-thousand-ARS presentation rounding, never a balancing plug.
    if any(abs(a-b)>1 for a,b in zip(totals,d['nature_totals'])):
        raise ValueError(f'Naturaleza AR {year}: {totals} != {d["nature_totals"]}')
    rows={3:formula(d['gas']),13:formula([d['other_sales'],*d['other_income'],max(0,-n[16][2])]),
          16:formula(d['gas_cost'],-1),26:formula(d['materials'],-1),
          40:formula(d['other_expense'],-1),
          41:formula([*n[13],n[14][2],d['finance_tax']],-1),42:formula(n[15],-1),
          44:formula(n[3],-1),45:formula(max(0,n[16][2]),-1),
          48:formula([*n[9],*n[10],d['investment_da']],-1),
          51:formula([d['finance_income'],d['associate']]),
          52:formula([d['interest'],d['recpam']],-1),56:formula(d['tax'],-1)}
    services=[1,2,4,5,8,11,18,20,21,22]
    other=[6,7,12,17,19,23]
    for i,row in [(1,20),(2,21),(0,22)]: rows[row]=formula(n[0][i],-1)
    for i,row in [(1,28),(2,29),(0,30)]: rows[row]=formula([n[j][i] for j in services],-1)
    for i,row in [(1,32),(2,33),(0,34)]: rows[row]=formula([n[j][i] for j in other],-1)
    return rows

def income_cl(d):
    return {3:formula(d['gas']),13:formula(d['other_income']),16:formula(d['gas_cost'],-1),
      19:formula(d['personal'],-1),32:formula(d['admin'],-1),
      33:formula(d['marketing'],-1),34:formula(d['om'],-1),
      40:formula(d['other_expense'],-1),45:formula(d['baddebt'],-1),48:formula(d['da'],-1),
      51:formula(d['finance_income']),52:formula(d['finance_expense'],-1),56:formula(d['tax'],-1)}

def balance(d,company):
    return {4:formula(d['cash']),5:formula(d['receivable']),6:formula(d['current_other']),
      8:formula(d['fixed']),9:formula(d['noncurrent_other']),12:formula(d['suppliers']),
      13:formula(d.get('short_debt',[])),14:formula(d['current_liab_other']),
      16:formula(d.get('long_debt',[])),17:formula(d['long_liab']),19:formula(d['capital']),
      21:formula(d['reserves']),25:formula(202351288 if company=='ecogas_cuyo' else 37000),
      30:formula(d['gross']),31:formula(d['net_ppe'])}

def build(company, *, template=None, reports=None, output=None):
    if company not in ('ecogas_cuyo','metrogas_chile'):
        raise ValueError('Empresa no revisada')
    facts=AR if company=='ecogas_cuyo' else CL
    if company=='ecogas_cuyo' and reports is not None and template is not None:
        inventory={'template':str(template),'reports':[{'year':year,'path':str(path),'sha256':AR_HASHES[year]}
                   for year,path in reports.items() if year in AR_HASHES]}
    else:
        inventory=json.loads((ROOT/'cache/new_cases/inventory.json').read_text(encoding='utf-8'))[company]
    template=Path(template or inventory['template'])
    if reports is not None:
        if set(reports)!=set(facts):
            raise ValueError('Períodos fuera del caso revisado')
        inventory=dict(inventory, reports=[dict(r,path=str(reports[r['year']])) for r in inventory['reports'] if r['year'] in facts])
    erform,bpform=layout(template)
    patches={ER:{},BP:{}}
    output=Path(output) if output is not None else ROOT/'outputs'/('Ecogas Cuyo' if company=='ecogas_cuyo' else 'Metrogas Chile')/(
        'AR - Ecogas Cuyo - Datos Financieros - 2023-2025.xlsx' if company=='ecogas_cuyo'
        else 'CL - Metrogas Chile - Datos Financieros - 2024-2025 - INDIVIDUAL.xlsx')
    if output.exists(): raise ValueError('La salida ya existe; no se sobrescribe')
    evidence=[]
    obs={ER:{},BP:{}}
    for year,d in facts.items():
        source=next(r for r in inventory['reports'] if r['year']==year)
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('El PDF cambió: requiere una nueva revisión, no reutilizar valores')
        c=chr(ord('K')+year-2023)
        for sheet,last,formulas in [(ER,57,erform),(BP,31,bpform)]:
            patches[sheet].update({f'{c}{r}':None for r in range(2,last+1)})
            patches[sheet].update({f'{c}{r}':'='+f.format(c=c) for r,f in formulas.items()})
        patches[ER].update({f'{c}{r}':v for r,v in (income_ar(year,d) if company=='ecogas_cuyo' else income_cl(d)).items()})
        patches[BP].update({f'{c}{r}':v for r,v in balance(d,company).items()})
        patches[BP][f'{c}23']=f'={c}18*1000000/{c}25'
        patches[BP][f'{c}24']=f"='{ER}'!{c}57*1000000/{c}25"
        evidence.append({'year':year,'pdf':source,'facts_thousands':d,
            'nature_rows':dict(zip(LABELS,NATURE[year])) if company=='ecogas_cuyo' else None})
        for sheet,last in [(ER,57),(BP,31)]:
            for r in range(2,last+1):
                message='Fórmula de total; componentes cargados con operandos publicados.' if f'{c}{r}' in patches[sheet] and patches[sheet][f'{c}{r}'] is not None else 'Sin partida separada informada; no se imputa un importe.'
                if sheet==ER:
                    if r==3: message='Ventas publicadas sin desglose monetario por cliente; reemplazo autorizado del subtotal.'
                    if r==14: message='Ventas informadas netas; no se duplica una deducción no desglosada.'
                    if r==13: message='Otros ingresos y reversiones positivas; no se registran como gastos positivos.'
                    if company=='ecogas_cuyo':
                        if r in (16,18,48): message='Reclasificación de naturaleza: gas/transporte en costo; distribución en PMSO/otros; depreciaciones separadas. Se excluyen activaciones.'
                        if r in (24,25): message='Sin materiales separados de administración/comercial; consumo de existencias informado íntegro en O&M, sin estimar un segundo gasto.'
                        if 28<=r<=30: message='Servicios: honorarios, alquileres, facturación, correos, servidumbres, limpieza, terceros, convenios y fletes; por función.'
                        if 32<=r<=34: message='Seguros, viajes, mantenimiento/reparaciones, publicidad, comisiones bancarias y gastos diversos; por función.'
                        if r==41: message='Impuestos y tasas más Ingresos Brutos comercial/financiero, separados de PMSO; sin doble conteo financiero.'
                        if r==42: message='Tasa ENARGAS por función, separada del PMSO.'
                        if r==44: message='Juicios y reclamos informados, fuera del PMSO.'
                        if r==45: message='Incobrables negativos; reversión de 2023 trasladada a otros ingresos.'
                        if r==52: message='Intereses de financiación más pérdida RECPAM. IIBB financiero reclasificado a tributos. Intereses comerciales de otros egresos permanecen en otros gastos.'
                    else:
                        if r in (23,27): message='REVIEW: no hay separación de materiales/servicios ni base histórica numérica para estimar; importes incluidos en gastos funcionales de Otros PMSO, sin duplicar.'
                        if r==19: message='Personal total: suma de sueldos, beneficios cortos, terminación, beneficios largos y otros; sin función informada.'
                        if 32<=r<=34: message='Gastos funcionales publicados: administración, mercadotecnia y operación/mantenimiento más varios; no se infiere naturaleza materiales/servicios.'
                        if r==52: message='Gastos financieros negativos, incluidos cambio y reajustes negativos; reversión TGN 2024 trasladada a otros ingresos. Cambio 2024 tomado del estado principal, difiere M$1 de la nota.'
                else:
                    if r==5: message='Deudores comerciales y otras cuentas por cobrar según balance; agregado publicado, no exclusivamente clientes.'
                    if r==8: message='PPE, intangibles y activos fijos adicionales publicados, sin sumar dos veces su apertura.'
                    if r in (13,16): message='Préstamos y bonos por plazo; derivados y arrendamientos en Otros.' if company=='metrogas_chile' else 'No se presentan préstamos bancarios en el balance; sin importe inventado.'
                    if r==20: message='No se informa reserva de valor llave; no confundir con reservas legales u otras reservas.'
                    if r in (30,31): message='PPE bruto/neto publicado; perímetro de activos PPE (intangibles y otros fijos no incluidos en esta pareja).'
                    if r==29: message='Fórmula: inmovilizado bruto menos neto, según instrucción del usuario.'
                obs[sheet].setdefault(r,[]).append(f'{year}: {message}')
    for sheet,rows in obs.items():
        for row,messages in rows.items():
            patches[sheet][f'N{row}']=' | '.join(messages)
            patches[sheet][f'O{row}']=' | '.join(f'{year}: {Path(next(r["path"] for r in inventory["reports"] if r["year"]==year)).name}; páginas PDF '+','.join(map(str,d['pages']))+'; miles de moneda local /1000.' for year,d in facts.items())
    if company=='metrogas_chile':
        patches[ER]['N2']+=' | 2024 individual: auditoría p.3 y absorción de última subsidiaria p.29; algunos encabezados aún dicen consolidado. 2022/2023 no modificados.'
    # A dedicated evidence file makes the pilot's supervised mapping transparent.
    audit={'company':company,'method':'Reviewed disclosed operands; deterministic Python pilot, not a generic unattended PDF extractor',
           'output':str(output),'template_sha256':hashlib.sha256(template.read_bytes()).hexdigest(),
           'evidence':evidence,'checks':[]}
    candidate=output.with_suffix('.validating.xlsx')
    status=write(template,candidate,patches)
    audit['preservation']=status
    book=Book(candidate)
    for year,d in facts.items():
        c=chr(ord('K')+year-2023)
        checks=[(ER,57,d['net']),(ER,53,d['pretax']),
                (BP,2,d['assets']),(BP,3,d['current_assets']),(BP,11,d['current_liab']),(BP,18,d['equity'])]
        for sheet,row,published in checks:
            actual=book.value(sheet,f'{c}{row}'); difference=actual-published/1000
            audit['checks'].append(dict(year=year,sheet=sheet,cell=f'{c}{row}',actual=actual,published=published/1000,difference=difference))
            if abs(difference)>0.00101: raise ValueError(f'No conciliado {year} {sheet} {row}: {difference}')
        if abs(book.value(BP,f'{c}2')-book.value(BP,f'{c}10')-book.value(BP,f'{c}18'))>0.00101:
            raise ValueError('No se cumple Activo = Pasivo + Patrimonio')
    candidate.replace(output)
    output.with_suffix('.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(output),'checks':audit['checks']},ensure_ascii=False))
    return audit

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('company',choices=['ecogas_cuyo','metrogas_chile'])
    build(ap.parse_args().company)
