"""Portable pilot entry: five reviewed company/year cases, not universal extraction."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
COMPANIES=('ecogas_cuyo','efigas','sgc','potigas','compagas')


def resolve_config(config,root=ROOT):
    result=dict(config)
    def absolute(value):
        p=Path(value)
        return str(p.resolve() if p.is_absolute() else (root/p).resolve())
    for key in ('template','reference','output_dir'):
        if result.get(key): result[key]=absolute(result[key])
    result['reports']={year:absolute(path) for year,path in config['reports'].items()}
    return result


def validate_pilot_config(company,config):
    if company not in COMPANIES: raise ValueError('Empresa fuera del paquete piloto')
    expected={str(y) for y in range(2020,2026)} if company=='sgc' else {'2023','2024','2025'}
    if set(config['reports'])!=expected:
        raise ValueError('Períodos fuera del caso revisado')
    if company=='efigas' and config.get('missing_policy')!='PUBLISHED_TOTALS_WHEN_NO_BREAKDOWN':
        raise ValueError('Efigas requiere su política aprobada de totales publicados')


def generate_pilot(company,config,output):
    validate_pilot_config(company,config)
    if company=='ecogas_cuyo':
        from spanish_cases.reviewed_southern import build
        return build(company,template=Path(config['template']),
                     reports={int(y):p for y,p in config['reports'].items()},output=output)
    if company in ('sgc','potigas','compagas'):
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
        return {'checks':audit.get('direct_source_checks',audit.get('reconciliations',audit.get('reconciliation',[]))),
                'preservation':audit.get('package',{}),'limitations':audit.get('limitations',audit.get('warnings',[]))}
    from spanish_cases.efigas import build
    return build(Path(config['template']),{int(y):p for y,p in config['reports'].items()},output)


def main():
    parser=argparse.ArgumentParser(description='Paquete piloto local, sin IA')
    parser.add_argument('company',choices=COMPANIES)
    parser.add_argument('--config',type=Path)
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--check',action='store_true')
    actions.add_argument('--verify-approved',action='store_true')
    args=parser.parse_args()
    config=resolve_config(json.loads((args.config or ROOT/'config/local'/f'{args.company}.json').read_text(encoding='utf-8-sig')))
    validate_pilot_config(args.company,config)
    from spanish_cases.regression import assert_inputs,verify_approved
    assert_inputs(config)
    if args.check:
        print('Archivos presentes y hashes correctos; no es una auditoría contable.')
        return
    if args.verify_approved:
        report=verify_approved(args.company,config)
        print(json.dumps(report,ensure_ascii=False))
        raise SystemExit(0 if report['status']=='PASS' else 1)
    output=Path(config['output_dir'])/config['output_filename']
    if output.exists() or output.resolve() in (Path(config['template']),Path(config['reference'])):
        parser.error('Salida existente o protegida: elegir nombre nuevo')
    generate_pilot(args.company,config,output)
    print('Generada:',output)


if __name__=='__main__': main()
