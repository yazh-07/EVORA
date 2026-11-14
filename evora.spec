# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

model_data = collect_data_files('en_core_web_sm', include_py_files=True)
graph_data = []
if sys.platform == 'win32':
    import runpy
    builder = runpy.run_path(str(Path(SPECPATH) / 'scripts/prepare_windows_graph.py'))
    graph_data = [(str(builder['prepare']()), 'graph-runtime')]
for distribution in ('en-core-web-sm', 'spacy', 'thinc', 'numpy'):
    model_data += copy_metadata(distribution)

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('frontend/dist', 'frontend/dist'), ('specs/openapi.yaml', 'specs'), ('backend/models', 'backend/models'), ('backend/geodata', 'backend/geodata')] + model_data + graph_data,
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on', 'argon2', 'argon2.low_level', 'sqlcipher3', 'sqlcipher3.dbapi2', 'sqlcipher3._sqlite3'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'doctest', 'test', 'tests', 'curses',
              'torch', 'tensorflow', 'cupy', 'jax', 'matplotlib', 'pandas', 'IPython', 'jupyter'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='evora',
    icon=str(Path(SPECPATH) / 'desktop/icon.ico'),
    version=str(Path(SPECPATH) / 'desktop/backend-version.txt') if sys.platform == 'win32' else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=sys.platform != "win32",
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=sys.platform != "win32",
    upx=False,
    name='evora',
)
