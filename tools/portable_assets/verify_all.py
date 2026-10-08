"""Unit tests, full regenerations and persistent local evidence."""
import json
from pathlib import Path
import subprocess
import sys

from menu import load_case
from spanish_cases.regression import verify_approved


def main():
    root=Path(__file__).resolve().parent
    tests=subprocess.run([sys.executable,'run_tests.py'],cwd=root)
    if tests.returncode: return tests.returncode
    reports=[]
    for company in ('ecogas_cuyo','efigas','sgc','potigas','compagas'):
        result=verify_approved(company,load_case(company))
        reports.append({'company':company,'status':result['status'],
                        'different_parts':result['comparison']['different_parts'],'report':result['report']})
        print(company,result['status'])
    status='PASS' if all(r['status']=='PASS' for r in reports) else 'DIFFERENCE'
    summary={'status':status,'python':sys.version,'cases':reports,'native_excel_check':'NOT_RUN',
             'meaning':'Reproducción de casos aprobados, no extracción universal ni aceptación en otra PC'}
    destination=root/'outputs/resultado_prueba.json'
    destination.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Resultado:',status,'\nInforme:',destination)
    return 0 if status=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
