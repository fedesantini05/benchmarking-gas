"""Read-only, limited arithmetic evaluator for the approved template formulas."""
import ast
import operator
import posixpath
import re
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
OPS = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul, ast.Div:operator.truediv}

class MissingInput(ValueError):
    """Explicitly unavailable source value; must not become numerical zero."""
    pass

def arithmetic(expression):
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int,float): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS: return OPS[type(node.op)](visit(node.left),visit(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd,ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op,ast.USub) else 1)
        raise ValueError('Formula fuera del subconjunto aritmetico admitido')
    return visit(ast.parse(expression,mode='eval'))

class Book:
    def __init__(self,path):
        self.sheets={}
        with ZipFile(path) as z:
            rels={n.get('Id'):n.get('Target') for n in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
            for node in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',NS):
                target=rels[node.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
                target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
                self.sheets[node.get('name')]={c.get('r'):c for c in ET.fromstring(z.read(target)).findall('.//m:c',NS)}
        for cells in self.sheets.values():
            masters={}
            for ref,cell in cells.items():
                f=cell.find('m:f',NS)
                if f is not None and f.get('t')=='shared' and f.text:
                    masters[f.get('si')]=(ref,f.text)
            def colnum(label):
                value=0
                for char in label: value=value*26+ord(char)-64
                return value
            def colname(number):
                label=''
                while number:
                    number,rem=divmod(number-1,26); label=chr(65+rem)+label
                return label
            for ref,cell in cells.items():
                f=cell.find('m:f',NS)
                if f is None or f.get('t')!='shared' or f.text: continue
                origin,formula=masters[f.get('si')]
                old=re.fullmatch(r'([A-Z]+)(\d+)',origin); new=re.fullmatch(r'([A-Z]+)(\d+)',ref)
                dx=colnum(new[1])-colnum(old[1]); dy=int(new[2])-int(old[2])
                def shift(m):
                    return m[1]+(m[2] if m[1] else colname(colnum(m[2])+dx))+m[3]+str(int(m[4])+(0 if m[3] else dy))
                f.text=re.sub(r'(\$?)([A-Z]+)(\$?)(\d+)',shift,formula)
    def value(self,sheet,ref,stack=()):
        key=(sheet,ref)
        if key in stack: raise ValueError('Referencia circular')
        cell=self.sheets[sheet].get(ref)
        if cell is None: return 0
        formula=cell.findtext('m:f',namespaces=NS)
        if formula == 'NA()' or (cell.get('t') == 'e' and cell.findtext('m:v',namespaces=NS) == '#N/A'):
            raise MissingInput(f'Fuente no disponible: {key}')
        if formula is None:
            raw=cell.findtext('m:v',namespaces=NS)
            if cell.get('t') in ('s','inlineStr','e'): raise ValueError(f'Celda no numerica {key}')
            return float(raw) if raw else 0
        def val(s,r): return self.value(s,r,stack+(key,))
        guarded=re.fullmatch(r'IF\(COUNT\(([^)]*)\)=(\d+),(.*),""\)',formula)
        if guarded:
            refs=[]
            for item in guarded[1].split(','):
                span=re.fullmatch(r'([A-Z]+)(\d+):([A-Z]+)(\d+)',item)
                if span:
                    if span[1]!=span[3]: raise ValueError('COUNT solo admite rangos verticales')
                    refs.extend(f'{span[1]}{row}' for row in range(int(span[2]),int(span[4])+1))
                elif re.fullmatch(r'[A-Z]+\d+',item): refs.append(item)
                else: raise ValueError('COUNT fuera del subconjunto admitido')
            count=0
            for target in refs:
                node=self.sheets[sheet].get(target)
                if node is None: continue
                target_formula=node.findtext('m:f',namespaces=NS)
                if target_formula is None and not node.findtext('m:v',namespaces=NS): continue
                value=val(sheet,target)
                if type(value) in (int,float): count+=1
            if count!=int(guarded[2]): return ''
            formula=guarded[3]
        def rng(match):
            c1,r1,c2,r2=match.groups()
            if c1!=c2: raise ValueError('Solo sumas verticales')
            return str(sum(val(sheet,f'{c1}{row}') for row in range(int(r1),int(r2)+1)))
        formula=re.sub(r'SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)',rng,formula)
        formula=re.sub(r"'([^']+)'!([A-Z]+\d+)",lambda m:str(val(m[1],m[2])),formula)
        formula=formula.replace('$','')
        formula=re.sub(r'\b[A-Z]+\d+\b',lambda m:str(val(sheet,m[0])),formula)
        return arithmetic(formula)

def compare(record,book):
    f=record['facts']
    def v(k):
        if f[k]['value'] is None: raise ValueError(f'Falta {k}')
        return f[k]['value']/1000
    col=chr(ord('H')+record['year']-2020)
    er='Estado de Resultados'; bp='Balance Patrimonial'
    checks={
        (er,3):v('gas_operating_revenue'), (er,4):v('residential'),
        (er,5):v('small_commercial')+v('large_commercial'), (er,6):v('industrial_other'),
        (er,16):-v('gas_cost'), (er,18):-v('operations_maintenance'),
        (er,37):-v('taxes_other_income'), (er,44):-v('da'),
        (er,49):v('pretax'), (er,52):-v('income_tax'), (er,53):v('net_income'),
        (bp,2):v('assets'), (bp,3):v('current_assets'), (bp,4):v('cash'),
        (bp,5):v('receivables'), (bp,8):v('net_utility_plant')+v('other_property_investments'),
        (bp,9):v('goodwill')+v('deferred_other_assets'), (bp,11):v('current_liabilities'),
        (bp,12):v('suppliers'), (bp,16):v('long_debt'), (bp,18):v('equity'),
        (bp,27):v('current_assets')-v('cash'), (bp,29):v('accumulated_depreciation'),
        (bp,30):v('gas_plant_gross')+v('construction_work_progress'), (bp,31):v('net_utility_plant'),
        (bp,25):f['shares_thousand']['value']}
    result=[]
    for (sheet,row),value in checks.items():
        approved=book.value(sheet,f'{col}{row}')
        result.append({'year':record['year'],'sheet':sheet,'cell':f'{col}{row}','extracted':value,
                       'approved':approved,'difference':value-approved,'status':'PASS' if abs(value-approved)<1e-8 else 'DIFFERENCE'})
    return result
