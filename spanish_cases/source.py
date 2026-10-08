"""Deterministic label-based reader for Spanish disclosed financial tables."""
import json
from pathlib import Path
import re
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
NUMBER=r'\(?-?\d[\d.,]*\)?|(?<!\w)[—–-](?!\w)'

def normalize(text):
    text=''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')
    return re.sub(r'[^a-z0-9]','',text)

def amount(text):
    if text in ('-','—','–'): return 0
    sign=-1 if text.startswith(('(','-')) else 1
    return sign*int(re.sub(r'[^0-9]','',text))

class Source:
    def __init__(self,company,year,*,pages=None):
        self.company=company; self.year=year; self.evidence=[]
        self.pages=pages if pages is not None else json.loads((ROOT/'cache/new_cases'/f'{company}_{year}.json').read_text(encoding='utf-8'))

    def row(self,label,pages,*,count=2,first=False,occurrence=0):
        candidates=[]
        for page in pages:
            lines=self.pages[page-1].splitlines()
            for index,line in enumerate(lines):
                joined=line
                for following in range(4):
                    if following: joined+=' '+lines[index+following]
                    norm=normalize(joined)
                    if norm.startswith(normalize(label)):
                        # Locate the suffix by its amount-bearing line. Note IDs
                        # are discarded by selecting the final disclosed columns.
                        suffix=joined
                        tokens=re.findall(NUMBER,suffix)
                        if len(tokens)>=count:
                            if first:
                                # Management tables have two values then a variation.
                                selected=tokens[:count]
                            else: selected=tokens[-count:]
                            candidates.append({'value':[amount(t) for t in selected],
                                               'page':page,'label':label,'source_line':joined})
                            break
                    if index+following+1>=len(lines): break
        if not candidates or occurrence>=len(candidates):
            raise ValueError(f'{self.company} {self.year}: falta fila {label} en {pages}')
        result=candidates[occurrence]
        self.evidence.append(result)
        return result['value']

    def v(self,label,pages,**kwargs): return self.row(label,pages,**kwargs)[0]
