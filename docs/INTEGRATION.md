# Integration checks

Use disposable accounts, databases, evidence vaults and graph partitions for integration runs. The root README documents dependency setup, API bundling, unit tests and the production build.

## Application checks

```sh
npm --prefix frontend run test:desk-browser
npm --prefix frontend run test:results-media
npm --prefix frontend run test:map-views
```

These browser checks include explicit synthetic transports; read each script's header for its scope. `frontend/test/results-live.integration.mjs` requires `EVORA_DISPOSABLE_BACKEND=1` and refuses a workstation with existing accounts.

## Graph runtime

```sh
EVORA_GRAPH_TEST_RUNTIME=/path/to/staged/runtime .venv/bin/python -m unittest backend.tests.test_managed_graph -v
```

The runtime directory contains `java/`, `neo4j/lib/` and `classes/GraphHost.class`. These tests cover authenticated startup, persistence, ownership locking and shutdown.

## Native packages

Windows packaging stages the pinned graph runtime through `scripts/prepare_windows_graph.py`, invoked by `evora.spec`. Release workflows build the frontend, freeze the backend and run:

```sh
python scripts/smoke_release.py dist/evora/evora.exe
```

The frozen smoke checks executable resources, local extraction, certificate loading, account setup and frontend serving. With a bundled graph it also processes synthetic GPS data, completes analysis and reads graph results before shutdown.

Provider-account authorization and model accuracy require separate testing with permitted data; synthetic protocol checks do not establish either.
