"""Batch of approved cases; output status is never hidden by partial success."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import html

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pilot_adapters import COMPANIES,validate,generate
from run_company import resolve_config
from spanish_cases.regression import assert_inputs,compare_packages,efigas_source_updates
from cloud.data_bundle import unpack


def select_companies(value):
    result=list(COMPANIES) if value.strip().lower()=='todas' else [s.strip() for s in value.split(',')]
    if not result or len(result)>len(COMPANIES) or len(set(result))!=len(result) or any(s not in COMPANIES for s in result):
        raise ValueError('Empresas no habilitadas o duplicadas')
    return result


def run(companies,data,output,mode,report_overrides=None):
    if mode not in ('verificar','generar'): raise ValueError('Acción no habilitada')
    if output.exists(): raise FileExistsError('Carpeta de resultados existente')
    output.mkdir(parents=True)
    records=[]
    for company in companies:
        item={'company':company,'status':'FAILED','native_excel_check':'NOT_RUN'}
        case_dir=output/company
        try:
            config=resolve_config(json.loads((data/'config/local'/f'{company}.json').read_text(encoding='utf-8-sig')),root=data)
            overrides=(report_overrides or {}).get(company,{})
            original_reports=dict(config['reports'])
            if any(year not in config['reports'] for year in overrides): raise ValueError('No se autorizan períodos nuevos por sustitución de fuentes')
            config['reports'].update({year:str(Path(path).resolve()) for year,path in overrides.items()})
            validate(company,config)
            for p in [config['template'],config['reference']]:
                if not Path(p).resolve().is_relative_to(data.resolve()): raise ValueError('Fuente fuera del paquete')
            for year,p in config['reports'].items():
                if not Path(p).resolve().is_relative_to(data.resolve()) and year not in overrides:
                    raise ValueError('Fuente fuera del paquete sin vinculación autorizada')
            assert_inputs(config)
            item['input_sources']={year:{'path':path,'origin':'MATCHING_LOCAL_DOWNLOAD' if year in overrides else 'APPROVED_LOCAL_PACKAGE',
                                         'sha256':config.get('report_sha256',{}).get(year)} for year,path in config['reports'].items()}
            with tempfile.TemporaryDirectory(prefix=f'{company}-',dir=output) as temporary:
                workbook=Path(temporary)/f'{company}.xlsx'
                audit=generate(company,config,workbook)
                updates=efigas_source_updates(config['reference'],original_reports,config['reports'],
                                              config['report_sha256'],audit['records']) if company=='efigas' and overrides else None
                comparison=compare_packages(config['reference'],workbook,allowed_source_updates=updates)
                item.update(status=comparison['status'],comparison=comparison,years=sorted(config['reports']),
                            accounting_checks=audit['checks'],limitations=audit.get('limitations',[]),
                            data_completeness='PARTIAL' if company=='efigas' else 'REVIEWED_CASE')
                if mode=='generar' and comparison['status']=='PASS':
                    import shutil
                    case_dir.mkdir()
                    shutil.copyfile(workbook,case_dir/workbook.name)
            case_dir.mkdir(exist_ok=True)
        except Exception as error:
            # Continue other cases but fail the aggregate workflow; no failed Excel is delivered.
            item['error']=f'{type(error).__name__}: {error}'
            case_dir.mkdir(exist_ok=True)
        (case_dir/'control.json').write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
        records.append(item)
    summary={'status':'PASS' if all(r['status']=='PASS' for r in records) else 'FAILED',
             'mode':mode,'cases':records,'commit':os.getenv('GITHUB_SHA','LOCAL_TEST'),
             'run_id':os.getenv('GITHUB_RUN_ID','LOCAL_TEST'),'native_excel_check':'NOT_RUN'}
    (output/'resumen.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=''.join('<tr><td>'+html.escape(r['company'])+'</td><td>'+html.escape(r['status'])+'</td><td>'+html.escape(r.get('error','Datos parciales observados' if r.get('data_completeness')=='PARTIAL' else 'Caso revisado'))+'</td></tr>' for r in records)
    document='<html lang="es"><meta charset="utf-8"><title>Controles de benchmarking</title><body><h1>Resultado: '+summary['status']+'</h1><table><tr><th>Empresa</th><th>Reproducción</th><th>Observación</th></tr>'+rows+'</table><p>PASS indica reproducción del caso aprobado. No certifica años nuevos ni Excel de escritorio.</p></body></html>'
    (output/'resumen.html').write_text(document,encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write('## Benchmarking: '+summary['status']+'\n\n'+ '\n'.join(f'- {r["company"]}: {r["status"]}' for r in records)+'\n\nExcel de escritorio: no verificado.\n')
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--companies',default='todas')
    parser.add_argument('--mode',choices=['generar','verificar'],default='verificar')
    parser.add_argument('--archive',required=True,type=Path)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    companies=select_companies(args.companies)
    with tempfile.TemporaryDirectory(prefix='benchmarking-data-') as temporary:
        data=Path(temporary)/'inputs'
        unpack(args.archive,data,args.sha256)
        summary=run(companies,data,args.output,args.mode)
    print(json.dumps({'status':summary['status'],'companies':[r['company'] for r in summary['cases']]}))
    raise SystemExit(0 if summary['status']=='PASS' else 1)


if __name__=='__main__': main()
