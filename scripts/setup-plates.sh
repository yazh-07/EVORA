#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -x .plate-venv/bin/python ]]; then uv venv --python python3.13 .plate-venv; fi
uv pip install --python .plate-venv/bin/python -r requirements-plates.txt
.plate-venv/bin/python -m backend.install_plate_models
