# Main repository update — 7 November 2026

The updated application and reliability repairs from `evora-clean` have been brought into `/home/whale2186/nemesis-shared/EVORA/git`. The repository remains on `feat/windows-installer` at HEAD `f7f3344fd75ac13758865515786c8e356fb9c783`; all changes are uncommitted. No branch switch, staging, commit, push, merge, remote change or release was performed.

## Integration

- Transferred current ChatGPT authorization/inference, shared or separate image models, provider discovery/error handling, image/video processing, source graph and image-preflight repairs, Q&A validation, motion/UI changes, regression tests and validation documentation.
- Reviewed overlapping files against the clean checkout's base and the existing main-repo versions. The main repo was initially clean. The existing desktop Go code, Python launcher, installer scripts, PyInstaller specification and GitHub workflows are unchanged.
- Preserved the main repo's full coordination helper instead of replacing it with the smaller recovered helper from the other checkout. Its current contract validator retains the approved workstation/media operations and exact contract/provenance checks.
- Preserved the main-only legacy planning/CLI/ledger tests. Their removed planning documents and original 27-operation contract are explicitly historical fixtures recovered from commit `114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb`. CLI tests exercise the current helper in explicit historical mode; current product contract tests still use `specs/openapi.yaml`. No obsolete active project roadmap was recreated and no legacy mutation checks were removed.
- Updated both feature-document entry points, with the appropriate relative links, so the README-linked document includes the current features.
- Rebuilt the frontend using scratch dependencies and installed the fresh local build. The main repo's `frontend/node_modules` directory and the tracked symlink in `evora-clean/frontend/node_modules` were not replaced, deleted or populated.

The 258 backend/frontend source files matched the tested clean-worktree update before the additional offline-settings fix described below. After that fix, main and its tested scratch copy match; the older checkout is left untouched.

## Additional defect found during verification

The main repo's local-account browser check caught a real initial-render mismatch. With no stored `offline_mode` value yet, the settings dialog treated the draft as offline for the switch/text, but `!draft.offline_mode` still rendered the cloud-provider options. The options disappeared after settings loaded, making the browser assertion timing-dependent.

`SettingsModal.tsx` now renders cloud/ChatGPT options only when `offline_mode === false`, matching the existing switch/request semantics. This fixes the initial flash without waiting longer or weakening the browser assertion. A focused component regression covers missing, true and false offline flags, and the full local-account browser workflow now passes.

## Verification

Tests used an exact source copy at `/tmp/evora-main-sync/project`, with scratch frontend dependencies. Backend tests also ran against a disposable real Neo4j service at loopback port 17687, initialized before the suites. The user's persistent graph and databases were not used for test cases.

```sh
export EVORA_TEST_PYTHON=/home/whale2186/.hermes/cache/scratch/test_neo4j_venv/bin/python
export EVORA_QA_MODEL=''
export EVORA_NEO4J_INTEGRATION=1
export NEO4J_URI=bolt://127.0.0.1:17687
export NEO4J_PASSWORD=disposable-main-sync-validation

bash /tmp/evora-main-sync/project/scripts/verify-full-scope.sh
npm --prefix /tmp/evora-main-sync/project/frontend test
npm --prefix /tmp/evora-main-sync/project/frontend run build
python3 /tmp/evora-main-sync/run_integrations.py

EVORA_PLAYWRIGHT_MODULE=/tmp/evora-feature-qa/tools/node_modules/playwright/index.mjs EVORA_CHROME_PATH=/opt/google/chrome/chrome EVORA_BROWSER_BASE_URL=http://127.0.0.1:18919 EVORA_BROWSER_ARTIFACTS=/tmp/evora-main-sync/launcher-browser-artifacts node /tmp/evora-main-sync/project/frontend/test/workspace-browser.integration.mjs

"$EVORA_TEST_PYTHON" launcher.py --help
"$EVORA_TEST_PYTHON" scripts/verify_coordination.py fixtures/planning/legacy-coordination/openapi.json --historical-planning --planning-root fixtures/planning/legacy-coordination
git diff --check
git status --short
```

The full-scope gate regenerates the OpenAPI bundle from `specs/openapi.yaml`, then checks every script test, the complete backend/frontend suites, full-modality, detector-feedback, deeper-processing, the production build and source diff whitespace. The sequential runner additionally runs cases, adaptive, review-override, qa-tracer, local-auth-browser, image-understanding, video-understanding and chatgpt-connection, with the correct Python interpreter and explicit Playwright/Chrome paths.

| Check | Final result |
| --- | --- |
| Backend, real Neo4j enabled | 908 tests, 92.458 s, OK, no skips |
| Main repo script suite | 124 tests, OK, including its additional legacy checks |
| Complete frontend after the settings fix | 382 passed, no skips |
| API declaration freshness, TypeScript and production build | Passed |
| Full-scope verification gate | Exit 0; frontend was 381 before the additional settings regression, then rechecked as 382 with a fresh build |
| Eleven sequential API/browser integrations after the settings fix | All exit 0 |
| Full workspace browser through the actual Python launcher | Exit 0: original hash verification, timeline/source/graph views, reviews, report content/export, mobile layout, themes and logout |
| Python launcher help/startup | Passed; a disposable launcher workstation served the browser acceptance flow |
| Explicit historical coordination CLI | Exit 0; reports planning-only scope |
| Installer/desktop/workflow preservation | No changes in `desktop/`, `installer/`, `launcher.py`, `evora.spec` or `.github/` |
| Final whitespace, status, branch and dependency inspection | Passed; original dependency paths and HEAD/branch preserved |

Initial local-auth-browser failure is superseded by the explicit-online visibility fix and successful final run. No known failing check remains in this transfer. These checks do not build or validate a Windows installer; packaging files are preserved. The model/OCR accuracy limits documented in [the reliability repair](reliability-fixes-2026-11-07.md) still apply. No additional live paid-provider accuracy claim is made by these protocol/browser tests.

Logs and disposable test artifacts are under `/tmp/evora-main-sync/`; they may not persist across sessions. The original overlapping source files were backed up there before transfer.

## Running application and existing data

The running app now imports the main repository's backend and serves its fresh frontend at `http://127.0.0.1:8000`. Post-restart checks confirm that local setup is complete, online mode is enabled and the existing ChatGPT connection remains present/authorized. The selected provider/model remains ChatGPT with `gpt-6.1-sol`, shared for images.

The existing runtime data was deliberately **not moved or copied**. This server continues to use:

- Database: `/home/whale2186/nemesis-shared/EVORA/evora-clean/storage/evora.sqlite3`
- Original evidence vault: `/home/whale2186/nemesis-shared/EVORA/evora-clean/storage/evidence`
- Protected ChatGPT credentials: the companion private directory beside that database
- Existing persistent workstation Neo4j service on loopback port 7687

Those paths must be retained or explicitly migrated before removing the older checkout. A manual launch using the main repo's default database path would select a different workstation database; use the existing database/storage paths above to retain these accounts and cases. Runtime model preferences still follow the existing settings behavior documented in [ChatGPT connection setup](chatgpt-connection.md).

The disposable launcher/test database service is stopped after verification. The real app and its persistent graph remain running. No private database, original evidence, OAuth token or local credential/configuration file was added to the repository transfer.
