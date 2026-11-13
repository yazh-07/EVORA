#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
if [[ ! -x .venv/bin/python ]]; then
  echo 'Create .venv with Python 3.14.8, 3.14.9 or 3.14.10, then install requirements.txt.' >&2
  exit 1
fi
.venv/bin/python -m backend.check_runtime
npm --prefix frontend run build
exec .venv/bin/python -m backend.run "$@"
