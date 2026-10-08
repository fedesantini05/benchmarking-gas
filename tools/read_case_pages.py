import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('case')
ap.add_argument('year', type=int)
ap.add_argument('--pages')
ap.add_argument('--find')
args = ap.parse_args()
pages = json.loads((ROOT / 'cache/new_cases' / f'{args.case}_{args.year}.json').read_text(encoding='utf-8'))
if args.pages:
    for number in map(int, args.pages.split(',')):
        print(f'\n--- PDF page {number} ---\n{pages[number-1]}')
else:
    for number, page in enumerate(pages, 1):
        matches = [line.strip() for line in page.splitlines() if re.search(args.find, line, re.I)]
        if matches:
            print(number, ' | '.join(matches)[:350])
