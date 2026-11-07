# Password-unlocked database encryption

EVORA's local account sign-in also unlocks its SQLite case database. No separate database password or key-setting screen is required.

New workstation setup encrypts the database before returning the administrator account and recovery code. An existing plaintext database migrates after the next successful administrator sign-in. EVORA then displays a replacement recovery code; save it because the previous code is replaced. Restarting the backend discards its in-memory key and requires password entry again, even when the browser still has an old session cookie.

Password changes, administrator password resets and account recovery update the password protection for the database key. New accounts receive their own password-protected key entry. Existing additional accounts must sign in once while the migrated database is unlocked, or have their password reset by an administrator, before they can unlock it after a restart. Existing account roles and case permissions remain enforced by the application.

Signing out ends the account session. The database key stays in backend memory until EVORA shuts down so background processing and other signed-in users can continue. Fully close EVORA to lock the database at the cryptographic level.

## Implementation and recovery

The database uses [SQLCipher](https://www.zetetic.net/sqlcipher/sqlcipher-api/) through the pinned `sqlcipher3==0.6.5` runtime dependency. SQLCipher protects database pages and its write-ahead journal. Temporary SQL storage is kept in memory. Native packaging includes the SQLCipher Python extension.

A random 256-bit database key is wrapped with AES-GCM using an Argon2id-derived key from each account password. Independent salts and nonces are generated for every wrapping operation. Associated data binds the wrapper to the database, account and credential purpose. Passwords and plaintext database keys are never stored in the key file. The existing recovery code has a separate protected key wrapper.

Wrapped entries live beside the database in `<database>.keys.json`, with private file permissions (owner-only permissions on POSIX, current-user ACL on Windows). Do not delete or separate this file from the database. Back up the database and its matching key file together while EVORA is fully stopped, along with the original evidence directory. A password or recovery code alone cannot reconstruct a deleted key file. Losing both password and recovery access makes encrypted records inaccessible.

Password updates stage a new wrapper before committing the account change, retaining the prior wrappers through interruption. The encrypted account row remains authoritative: an uncommitted password cannot unlock the database. Successful completion removes obsolete wrappers. Password changes do not invalidate copies of older key files or previously decrypted keys; this is storage encryption, not retroactive revocation of copied data.

Migration checkpoints the old database, exports an encrypted copy, checks SQLCipher and SQLite integrity, compares schema objects and every table's records, persists wrapped keys, and atomically replaces the original. It creates no plaintext backup. A failed migration leaves the original database readable for retry and cleans the temporary encrypted copy. A process lease prevents two backend processes from opening the same workstation database. Normal SQLite readers remain concurrent with processing writes.

The app can serve its sign-in screen while the database is locked. Case access, account reads and old browser sessions remain unavailable until a valid password or recovery code unlocks the database. Failed locked-state logins are rate-limited in memory; unlocked-state authentication retains the existing persistent throttle table. Database schema initialization and queued analysis recovery wait until unlocking.

## Scope

This change encrypts the local SQLite database: accounts, case metadata, extracted observations, stored processing/analysis outputs, notes, reviews and model report provenance. Original evidence files, downloaded reports, existing backups, ChatGPT credential files and the separate Neo4j projection store are outside this encryption scope. It does not provide per-case cryptographic separation between accounts sharing the database. Hosted model sharing controls continue to apply.

## Verification

Regenerate the OpenAPI bundle before backend and contract tests. Use the project Python environment and the pinned frontend dependencies:

```sh
node scripts/bundle-openapi.mjs specs/openapi.yaml /tmp/evora-openapi.json frontend
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts
npm --prefix frontend test
npm --prefix frontend run build
```

Set `EVORA_TEST_PYTHON` to the project interpreter and `EVORA_CONTRACT_BUNDLE` to the regenerated bundle for the full-modality, detector-feedback and deeper-processing integration scripts in `frontend/test`. Browser checks additionally require Playwright and Chrome; set `EVORA_PLAYWRIGHT_MODULE` and `EVORA_CHROME_PATH` when they are installed outside the default locations.

Frozen builds can be checked with `python scripts/smoke_release.py <executable>` and `python scripts/smoke_standalone.py <executable>`. The standalone smoke test covers encrypted storage, CSV processing, analysis without Neo4j, report generation with a model protocol double, preserved source bytes and password unlock after restart. Model protocol doubles do not establish live account or model availability.
