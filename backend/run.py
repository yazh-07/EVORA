"""Run the offline workstation on loopback: python -m backend.run."""
import argparse
import sys
from pathlib import Path

import uvicorn
from starlette.staticfiles import StaticFiles
from backend.app import create_app


def main():
    parser = argparse.ArgumentParser(description='EVORA offline forensic workstation')
    parser.add_argument('--database', default='storage/evora.sqlite3')
    parser.add_argument('--storage', default='storage/evidence')
    parser.add_argument('--online', action='store_true', help='Start with hosted providers enabled; local accounts and loopback hosting remain in use')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host',choices=['127.0.0.1','0.0.0.0'])
    args = parser.parse_args()
    from backend.runtime_settings import load
    preferences=load(args.database)
    host=args.host or ('0.0.0.0' if preferences.network_available else '127.0.0.1')
    if '--port' not in sys.argv[1:]:args.port=preferences.port
    frontend = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
    if not (frontend / 'index.html').is_file():
        parser.error('Build the interface first: npm --prefix frontend run build')
    app = create_app(args.database, storage_dir=args.storage, offline_mode=False if args.online else None,network_available=host=='0.0.0.0',listen_port=args.port)
    app.mount('/', StaticFiles(directory=frontend, html=True), name='workstation')
    uvicorn.run(app, host=host, port=args.port, access_log=False)


if __name__ == '__main__':
    main()
