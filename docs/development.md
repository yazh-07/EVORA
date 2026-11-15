# Developing EVORA

EVORA uses Python/FastAPI, React/TypeScript, SQLite, and Go launchers. Dependency versions are pinned in `requirements.txt`, `frontend/package.json`, and the lockfile. Runtime versions are recorded in `backend/.python-version` and `frontend/package.json`.

## Setup

From the repository root, create a Python 3.14 environment and install the dependencies:

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
npm --prefix frontend ci
npm --prefix frontend run build
```

On Windows, use `py -3.14 -m venv .venv` and activate `.venv\Scripts\Activate.ps1` in PowerShell. Dependency installation downloads the pinned public English text model. See [backend setup](../backend/README.md) for runtime checks and graph configuration.

Run the local workstation with a development database and evidence folder:

```sh
python -m backend.run --database storage/dev/cases.sqlite3 --storage storage/dev/evidence --port 8000
```

Open `http://127.0.0.1:8000` and create a local administrator account. Keep real evidence and credentials out of development fixtures and commits.

For frontend development, run `npm --prefix frontend run dev`. The frontend reads `EVORA_API_BASE_URL` at build/start time; set it to your loopback backend address when serving them separately. With a configured external Neo4j instance and private `.env`, `./scripts/run-local.sh` runs runtime checks, builds the UI, and starts the workstation.

## Tests

```sh
node scripts/bundle-openapi.mjs specs/openapi.yaml /tmp/evora-openapi.json frontend
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -v
npm --prefix frontend run check:api
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

On Windows, use a path under `$env:TEMP` for the contract bundle and set `$env:EVORA_CONTRACT_BUNDLE` before running Python tests. Live Neo4j tests require a disposable instance and explicit opt-in with `EVORA_NEO4J_INTEGRATION=1`. Browser tests use Playwright and a disposable workstation; follow the setup comments in the relevant `frontend/test` script.

For launchers and update transactions:

```sh
go test -C desktop ./internal/patcher ./cmd/updater
# Linux launcher and real update/rollback coverage:
python -m unittest backend.tests.test_linux_updates
```

## Packaging

The [release workflow](../.github/workflows/release.yml) builds the frontend and frozen backend, tests each platform, and packages the installers and incremental update files. See [incremental updates](incremental-updates.md) for the file inventory and rollback protocol, and [Windows icons](../desktop/ICONS.md) for executable resources.

## Project references

- [Backend components](../backend/README.md)
- [Architecture](ARCHITECTURE.md)
- [API contract](../specs/openapi.yaml) and [contract policies](CONTRACTS.md)
- [Design system](../DESIGN.md)

Changes should preserve source provenance, case access controls, and published analysis history. Use synthetic or publicly permitted data in tests and screenshots.
