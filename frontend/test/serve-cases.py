"""U02 local synthetic integration server; not a production entry point.

Real FastAPI/SQLite/processing/analysis producers; synthetic identities/data.
U05D uses the existing transactional Neo4j double, not a live graph service.
The static mount serves the built UI on the API origin without changing CORS.
"""
import argparse
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import uvicorn
from starlette.staticfiles import StaticFiles
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend import analysis
from backend.tests.test_analysis import GraphDouble

# Test-only factory: preserve real analysis/publication logic and SQLite outputs.
# No claim of live Neo4j acceptance (I01 retains that gate).
_graph = GraphDouble()
analysis.Neo4jGraphDatabase = lambda: _graph

parser = argparse.ArgumentParser()
parser.add_argument('--database', required=True)
parser.add_argument('--port', type=int, default=0)
args = parser.parse_args()
app = create_app(args.database, storage_dir=Path(args.database).resolve().parent / 'evidence', token_verifier=SyntheticTokenVerifier({
    'u02-synthetic-one': 'investigator-1',
    'u02-synthetic-two': 'investigator-2',
    'u02-synthetic-empty': 'investigator-2',
}))
# Explicitly local-only test/demo deployment, with no-store response headers.
@app.middleware('http')
async def no_store(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response

app.mount('/', StaticFiles(directory=Path(__file__).resolve().parents[1] / 'dist', html=True), name='u02-demo')
sock = socket.socket()
sock.bind(('127.0.0.1', args.port))
print(f'U02_URL=http://127.0.0.1:{sock.getsockname()[1]}', flush=True)
uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False)).run(sockets=[sock])
