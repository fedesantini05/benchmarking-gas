"""Bind readable downloads only when byte-identical to an already reviewed source."""
import hashlib
import json
from pathlib import Path
import re

from ecosystem.sources import company_folder


def bind_reports(company,data_root,outputs_root):
    folder=Path(outputs_root)/company_folder(company)
    if not folder.exists(): return {}
    config=json.loads((Path(data_root)/'config/local'/f'{company["id"]}.json').read_text(encoding='utf-8-sig'))
    result={}
    for year,expected in config['report_sha256'].items():
        matches=[]
        for path in folder.glob('*.pdf'):
            if ' - Resumen ejecutivo - ' in path.name: continue
            if not re.search(r' - '+re.escape(year)+r'(?: - version \d+)?\.pdf$',path.name): continue
            if not path.resolve().is_relative_to(folder.resolve()): raise ValueError('Descarga fuera de carpeta autorizada')
            with path.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual!=expected:
                raise ValueError(f'{year}: descarga distinta del caso revisado; requiere nueva revisión, no se usa silenciosamente el archivo anterior')
            matches.append(path.resolve())
        if matches: result[year]=str(sorted(matches)[0])
    return result
