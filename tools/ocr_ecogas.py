"""Local OCR for scanned annual reports; no network or model calls."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--poppler', type=Path, required=True)
ap.add_argument('--tesseract', type=Path, required=True)
args = ap.parse_args()
inventory = json.loads((ROOT / 'cache/new_cases/inventory.json').read_text(encoding='utf-8'))

def process(job):
    year, pdf, page = job
    target = ROOT / 'cache/new_cases' / f'ocr_{year}'
    target.mkdir(parents=True, exist_ok=True)
    text = target / f'page_{page}.txt'
    if not text.is_file():
        prefix = target / f'page_{page}'
        subprocess.run([str(args.poppler), '-f', str(page), '-l', str(page), '-singlefile',
                        '-r', '150', '-png', str(pdf), str(prefix)], check=True, capture_output=True)
        env = dict(os.environ, OMP_THREAD_LIMIT='1')
        subprocess.run([str(args.tesseract), str(prefix.with_suffix('.png')), str(prefix),
                        '-l', 'eng', '--psm', '3'], env=env, check=True, capture_output=True)
    return year, page, text.read_text(encoding='utf-8')

jobs = [(r['year'], r['path'], p) for r in inventory['ecogas_cuyo']['reports']
        if r['year'] in (2024, 2025) for p in range(1, r['pages']+1)]
result = {2024: {}, 2025: {}}
with ThreadPoolExecutor(max_workers=4) as pool:
    for index, (year, page, text) in enumerate(pool.map(process, jobs), 1):
        result[year][page] = text
        if index % 20 == 0:
            print(f'OCR {index}/{len(jobs)}', flush=True)
for year, pages in result.items():
    (ROOT / 'cache/new_cases' / f'ecogas_cuyo_{year}.json').write_text(
        json.dumps([pages[p] for p in sorted(pages)], ensure_ascii=False), encoding='utf-8')
print('OCR completado; requiere conciliación y revisión visual de importes.', flush=True)
