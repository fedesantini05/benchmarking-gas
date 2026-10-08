"""Local execution history and strict reviewed-case gate, without auto-approval."""
from datetime import datetime,timezone
import json
from pathlib import Path
import uuid

from cloud.run_batch import run as generate_batch
from ecosystem.sources import discover,download,company_folder


def now(): return datetime.now(timezone.utc).isoformat()


def execute(catalog,request,storage,data_root=None,discoverer=discover,downloader=download,generator=generate_batch):
    ids=request.get('companies',[]); years=request.get('years',[]); action=request.get('action')
    known={c['id']:c for c in catalog['companies']}
    if not ids or len(ids)>20 or len(set(ids))!=len(ids) or any(i not in known for i in ids):
        raise ValueError('Seleccionar de 1 a 20 empresas del catálogo sin duplicados')
    if not years or len(years)>20 or any(type(y)!=int or not 1900<=y<=2100 for y in years) or len(set(years))!=len(years):
        raise ValueError('Períodos inválidos')
    if action not in ('discover','generate'): raise ValueError('Acción no admitida')
    job_id=uuid.uuid4().hex; folder=Path(storage)/job_id; folder.mkdir(parents=True)
    result={'id':job_id,'status':'RUNNING','started':now(),'request':request,'cases':[]}
    path=folder/'job.json'
    def save(): path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    for identity in ids:
        company=known[identity]
        try:
            if action=='discover':
                item=discoverer(company,years)
                if request.get('download'):
                    downloads=Path(storage).resolve().parent/company_folder(company)
                    downloads.mkdir(parents=True,exist_ok=True)
                    records=[]
                    for candidate in item['candidates'][:10]:
                        try: records.append(downloader(candidate,company,downloads))
                        except Exception as error: records.append(dict(candidate,status='DOWNLOAD_ERROR',error=str(error)))
                    item['downloads']=records
                    item['download_directory']=str(downloads)
                    item['download_limit']=10
            elif set(years)!=set(company.get('reviewed_years',[])):
                item={'company':identity,'status':'REVIEW_REQUIRED',
                      'reason':'El generador actual requiere el conjunto completo de períodos revisados. No acepta años nuevos ni actualiza aprobaciones.'}
            elif data_root is None:
                item={'company':identity,'status':'INPUTS_REQUIRED','reason':'Documentos locales autorizados no configurados'}
            else:
                output=folder/identity
                batch=generator([identity],Path(data_root),output,'generar')
                item=dict(batch['cases'][0])
                if item['status']=='PASS':
                    item['status']='PARTIAL' if item.get('data_completeness')=='PARTIAL' else 'COMPLETED'
                item['output_directory']=identity
        except Exception as error:
            item={'company':identity,'status':'FAILED','error':f'{type(error).__name__}: {error}'}
        result['cases'].append(item); save()
    result['status']='COMPLETED' if all(c['status']=='COMPLETED' for c in result['cases']) else 'REVIEW_REQUIRED'
    result['finished']=now(); save()
    return result
