"""Small local menu for the two approved 2023-2025 pilot cases."""
from datetime import datetime
import json
from pathlib import Path
import sys

from run_company import ROOT, resolve_config, generate_pilot
from spanish_cases.regression import assert_inputs, verify_approved


def load_case(company):
    if company not in ('ecogas_cuyo','efigas'):
        raise ValueError('Empresa fuera de esta etapa')
    path=ROOT/'config/local'/f'{company}.json'
    return resolve_config(json.loads(path.read_text(encoding='utf-8-sig')))


def main():
    print('Benchmarking local, sin IA\n1. Ecogas Cuyo\n2. Efigas\n0. Salir')
    selection=input('Empresa: ').strip()
    if selection=='0': return
    if selection not in ('1','2'): raise ValueError('Selección no válida')
    company={'1':'ecogas_cuyo','2':'efigas'}[selection]
    print('Períodos revisados: 2023, 2024 y 2025. No admite nuevos años todavía.')
    print('1. Verificar contra la planilla aprobada\n2. Generar una copia nueva\n0. Salir')
    action=input('Acción: ').strip()
    if action=='0': return
    if action not in ('1','2'): raise ValueError('Selección no válida')
    config=load_case(company)
    if action=='1':
        report=verify_approved(company,config)
        print('Verificación:',report['status'],'\nInforme:',report['report'])
        if report['status']!='PASS': raise ValueError('La reproducción difiere de la aprobada')
    else:
        assert_inputs(config)
        folder=Path(config['output_dir'])/'copias'; folder.mkdir(parents=True,exist_ok=True)
        output=folder/f'{company}-2023-2025-{datetime.now():%Y%m%d-%H%M%S-%f}.xlsx'
        generate_pilot(company,config,output)
        print('Copia nueva:',output,'\nOriginales y versión aprobada conservados.')


if __name__=='__main__':
    try: main()
    except (ValueError,KeyError,OSError) as error:
        print('No se completó:',error,file=sys.stderr)
        raise SystemExit(1)
