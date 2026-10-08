"""Shared execution of five reviewed pilots; no downloads or AI services."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
COMPANIES=('ecogas_cuyo','efigas','sgc','potigas','compagas')


def validate(company,config):
    if company not in COMPANIES: raise ValueError('Empresa no habilitada para ejecución por lote')
    expected={str(y) for y in range(2020,2026)} if company=='sgc' else {'2023','2024','2025'}
    if set(config['reports'])!=expected: raise ValueError('Períodos fuera del caso revisado')
    if company=='efigas' and config.get('missing_policy')!='PUBLISHED_TOTALS_WHEN_NO_BREAKDOWN':
        raise ValueError('Efigas: falta política aprobada de totales sin desglose')


def generate(company,config,output):
    validate(company,config)
    output=Path(output)
    if output.exists(): raise FileExistsError('No se sobrescribe una salida existente')
    if company=='ecogas_cuyo':
        from spanish_cases.reviewed_southern import build
        return build(company,template=Path(config['template']),
                     reports={int(y):p for y,p in config['reports'].items()},output=output)
    if company=='efigas':
        from spanish_cases.efigas import build
        return build(Path(config['template']),{int(y):p for y,p in config['reports'].items()},output)
    folder=ROOT/('sgc' if company=='sgc' else 'legacy')
    script=folder/('generar_planilla.py' if company=='sgc' else f'{company}_pipeline.py')
    normalized=dict(config,output_dir=str(output.parent.resolve()),output_filename=output.name)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='config-',dir=output.parent) as temporary:
        path=Path(temporary)/'company.json'
        path.write_text(json.dumps(normalized,ensure_ascii=False),encoding='utf-8')
        command=[sys.executable,str(script),'--config',str(path)]
        if company=='potigas':
            command=[sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from potigas_pipeline import run;run(sys.argv[2])',str(folder),str(path)]
        subprocess.run(command,cwd=ROOT,check=True)
    audit_path=output.parent/('generacion.audit.json' if company=='sgc' else f'{company}.audit.json')
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if audit.get('status')!='PASS': raise ValueError('Falla en controles del generador')
    return {'checks':audit.get('source_checks',audit.get('reconciliations',audit.get('reconciliation',[]))),
            'preservation':audit.get('package',{}),'limitations':audit.get('limitations',audit.get('warnings',[])),
            'original_audit':audit}
