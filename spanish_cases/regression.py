"""Regenerate from original inputs, never copy an approved Excel as output."""
import hashlib
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_packages(reference, candidate):
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
        differences=sorted((before ^ after) | {p for p in before & after if old.read(p)!=new.read(p)})
    return {'status':'PASS' if not differences else 'DIFFERENCE',
            'parts_compared':len(before | after),'different_parts':differences}


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
