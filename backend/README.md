# Backend

FastAPI serves the authorized case APIs under `/api/v1`. SQLite stores accounts, evidence metadata, processing outputs, analysis snapshots and audit history. Original evidence bytes live in the configured vault. Neo4j stores rebuildable graph projections.

## Run from source

Create `.venv` with a supported pinned Python version and install `requirements.txt`. Configure Neo4j using the root `.env.example`, then run:

```sh
./scripts/run-local.sh
```

The script checks the text model and graph connection, builds the frontend and starts the workstation. It forwards `--database`, `--storage` and `--port` to the backend. For an API-only process with environment configuration already loaded:

```sh
.venv/bin/python -m backend.run --port 8000
```

## Components

- `app.py`: application lifecycle and routes.
- `local_auth.py`, `auth.py`: workstation sessions, roles and case access.
- `evidence.py`, `processing.py`, `parsers/`: intake and source extraction.
- `results.py`, `locations.py`: extraction results and geographic projections.
- `analysis.py`, `graph_projection.py`, `graph_db.py`: analysis and graph publication.
- `managed_graph.py`: packaged Windows graph lifecycle.
- `chatgpt_connection.py`: protected OAuth credentials and ChatGPT provider requests.

## Tests

Bundle `specs/openapi.yaml` as described in the root README, then run:

```sh
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json .venv/bin/python -m unittest discover -s backend/tests -v
```

Live graph tests require a disposable Neo4j configuration and explicit opt-in. Managed-runtime tests use `EVORA_GRAPH_TEST_RUNTIME` pointing to a staged Java/Neo4j runtime.

See [API contracts](../specs/openapi.yaml), [local accounts](../docs/local-accounts.md), [database encryption](../docs/database-encryption.md), [bundled graph](../docs/bundled-graph.md) and [model reports](../docs/model-reports.md).
