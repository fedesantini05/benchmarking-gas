"""Reviewed vocabulary lookup, not a universal accounting classifier."""
import json
from pathlib import Path


def labels(country,concept):
    glossary=json.loads(Path(__file__).with_name('glossary_ar_cl.json').read_text(encoding='utf-8'))
    return glossary[country][concept]


def efigas_label(concept,year):
    if year not in (2023,2024,2025):
        raise ValueError('Efigas: año no revisado')
    options=labels('Colombia',concept)
    if len(options)!=1:
        raise ValueError('Etiqueta ambigua: requiere revisar el adaptador')
    return options[0]
