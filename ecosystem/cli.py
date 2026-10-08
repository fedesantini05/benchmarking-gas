"""Local ecosystem entrypoint; no corporate deployment or external writes."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ecosystem.catalog import load,select,import_csv
from ecosystem.jobs import execute


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--catalog',type=Path,default=ROOT/'config/catalog.json')
    commands=parser.add_subparsers(dest='command',required=True)
    listing=commands.add_parser('list')
    listing.add_argument('--country',default=''); listing.add_argument('--query',default='')
    importing=commands.add_parser('import-csv')
    importing.add_argument('file',type=Path); importing.add_argument('--output',required=True,type=Path)
    job=commands.add_parser('run')
    job.add_argument('--companies',required=True); job.add_argument('--years',required=True)
    job.add_argument('--action',choices=['discover','generate'],default='discover')
    job.add_argument('--download',action='store_true'); job.add_argument('--data-root',type=Path)
    job.add_argument('--storage',type=Path,default=ROOT/'outputs/platform')
    server=commands.add_parser('serve'); server.add_argument('--port',type=int,default=8765)
    server.add_argument('--data-root',type=Path); server.add_argument('--storage',type=Path,default=ROOT/'outputs/platform')
    args=parser.parse_args()
    if args.command=='import-csv':
        data=import_csv(args.file); args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
        print('Catálogo candidato creado; requiere revisión, no habilita procesamiento.'); return
    if args.command=='list': result=select(load(args.catalog),country=args.country,query=args.query)
    elif args.command=='run':
        result=execute(load(args.catalog),{'companies':args.companies.split(','),
                       'years':[int(y) for y in args.years.split(',')],
                       'action':args.action,'download':args.download},args.storage,args.data_root)
    else:
        from ecosystem.server import serve
        serve(args.catalog,args.storage,args.data_root,args.port); return
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
