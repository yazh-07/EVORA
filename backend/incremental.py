"""Versioned application manifests and bounded, verified byte-range downloads."""
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time

MANIFEST='EVORA-Update-Windows-x64.json'
BUNDLE='EVORA-Update-Windows-x64.bin'
INSTALLED='evora-install.json'
MAX_SIZE=2*1024**3
MAX_MANIFEST=8*1024**2

class IncrementalError(ValueError):pass
class RangeUnavailable(IncrementalError):pass

def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()

def safe_name(name):
    if not isinstance(name,str) or len(name)>240 or '\\' in name or ':' in name or '\x00' in name:raise IncrementalError('Invalid update path.')
    parts=PurePosixPath(name).parts
    if not parts or '/'.join(parts)!=name or any(p in ('.','..') or p.rstrip(' .')!=p or re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',p,re.I) for p in parts):raise IncrementalError('Invalid update path.')
    if name not in ('EVORA.exe','icon.ico','evora-updater.exe') and not (len(parts)>1 and parts[0]=='backend'):raise IncrementalError('Invalid update destination.')
    if len(parts)>1 and parts[1].lower() in ('storage','evidence','vault','evidence_vault','updates'):raise IncrementalError('User data cannot be updated.')
    if Path(name).suffix.lower() in ('.db','.sqlite','.sqlite3'):raise IncrementalError('Databases cannot be updated.')
    return name

def safe_path(root,name):
    path=Path(root)/safe_name(name)
    for parent in [path,*path.parents]:
        if parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()):raise IncrementalError('Linked update paths are not supported.')
        if parent==Path(root):break
    if not path.resolve().is_relative_to(Path(root).resolve()):raise IncrementalError('Invalid update destination.')
    return path

def parse_manifest(data,version=None):
    if len(data)>MAX_MANIFEST:raise IncrementalError('Update manifest is too large.')
    body=json.loads(data)
    if not isinstance(body,dict):raise IncrementalError('Invalid update manifest.')
    if body.get('format')!=1 or body.get('platform')!='windows-x64' or not re.fullmatch(r'\d+\.\d+\.\d+',body.get('version','')) or (version and body['version']!=version):raise IncrementalError('Unsupported update manifest.')
    files=body.get('files');seen=set();total=0
    if not isinstance(files,list) or not 1<=len(files)<=20000 or type(body.get('bundle_size')) is not int or not 0<body['bundle_size']<=MAX_SIZE:raise IncrementalError('Invalid update file list.')
    for item in files:
        if not isinstance(item,dict):raise IncrementalError('Invalid update file entry.')
        name=safe_name(item.get('path'));key=name.casefold()
        if key in seen:raise IncrementalError('Duplicate update path.')
        seen.add(key)
        for field in ('sha256','compressed_sha256'):
            if not isinstance(item.get(field),str) or not re.fullmatch('[a-f0-9]{64}',item[field]):raise IncrementalError('Invalid update checksum.')
        for field in ('size','offset','compressed_size'):
            if type(item.get(field)) is not int or not 0<=item[field]<=MAX_SIZE:raise IncrementalError('Invalid update size.')
        if not item['compressed_size'] or item['offset']+item['compressed_size']>body['bundle_size']:raise IncrementalError('Invalid update range.')
        total+=item['size']
    if total>4*MAX_SIZE or not {'evora.exe','evora-updater.exe','backend/evora.exe'}<=seen:raise IncrementalError('Incomplete application update.')
    return body

def plan_files(root,previous,current):
    old={f['path'].casefold():f for f in previous['files']};new={f['path'].casefold():f for f in current['files']}
    changed=[];deleted=[]
    for key,item in new.items():
        path=safe_path(root,item['path'])
        before=digest(path) if path.is_file() else None
        if path.exists() and not path.is_file():raise IncrementalError('Update destination is not a file.')
        if before==item['sha256']:continue
        if before is not None and key not in old:raise IncrementalError('An unmanaged file needs the full installer.')
        changed.append({**item,'before':before})
    for key,item in old.items():
        if key in new:continue
        path=safe_path(root,item['path'])
        if path.exists():
            if not path.is_file() or digest(path)!=item['sha256']:raise IncrementalError('A modified application file needs the full installer.')
            deleted.append(item)
    return changed,deleted

def stage_download(http,remote,root,files,bundle_url,bundle_size,stop,progress):
    root=Path(root);objects=root/'objects';objects.mkdir(parents=True,exist_ok=True,mode=0o700)
    if objects.is_symlink() or (hasattr(objects,'is_junction') and objects.is_junction()):raise IncrementalError('Invalid download cache.')
    received=0;completed=set();started=time.monotonic()
    for item in files:
        if stop.is_set():return False
        target=safe_path(root/'payload',item['path']);target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_file() and target.stat().st_size==item['size'] and digest(target)==item['sha256']:
            if item['compressed_sha256'] not in completed:received+=item['compressed_size'];completed.add(item['compressed_sha256'])
            progress(received);continue
        blob=objects/(item['compressed_sha256']+'.gz')
        if blob.is_symlink():raise IncrementalError('Invalid download cache.')
        if blob.exists() and blob.stat().st_size>item['compressed_size']:blob.unlink()
        offset=blob.stat().st_size if blob.exists() else 0
        if offset<item['compressed_size']:
            start=item['offset']+offset;end=item['offset']+item['compressed_size']-1
            with remote(http,bundle_url,{'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'}) as response:
                if response.status_code==200:raise RangeUnavailable('This server requires the full installer. Select Download installer to continue.')
                if response.status_code!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{bundle_size}':raise IncrementalError('Invalid incremental download range.')
                with blob.open('ab') as output:
                    for chunk in response.iter_bytes():
                        if time.monotonic()-started>7200:raise IncrementalError('Download timed out. Retry to resume.')
                        if stop.is_set():return False
                        offset+=len(chunk)
                        if offset>item['compressed_size']:raise IncrementalError('Update segment exceeded its expected size.')
                        output.write(chunk);progress(received+offset)
                    output.flush();os.fsync(output.fileno())
        if blob.stat().st_size!=item['compressed_size']:raise IncrementalError('Download interrupted. Retry to resume.')
        if digest(blob)!=item['compressed_sha256']:
            blob.unlink();raise IncrementalError('Update segment verification failed. Retry the download.')
        temporary=target.with_name(target.name+'.evora-part')
        if temporary.is_symlink():raise IncrementalError('Invalid staging path.')
        length=0;checksum=hashlib.sha256()
        try:
            with gzip.open(blob,'rb') as source,temporary.open('wb') as output:
                while chunk:=source.read(1024*1024):
                    if stop.is_set():return False
                    length+=len(chunk)
                    if length>item['size']:raise IncrementalError('Update file exceeded its expected size.')
                    checksum.update(chunk);output.write(chunk)
                output.flush();os.fsync(output.fileno())
            if length!=item['size'] or checksum.hexdigest()!=item['sha256']:raise IncrementalError('Update file verification failed.')
            os.replace(temporary,target)
        finally:
            temporary.unlink(missing_ok=True)
        if item['compressed_sha256'] not in completed:received+=item['compressed_size'];completed.add(item['compressed_sha256'])
        progress(received)
    return True
