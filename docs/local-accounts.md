# Offline local accounts

Start the built workstation from the repository root:

```sh
python -m pip install -r requirements.txt
npm --prefix frontend run build
python -m backend.run
```

Install dependencies and download the chosen local AI model before disconnecting the workstation. Normal account setup, login, password changes, recovery, evidence review, and account administration do not require internet access. The launcher binds to `127.0.0.1:8000`, serves the interface and API on one origin, and enforces offline model settings. `--database`, `--storage`, and `--port` select another local installation. Store the database and evidence directory on a protected local disk.

## First use

Open the application and create the first administrator with a username, display name, and password of at least 12 characters. There is no default account or password. Save the one-time recovery code outside the workstation before entering the workspace. Usernames contain letters, numbers, periods, underscores, and hyphens; matching is case-insensitive. Accounts, Argon2id password hashes, session hashes, and account audit events live in the application's SQLite database.

Administrators can see existing cases, including cases created before local accounts were introduced. Earlier case memberships and audit identities remain intact. Creating an administrator does not reassign previous evidence or rewrite audit history.

## Account management

Use **Account** in the header. Administrators can create accounts, change roles, disable accounts, reset passwords, and assign or revoke individual case memberships. A new account or administrative password reset requires the user to choose a new password at their next login. Keep at least one active administrator; the server prevents disabling or demoting the last one.

- Administrators manage accounts and all cases, including workstation/provider settings.
- Investigators can create cases and work on cases to which they have access.
- Reviewers can read assigned cases. The server rejects mutations, apart from their own password changes, session activity, and logout.

Administrative changes revoke that user's existing sessions. Case membership is checked on every case request. Original evidence, review, processing, and other case audit events use the logged-in user's stable account ID. Account actions have a separate append-only audit history visible to administrators (latest 100 events).

## Sessions and recovery

Sessions use a random opaque HttpOnly, SameSite=Strict cookie. The database stores only its SHA-256 digest. Cookies are also Secure when served over HTTPS. The bundled launcher uses HTTP on loopback only. Browser requests use same-origin credentials and a required custom mutation header; the server checks Origin, Fetch Metadata, and allowed hosts. Production local mode does not accept bearer tokens. The explicitly injected synthetic verifier remains available only for legacy test harnesses.

Inactivity locks the interface after 30 minutes. Background data refreshes do not extend the server's idle window; user activity updates it through the authenticated activity endpoint. Sessions also have a 12-hour absolute limit. Logout, recovery, account disabling, role changes, and password resets invalidate stored sessions. Tabs in the same browser profile receive session-change notifications; authenticated responses also identify the account so the client can discard a response after cookie replacement.

Forgotten investigator/reviewer passwords are reset by an administrator. The setup administrator can use **Forgot password?** with the recovery code. Recovery revokes every session for that account and returns a replacement code; the old code stops working. Recovery codes cannot be retrieved from the database in their original form. Losing both the password and recovery code requires a documented workstation administration procedure; there is no secret backdoor or email reset.

Login, recovery, setup, and password verification are throttled using persisted attempt counters. The last active administrator is protected against accidental lockout through account administration.

## Offline models

Local deployments default to offline mode. Cloud API keys are ignored at startup, cloud providers are rejected, and Ollama URLs must use `localhost` or a literal loopback IP address. Model-list requests obey the same restriction. Ollama itself and the desired models must already be installed. A direct `create_app(..., offline_mode=False)` deployment is a deliberate developer configuration, outside the offline launcher.

Application login does not encrypt evidence or defend against an operating-system administrator who can modify the application/database. Use filesystem permissions and disk encryption for stored evidence and backups. Back up the complete SQLite database consistently along with the evidence directory.

## Verification

```sh
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```

The browser acceptance creates a disposable database and local server, then checks setup, account creation, case assignment, forced password change, reviewer permissions, cookie restoration, cross-tab logout, recovery, and offline settings:

```sh
node frontend/test/local-auth-browser.integration.mjs
```

It requires Playwright and a browser already installed. `EVORA_TEST_PYTHON`, `EVORA_PLAYWRIGHT_MODULE`, and `EVORA_CHROME_PATH` can select existing installations. Its synthetic credentials are test fixtures, never runtime defaults.
