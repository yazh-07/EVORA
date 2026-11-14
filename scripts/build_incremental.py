"""Build a full application manifest and independently compressed file objects."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.incremental import MANIFEST,BUNDLE,digest,parse_manifest,safe_name
from backend.version import APP_VERSION

def build(backend,desktop,helper,icon,output,version):
    sources={'EVORA.exe':Path(desktop),'evora-updater.exe':Path(helper),'icon.ico':Path(icon)}
    for file in sorted(Path(backend).rglob('*')):
        if file.is_symlink():raise ValueError('Application bundle contains a symbolic link')
        if file.is_file():sources['backend/'+file.relative_to(backend).as_posix()]=file
    for file in Path(backend,'_internal').glob('*.dll'):
        if file.name.startswith(('python3','vcruntime140','msvcp140')):sources['backend/'+file.name]=file
    output=Path(output);output.mkdir(parents=True,exist_ok=True);files=[];objects={}
    with (output/BUNDLE).open('wb') as bundle:
        for name,file in sorted(sources.items()):
            safe_name(name);checksum=digest(file)
            if checksum not in objects:
                compressed=gzip.compress(file.read_bytes(),compresslevel=9,mtime=0)
                objects[checksum]=dict(offset=bundle.tell(),compressed_size=len(compressed),compressed_sha256=hashlib.sha256(compressed).hexdigest())
                bundle.write(compressed)
            files.append(dict(path=name,size=file.stat().st_size,sha256=checksum,**objects[checksum]))
        size=bundle.tell()
    body=dict(format=1,platform='windows-x64',version=version,bundle_size=size,files=files)
    encoded=json.dumps(body,sort_keys=True,separators=(',',':')).encode();parse_manifest(encoded,version)
    (output/MANIFEST).write_bytes(encoded)
    return body

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backend',default='dist/evora');p.add_argument('--desktop',default='desktop/evora-workstation.exe');p.add_argument('--helper',default='desktop/evora-updater.exe');p.add_argument('--icon',default='desktop/icon.ico');p.add_argument('--output',default='dist');p.add_argument('--version',default=APP_VERSION)
    a=p.parse_args();build(a.backend,a.desktop,a.helper,a.icon,a.output,a.version)
