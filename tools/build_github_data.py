"""Prepare a local data-only archive. This tool never uploads anything."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cloud.data_bundle import approved_member
from pilot_adapters import COMPANIES,validate
from run_company import resolve_config
from spanish_cases.regression import assert_inputs


def build(source,output):
    source=source.resolve(); output=output.resolve()
    if output.exists(): raise FileExistsError('No se sobrescribe un paquete existente')
    members={}
    for company in COMPANIES:
        config_path=source/'config/local'/f'{company}.json'
        raw=json.loads(config_path.read_text(encoding='utf-8-sig'))
        config=resolve_config(raw,root=source)
        validate(company,config); assert_inputs(config)
        for path in (config_path,Path(config['template']),Path(config['reference']),
                     *(Path(p) for p in config['reports'].values())):
            path=path.resolve()
            if not path.is_relative_to(source): raise ValueError('Datos fuera del paquete revisado')
            name=path.relative_to(source).as_posix()
            if not approved_member(name): raise ValueError(f'Archivo no permitido: {name}')
            members[name]=path
    manifest={'schema_version':1,'purpose':'LOCAL_PREPARATION_PENDING_COMPANY_UPLOAD_APPROVAL',
              'companies':list(COMPANIES),'files':{name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in sorted(members.items())}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,'x',compression=ZIP_DEFLATED) as z:
        for name,path in sorted(members.items()): z.write(path,name)
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    evidence={'archive':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
              'data_files':len(members),'bytes':output.stat().st_size,'uploaded':False}
    output.with_suffix('.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.source,args.output)))
