"""Unpack data only. Never accept or execute code supplied in the data archive."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import stat
from zipfile import ZipFile

LIMIT=1024*1024*1024


def approved_member(name):
    p=PurePosixPath(name)
    if '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or name!=p.as_posix():
        return False
    reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if any(part.endswith((' ','.')) or part.split('.')[0].upper() in reserved for part in p.parts):
        return False
    if len(p.parts)==3 and p.parts[:2]==('config','local') and p.suffix=='.json': return True
    if len(p.parts)==3 and p.parts[:2]==('data','templates') and p.suffix=='.xlsx': return True
    if len(p.parts)==4 and p.parts[:2]==('data','reports') and p.suffix.lower()=='.pdf': return True
    if len(p.parts)==2 and p.parts[0]=='references' and p.suffix=='.xlsx': return True
    return False


def unpack(archive,destination,expected_sha256):
    archive=Path(archive); destination=Path(destination)
    if len(expected_sha256)!=64 or any(c not in '0123456789abcdef' for c in expected_sha256.lower()):
        raise ValueError('Se requiere SHA-256 del paquete de datos aprobado')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_sha256.lower():
        raise ValueError('El paquete de datos no coincide con el aprobado')
    if destination.exists(): raise FileExistsError('Destino existente; no se sobrescribe')
    with ZipFile(archive) as z:
        members=z.infolist()
        if len(members)>100 or sum(m.file_size for m in members)>LIMIT:
            raise ValueError('Paquete demasiado grande')
        if len({m.filename.casefold() for m in members})!=len(members): raise ValueError('Partes duplicadas')
        for m in members:
            if m.is_dir() or stat.S_ISLNK(m.external_attr>>16): raise ValueError('Directorios/enlaces no admitidos')
            if m.filename!='MANIFEST.json' and not approved_member(m.filename):
                raise ValueError('El paquete sólo puede contener datos; no código ni ejecutables')
        manifest=json.loads(z.read('MANIFEST.json'))
        if set(manifest['files'])!={m.filename for m in members if m.filename!='MANIFEST.json'}:
            raise ValueError('Manifest incompleto')
        for name,expected in manifest['files'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=expected: raise ValueError('Archivo alterado')
        destination.mkdir(parents=True)
        for m in members:
            target=destination/m.filename
            if not target.resolve().is_relative_to(destination.resolve()): raise ValueError('Ruta fuera del destino')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(z.read(m.filename))
