"""EVORA Desktop Application Launcher.

Bundled entry point for standalone Windows and Linux binaries.
Starts the local offline backend server and opens the browser interface.
"""
import argparse
import os
import sys
import threading
import time
import webbrowser
from contextlib import ExitStack
from pathlib import Path

import uvicorn
from starlette.staticfiles import StaticFiles

# Determine bundle directory (PyInstaller sets _MEIPASS in frozen mode)
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
else:
    BUNDLE_DIR = Path(__file__).resolve().parent

if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))

from backend.app import create_app


def open_browser(url: str, delay_seconds: float = 1.0):
    """Open user's default browser after the server has initialized."""
    time.sleep(delay_seconds)
    try:
        webbrowser.open_new(url)
    except Exception as exc:
        print(f"[EVORA] Could not open default browser: {exc}")


def main():
    parser = argparse.ArgumentParser(
        description="EVORA — Forensic Evidence Fusion & Investigation Platform"
    )
    default_data_dir = Path.cwd() / "evora_data"
    parser.add_argument(
        "--database",
        default=str(default_data_dir / "cases.sqlite3"),
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--storage",
        default=str(default_data_dir / "evidence_vault"),
        help="Directory to store uploaded evidence binaries",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to serve the application on (default: 8000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically launch the web browser",
    )
    parser.add_argument('--graph-mode', choices=['auto', 'bundled', 'external'], default='auto')
    parser.add_argument('--graph-data', help='Private bundled graph data directory')
    parser.add_argument('--shutdown-file', help=argparse.SUPPRESS)
    parser.add_argument('--parent-pid', type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()

    frontend_dist = BUNDLE_DIR / "frontend" / "dist"
    if not (frontend_dist / "index.html").is_file():
        repo_dist = Path(__file__).resolve().parent / "frontend" / "dist"
        if (repo_dist / "index.html").is_file():
            frontend_dist = repo_dist
        else:
            sys.exit(
                "Error: Compiled frontend not found. Please run 'npm --prefix frontend run build' first."
            )

    db_path = Path(args.database).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    vault_path = Path(args.storage).resolve()
    vault_path.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  EVORA — Forensic Evidence Fusion Platform")
    print("=" * 60)
    print(f"  Interface & API : http://127.0.0.1:{args.port}")
    print(f"  Database        : {db_path}")
    print(f"  Evidence Vault  : {vault_path}")
    print("=" * 60)
    print("  Press Ctrl+C to stop the workstation server.\n")

    with ExitStack() as resources:
        runtime = BUNDLE_DIR / 'graph-runtime'
        bundled = args.graph_mode == 'bundled' or (args.graph_mode == 'auto' and
            (runtime.exists() or (os.name == 'nt' and getattr(sys, 'frozen', False))))
        if bundled:
            from backend.managed_graph import ManagedGraph
            graph_home = Path(args.graph_data) if args.graph_data else (
                Path(os.environ['LOCALAPPDATA']) / 'EVORA/graph' if os.name == 'nt' and os.environ.get('LOCALAPPDATA')
                else db_path.parent / 'graph')
            graph = ManagedGraph(runtime, graph_home, owner_pid=args.parent_pid or None)
            resources.callback(graph.close)
            os.environ.update(graph.start())
        app = create_app(str(db_path), storage_dir=str(vault_path))
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="workstation")

        if not args.no_browser:
            target_url = f"http://127.0.0.1:{args.port}"
            threading.Thread(target=open_browser, args=(target_url,), daemon=True).start()

        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, access_log=False))
        if args.shutdown_file or args.parent_pid:
            def watch_shutdown():
                from backend.process_owner import alive
                while not server.should_exit:
                    if (args.shutdown_file and Path(args.shutdown_file).exists()) or not alive(args.parent_pid):
                        server.should_exit = True
                        return
                    time.sleep(.25)
            threading.Thread(target=watch_shutdown, daemon=True).start()
        server.run()


if __name__ == "__main__":
    # Frozen child workers must re-enter this executable rather than argparse.
    if sys.argv[1:] == ['--check-oauth-tls']:
        import ssl
        from backend.chatgpt_connection import tls_context
        context = tls_context()
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        assert context.cert_store_stats()['x509_ca'] > 0
        print('OAuth TLS certificate verification ready')
    elif sys.argv[1:3] == ['-m', 'backend.text_ner_worker']:
        sys.argv = sys.argv[2:]
        from backend.text_ner_worker import run
        run()
    elif sys.argv[1:3] == ['-m', 'backend.video_speech_worker']:
        sys.argv = sys.argv[2:]
        from backend.video_speech_worker import main as speech_main
        speech_main()
    else:
        main()
