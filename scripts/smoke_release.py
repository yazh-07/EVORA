"""Verify a newly frozen executable using an isolated local workstation."""
import json
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen

binary = Path(sys.argv[1]).resolve()
subprocess.run([str(binary), '--help'], check=True, timeout=60)
manifest = binary.parent / '_internal/backend/models/text_ner.json'
worker = subprocess.run([str(binary), '-m', 'backend.text_ner_worker', str(manifest)],
    input='{"lines": []}\n', text=True, capture_output=True, timeout=120)
assert worker.returncode == 0, worker.stderr[-2000:]
assert json.loads(worker.stdout)['ok'] is True, worker.stdout
with TemporaryDirectory(prefix='evora-release-smoke-') as directory:
    root = Path(directory)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with (root / 'server.log').open('w+') as log:
        child = subprocess.Popen([str(binary), '--no-browser', '--port', str(port),
            '--database', str(root / 'case.sqlite3'), '--storage', str(root / 'evidence')],
            stdout=log, stderr=log)
        try:
            for attempt in range(120):
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/v1/auth/status', timeout=2) as response:
                        assert json.load(response) == {'setup_required': True, 'offline_mode': True}
                    with urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if child.poll() is not None or attempt == 119:
                        log.seek(0)
                        raise RuntimeError(log.read()[-4000:])
                    time.sleep(.5)
        finally:
            child.terminate()
            child.wait(timeout=20)
print('PASS frozen worker/model integrity, isolated startup, local auth and frontend')
