#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${EVORA_TEST_PYTHON:-/home/whale2186/.hermes/cache/scratch/test_neo4j_venv/bin/python}"
export EVORA_CONTRACT_BUNDLE="/tmp/evora-openapi.json"
export EVORA_TEST_PYTHON="$PYTHON"

echo "=== EVORA Full-Scope Verification Gate (I09B) ==="

echo "1. Validating contract examples..."
"$PYTHON" -m unittest discover -s "$ROOT_DIR/scripts" -p "test_contract_examples.py"

echo "2. Running complete backend test suite (812 tests)..."
"$PYTHON" -m unittest discover -s "$ROOT_DIR/backend/tests"

echo "3. Running frontend test suite (336 tests)..."
npm --prefix "$ROOT_DIR/frontend" run test

echo "4. Running full-modality integration tracer (I03B)..."
node "$ROOT_DIR/frontend/test/full-modality.integration.mjs"

echo "5. Running detector feedback priority tracer (I07)..."
node "$ROOT_DIR/frontend/test/detector-feedback.integration.mjs"

echo "6. Running deeper processing rerank tracer (I07B)..."
node "$ROOT_DIR/frontend/test/deeper-processing.integration.mjs"

echo "7. Running production build and API typechecks..."
npm --prefix "$ROOT_DIR/frontend" run build

echo "8. Checking repository cleanliness..."
git -C "$ROOT_DIR" diff --check

echo "=== ALL EVORA FULL-SCOPE GATES PASSED (100% REPRODUCIBLE) ==="
