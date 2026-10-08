"""Copy a recorded download to readable company folders; preserve old evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from ecosystem.catalog import load
from ecosystem.sources import company_folder,store_document


def rehome(job_id,catalog_path):
    if not re.fullmatch(r'[a-f0-9]{32}',job_id): raise ValueError('Identificador de ejecución inválido')
    companies={c['id']:c for c in load(catalog_path)['companies']}
    source_folder=ROOT/'outputs/platform'/job_id
    record=json.loads((source_folder/'job.json').read_text(encoding='utf-8'))
    changes=[]
    for case in record['cases']:
        company=companies[case['company']]
        for document in case.get('downloads',[]):
            if document['status']!='DOWNLOADED_PENDING_REVIEW': continue
            old=source_folder/company['id']/document['filename']
            if not old.resolve().is_relative_to(source_folder.resolve()): raise ValueError('Fuente fuera de la ejecución')
            content=old.read_bytes()
            if hashlib.sha256(content).hexdigest()!=document['sha256']: raise ValueError('Documento alterado')
            destination=ROOT/'outputs'/company_folder(company)
            stored=store_document(content,document,company,destination)
            changes.append({'company':company['id'],'original_path':str(old),**stored,
                            'status':'DOWNLOADED_PENDING_REVIEW','source_url':document['url']})
    audit=ROOT/'outputs/platform'/f'reubicacion-{job_id}.json'
    with audit.open('x',encoding='utf-8') as f:
        json.dump({'originals_preserved':True,'files':changes},f,ensure_ascii=False,indent=2)
    return changes


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('job_id')
    parser.add_argument('--catalog',type=Path,default=ROOT/'config/catalog.json')
    args=parser.parse_args()
    print(json.dumps(rehome(args.job_id,args.catalog),ensure_ascii=False,indent=2))
