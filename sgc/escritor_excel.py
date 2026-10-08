"""Narrow OOXML writer: preserve workbook features and store formula caches."""
import math
from copy import copy
import re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as ET
from control_planilla import Book, NS, MissingInput

MAIN=NS['m']
def tag(name): return '{'+MAIN+'}'+name

def write(template, output, patches, *, allow_missing=False):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.pending.xlsx')
    with ZipFile(template) as src:
        wb=ET.fromstring(src.read('xl/workbook.xml'))
        rels={r.get('Id'):r.get('Target') for r in ET.fromstring(src.read('xl/_rels/workbook.xml.rels'))}
        paths={}
        for s in wb.findall('m:sheets/m:sheet',NS):
            target=rels[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')].lstrip('/')
            paths[s.get('name')]=target if target.startswith('xl/') else 'xl/'+target
        changed={}
        for name,values in patches.items():
            root=ET.fromstring(src.read(paths[name]))
            rows={r.get('r'):r for r in root.findall('m:sheetData/m:row',NS)}
            for ref,value in values.items():
                row=rows[re.search(r'\d+$',ref)[0]]
                old=next((c for c in row if c.get('r')==ref),None)
                cell=ET.Element(tag('c'),r=ref)
                if old is not None:
                    if old.get('s') is not None: cell.set('s',old.get('s'))
                    row.replace(old,cell)
                else: row.append(cell)
                if isinstance(value,str) and value.startswith('='):
                    ET.SubElement(cell,tag('f')).text=value[1:]
                elif isinstance(value,str):
                    cell.set('t','inlineStr'); ET.SubElement(ET.SubElement(cell,tag('is')),tag('t')).text=value
                elif value is not None: ET.SubElement(cell,tag('v')).text=str(value)
                def col(c):
                    n=0
                    for ch in re.match('[A-Z]+',c.get('r'))[0]: n=n*26+ord(ch)-64
                    return n
                row[:]=sorted(row,key=col)
            changed[paths[name]]=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
        calc=wb.find('m:calcPr',NS)
        if calc is None: calc=ET.SubElement(wb,tag('calcPr'))
        calc.set('calcMode','auto'); calc.set('fullCalcOnLoad','1'); calc.set('forceFullCalc','1')
        changed['xl/workbook.xml']=ET.tostring(wb,xml_declaration=True,encoding='UTF-8',standalone=True)
        removed=set()
        if 'xl/calcChain.xml' in src.namelist():
            removed.add('xl/calcChain.xml')
            for part in ('xl/_rels/workbook.xml.rels','[Content_Types].xml'):
                tree=ET.fromstring(src.read(part))
                for element in list(tree):
                    if element.get('Type','').endswith('/calcChain') or element.get('PartName')=='/xl/calcChain.xml': tree.remove(element)
                changed[part]=ET.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
        def save(path):
            with ZipFile(path,'w') as dst:
                for info in src.infolist():
                    if info.filename not in removed: dst.writestr(copy(info),changed[info.filename] if info.filename in changed else src.read(info.filename))
        save(temporary)
        book=Book(temporary)
        for name,values in patches.items():
            root=ET.fromstring(changed[paths[name]])
            cells={c.get('r'):c for c in root.findall('.//m:c',NS)}
            for ref,value in values.items():
                if isinstance(value,str) and value.startswith('='):
                    try:
                        number=book.value(name,ref)
                    except MissingInput:
                        if not allow_missing: raise
                        cells[ref].set('t','e')
                        ET.SubElement(cells[ref],tag('v')).text='#N/A'
                        continue
                    if number == '':
                        cells[ref].set('t','str')
                        ET.SubElement(cells[ref],tag('v')).text=''
                        continue
                    if not math.isfinite(number): raise ValueError(f'Valor no finito {name}!{ref}')
                    ET.SubElement(cells[ref],tag('v')).text=format(number,'.15g')
            changed[paths[name]]=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
        save(temporary)
        with ZipFile(temporary) as final:
            if final.testzip(): raise ValueError('XLSX inválido')
            for name in src.namelist():
                if name not in changed and name not in removed and src.read(name)!=final.read(name): raise ValueError('Parte no autorizada modificada')
            # Every cell outside the patch must remain semantically identical.
            for name,values in patches.items():
                before=ET.fromstring(src.read(paths[name])); after=ET.fromstring(final.read(paths[name]))
                for root in (before,after):
                    for c in root.findall('.//m:c',NS):
                        if c.get('r') in values: c.getparent().remove(c)
                if ET.tostring(before)!=ET.tostring(after): raise ValueError('Celdas fuera de alcance modificadas')
        temporary.replace(output)
    return {'parts_changed':list(changed),'parts_removed':list(removed),'out_of_scope_preserved':True,'formula_caches':True}
