"""Explicit entities and capabilities; names never select an adapter implicitly."""
import csv
import json
from pathlib import Path
import re
import unicodedata


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))


def load(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('schema_version')!=1: raise ValueError('Versión de catálogo no admitida')
    ids=set()
    for company in data['companies']:
        identity=company['id']
        if not re.fullmatch(r'[a-z0-9_]{1,80}',identity) or identity in ids or not company['name'].strip():
            raise ValueError('Identidad inválida o repetida')
        ids.add(identity)
    return data


def select(data,country='',query='',sector='',module='',regulator='',vertical=''):
    return [c for c in data['companies'] if
            (not country or c.get('country')==country.upper()) and
            (not query or normalize(query) in normalize(c['name']+' '+c['id'])) and
            (not sector or c.get('sector')==sector) and
            (not module or c.get('module')==module) and
            (not regulator or c.get('regulator')==regulator) and
            (not vertical or c.get('vertical_integration')==vertical)]


def import_csv(path):
    """Stage names only; never invent country, source, entity scope or adapter."""
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or 'nombre' not in reader.fieldnames:
            raise ValueError('CSV requiere columna nombre; pais es opcional (código ISO)')
        companies=[]; seen=set()
        for row in reader:
            name=row['nombre'].strip(); country=(row.get('pais') or '').strip().upper()
            if not name or normalize(name) in seen: raise ValueError('Nombre vacío o duplicado: revisar lista')
            if country and not re.fullmatch(r'[A-Z]{2}',country): raise ValueError('País debe ser código ISO de dos letras o vacío')
            seen.add(normalize(name))
            companies.append({'id':f'pending_{len(companies)+1:04d}','name':name,'country':country,
                              'status':'IDENTITY_REVIEW','reviewed_years':[],'sources':[]})
    if not companies: raise ValueError('Lista vacía')
    return {'schema_version':1,'companies':companies}


def import_roster(path,seed):
    """Preserve user labels; seed capabilities attach by explicitly reviewed alias."""
    countries={'Australia':'AU','Brasil':'BR','Peru':'PE','Argentina':'AR',
               'Uruguay':'UY','Colombia':'CO','Chile':'CL','Mexico':'MX','EEUU':'US'}
    aliases={'Compagas':'compagas','Ecogas Cuyo':'ecogas_cuyo','Efigas':'efigas',
             'Potigas':'potigas','SGC':'sgc'}
    capabilities={c['id']:c for c in seed['companies']}
    result=[]; seen=set()
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            alias=row['Empresa'].removesuffix(' (p)').strip()
            identity=aliases.get(alias,re.sub(r'[^a-z0-9]+','_',normalize(alias)).strip('_'))
            if identity in seen: raise ValueError('Identidad repetida: revisar lista')
            seen.add(identity)
            country=countries.get(row['PaisDirecto'])
            if not country: raise ValueError('País no mapeado')
            website=row['PaginaWeb'].replace('\\.','.').strip()
            if not website.startswith('https://'): website='https://'+website
            source=capabilities.get(identity,{})
            result.append({'id':identity,'alias':alias,'name':row['NombreCompleto'],
                           'country':country,'country_label':row['PaisDirecto'],
                           'website':website,'regulator':row['Regulador'],
                           'vertical_integration':row['IntegracionVertical'],
                           'sector':'gas_natural','module':'financial',
                           'metadata_origin':'USER_SUPPLIED_2026-10-08_NOT_INDEPENDENTLY_VERIFIED',
                           'status':'REVIEWED_CASE' if source else 'ONBOARDING_PENDING',
                           'reviewed_years':source.get('reviewed_years',[]),
                           'generator_entity':source.get('name'),
                           'sources':source.get('sources',[])})
    return {'schema_version':1,'companies':result}
