#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${EVORA_TEST_PYTHON:-python3}"
SOURCE_ROOT_DIR="$("$PYTHON" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().parents[1])' "${BASH_SOURCE[0]}")"
VERIFY_DIR="$(mktemp -d "${TMPDIR:-/tmp}/evora-verification.XXXXXX")"
trap 'rm -rf "$VERIFY_DIR"' EXIT
export EVORA_CONTRACT_BUNDLE="$VERIFY_DIR/openapi.json"
export EVORA_TEST_PYTHON="$PYTHON"

echo "=== EVORA Full-Scope Verification Gate (I09B) ==="

echo "1. Regenerating the contract bundle and validating all script regressions..."
node "$ROOT_DIR/scripts/bundle-openapi.mjs" "$ROOT_DIR/specs/openapi.yaml" "$EVORA_CONTRACT_BUNDLE" "$ROOT_DIR/frontend"
"$PYTHON" -m unittest discover -s "$ROOT_DIR/scripts" -p "test_*.py"

echo "2. Running complete backend test suite..."
"$PYTHON" -m unittest discover -s "$ROOT_DIR/backend/tests"

echo "3. Running frontend test suite..."
npm --prefix "$ROOT_DIR/frontend" run test

echo "4. Running full-modality integration tracer (I03B)..."
node "$ROOT_DIR/frontend/test/full-modality.integration.mjs"

echo "5. Running detector feedback priority tracer (I07)..."
node "$ROOT_DIR/frontend/test/detector-feedback.integration.mjs"

echo "6. Running deeper processing rerank tracer (I07B)..."
node "$ROOT_DIR/frontend/test/deeper-processing.integration.mjs"

echo "7. Running production build and API typechecks..."
npm --prefix "$ROOT_DIR/frontend" run build

echo "8. Checking diff whitespace..."
git -C "$SOURCE_ROOT_DIR" diff --check

echo "=== EVORA AUTOMATED VERIFICATION GATES PASSED ==="
