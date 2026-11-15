"""Package the verified Windows application, including its desktop and updater."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.incremental import parse_manifest


def build(source, destination):
    source = Path(source)
    encoded = (source / 'EVORA-Update-Windows-x64.json').read_bytes()
    manifest = parse_manifest(encoded, target='windows-x64')
    bundle = source / 'EVORA-Update-Windows-x64.bin'
    if bundle.stat().st_size != manifest['bundle_size']:
        raise ValueError('Update bundle size does not match manifest')
    with bundle.open('rb') as objects, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in manifest['files']:
            objects.seek(item['offset'])
            compressed = objects.read(item['compressed_size'])
            if hashlib.sha256(compressed).hexdigest() != item['compressed_sha256']:
                raise ValueError('Invalid compressed file: ' + item['path'])
            checksum = hashlib.sha256()
            size = 0
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as original, archive.open('evora/' + item['path'], 'w', force_zip64=True) as output:
                while chunk := original.read(1024 * 1024):
                    size += len(chunk)
                    if size > item['size']:
                        raise ValueError('File exceeds expected size: ' + item['path'])
                    checksum.update(chunk)
                    output.write(chunk)
            if size != item['size'] or checksum.hexdigest() != item['sha256']:
                raise ValueError('Invalid application file: ' + item['path'])
        archive.writestr('evora/evora-install.json', encoded)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='dist')
    parser.add_argument('--output', default='dist/evora-windows-x64.zip')
    args = parser.parse_args()
    build(args.source, args.output)
