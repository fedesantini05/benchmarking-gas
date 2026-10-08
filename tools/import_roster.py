"""Stage the supplied participant list locally, never publish or approve sources."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from ecosystem.catalog import load,import_roster

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('csv',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(); result=import_roster(args.csv,load(ROOT/'config/catalog.json'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'companies':len(result['companies']),'countries':sorted({c['country'] for c in result['companies']}),'published':False}))
