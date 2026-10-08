"""Regenerate from original inputs, never copy an approved Excel as output."""
import hashlib
import json
from pathlib import Path
import tempfile
import re
from lxml import etree as ET
from zipfile import ZipFile


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_cell_update(before, after, ref, rule):
    """Replace only one exact inline-text change; all other bytes stay strict."""
    if not re.fullmatch(r'O[1-9][0-9]*', ref):
        raise ValueError('La excepción sólo admite celdas de Fuente (O)')
    pattern=rb'<c\b(?=[^>]*\br="'+ref.encode()+rb'")[^>]*>.*?</c>'
    old_cells=list(re.finditer(pattern,before,re.S)); new_cells=list(re.finditer(pattern,after,re.S))
    if len(old_cells)!=1 or len(new_cells)!=1: return after,False
    old_cell=old_cells[0].group(); new_cell=new_cells[0].group()
    text_pattern=rb'(<t(?:\s[^>]*)?>)(.*?)(</t>)'
    old_text=list(re.finditer(text_pattern,old_cell,re.S)); new_text=list(re.finditer(text_pattern,new_cell,re.S))
    if len(old_text)!=1 or len(new_text)!=1: return after,False
    parser=ET.XMLParser(resolve_entities=False,no_network=True)
    for cell,expected in ((old_cell,rule['before']),(new_cell,rule['after'])):
        root=ET.fromstring(cell,parser)
        if root.get('t')!='inlineStr' or root.find('f') is not None: return after,False
        if root.findtext('is/t')!=expected: return after,False
    def without_text(cell,match):
        return cell[:match.start(2)]+cell[match.end(2):]
    if without_text(old_cell,old_text[0])!=without_text(new_cell,new_text[0]): return after,False
    match=new_cells[0]
    return after[:match.start()]+old_cell+after[match.end():],True


def efigas_source_updates(reference, original_reports, reports, expected_hashes, records):
    """Derive exact citation changes only after verifying identical approved PDFs."""
    for year in original_reports:
        if sha256(original_reports[year])!=expected_hashes[year] or sha256(reports[year])!=expected_hashes[year]:
            raise ValueError('Cambio de contenido en fuente; requiere revisión')
    if {str(r['year']) for r in records}!=set(original_reports) or len(records)!=len(original_reports):
        raise ValueError('Períodos de evidencia incompletos')
    for record in records:
        year=str(record['year'])
        if Path(record['file']).resolve()!=Path(reports[year]).resolve() or record['sha256']!=expected_hashes[year]:
            raise ValueError('Evidencia no corresponde a la fuente aprobada')
    from spanish_cases.efigas import ER, BP
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    result={}
    with ZipFile(reference) as archive:
        parser=ET.XMLParser(resolve_entities=False,no_network=True)
        rels={r.get('Id'):r.get('Target') for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'),parser)}
        wb=ET.fromstring(archive.read('xl/workbook.xml'),parser)
        for sheet in wb.findall('m:sheets/m:sheet',ns):
            name=sheet.get('name')
            if name not in (ER,BP): continue
            target=rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')].lstrip('/')
            part=target if target.startswith('xl/') else 'xl/'+target
            def citation(paths):
                return ' | '.join(f'{r["year"]}: {Path(paths[str(r["year"]) ]).name}; PDF p. {r["er_page"] if name==ER else r["bp_page"]}; millones COP.' for r in records)
            old_text=citation(original_reports); new_text=citation(reports)
            if old_text==new_text: continue
            root=ET.fromstring(archive.read(part),parser)
            for cell in root.findall('.//m:sheetData/m:row/m:c',ns):
                ref=cell.get('r','')
                if not re.fullmatch(r'O[0-9]+',ref): continue
                row=int(ref[1:])
                if not (2<=row<=57 if name==ER else 2<=row<=32 and row!=22): continue
                if cell.get('t')=='inlineStr' and cell.findtext('m:is/m:t',namespaces=ns)==old_text:
                    result.setdefault(part,{})[ref]={'before':old_text,'after':new_text}
    return result


def compare_packages(reference, candidate, allowed_source_updates=None):
    """Compare every uncompressed XLSX part, including formulas/caches/styles.

    ZIP timestamps/compression are irrelevant; no workbook part is excluded.
    This is stricter than equal totals and does not assert native Excel behavior.
    """
    with ZipFile(reference) as old, ZipFile(candidate) as new:
        for archive in (old,new):
            if archive.testzip():
                raise ValueError('ZIP dañado')
            if len(archive.namelist())!=len(set(archive.namelist())):
                raise ValueError('Partes ZIP duplicadas')
        before=set(old.namelist()); after=set(new.namelist())
        differences=set(before ^ after); accepted=[]
        for part in sorted(before & after):
            old_bytes=old.read(part); new_bytes=new.read(part)
            if old_bytes==new_bytes: continue
            if part.startswith('xl/worksheets/') and part.endswith('.xml'):
                for ref,rule in (allowed_source_updates or {}).get(part,{}).items():
                    new_bytes,changed=_source_cell_update(old_bytes,new_bytes,ref,rule)
                    if changed: accepted.append({'part':part,'cell':ref,'reason':'SOURCE_FILENAME_ONLY_IDENTICAL_REPORT_SHA256'})
            if old_bytes!=new_bytes: differences.add(part)
        differences=sorted(differences)
    return {'status':'PASS' if not differences else 'DIFFERENCE',
            'parts_compared':len(before | after),'different_parts':differences,
            'accepted_source_updates':accepted}


def assert_inputs(config):
    """A changed approval, template or annual PDF must require a new review."""
    inputs=[('reference',config['reference'],config['reference_sha256']),
            ('template',config['template'],config['template_sha256'])]
    if set(config['reports'])!=set(config['report_sha256']):
        raise ValueError('Períodos/hash incompletos')
    inputs.extend((year,path,config['report_sha256'][year]) for year,path in config['reports'].items())
    for name,path,expected in inputs:
        if sha256(path)!=expected:
            raise ValueError(f'Cambió el archivo {name}; requiere revisión. No se actualiza la aprobación automáticamente.')


def verify_approved(company,config):
    from run_company import generate_pilot, validate_pilot_config
    validate_pilot_config(company,config)
    assert_inputs(config)
    folder=Path(config['output_dir']); folder.mkdir(parents=True,exist_ok=True)
    # Unique folder; original approved Excel and previous checks remain untouched.
    with tempfile.TemporaryDirectory(prefix=f'verify-{company}-',dir=folder) as temporary:
        candidate=Path(temporary)/'regenerated.xlsx'
        audit=generate_pilot(company,config,candidate)
        comparison=compare_packages(config['reference'],candidate)
        report={'company':company,'status':comparison['status'],
                'approval':'Usuario confirma Ecogas y Efigas el 2026-10-07',
                'reference':config['reference'],'reference_sha256':sha256(config['reference']),
                'comparison':comparison,'generation':'ORIGINAL_TEMPLATE_AND_REPORTS_NOT_REFERENCE_COPY',
                'accounting_checks':audit['checks'],
                'preservation':audit.get('preservation',audit.get('writer_checks')),
                'limitations':audit.get('limitations',[]),
                'native_excel_check':'NOT_RUN',
                'glossary':'Reviewed labels; no automatic learning or classification of a new company'}
    # Retain the evidence, not duplicate approved workbooks.
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix=f'{company}-',
                                     dir=folder,encoding='utf-8',delete=False) as handle:
        report['report']=handle.name
        json.dump(report,handle,ensure_ascii=False,indent=2)
    return report
