# Incremental updates

Installed Windows and Linux x86_64 workstations download only application files whose SHA-256 differs from the next release. Unchanged Python libraries, Java, and model assets are reused. This is a file-level update, so a changed executable is downloaded in full; it does not patch individual bytes within an executable. Older Linux packages, source runs, and unsupported architectures retain manual downloads until installed with the new Linux package.

The first installation containing this feature must come from a complete installer or Linux package. It adds `evora-updater.exe` and `evora-install.json`. Linux installs add `evora`, `evora-updater`, and the same inventory alongside the frozen backend. Later releases can update directly from any compatible installed version; intermediate releases are unnecessary.

## Release assets

The Windows release job builds the desktop and update helper, then runs:

```sh
python scripts/build_incremental.py
```

The script inventories exactly the application files installed by `installer/setup.iss`, including duplicated runtime DLLs. It writes:

- `EVORA-Update-Windows-x64.json`: protocol version, application version, per-file SHA-256 and size, and compressed byte ranges.
- `EVORA-Update-Windows-x64.bin`: independently compressed gzip objects, deduplicated by content hash.

Linux releases similarly publish `EVORA-Update-Linux-x86_64.json` and `.bin` from `python scripts/build_linux_package.py`. Linux file modes are part of the manifest. Library links in the frozen bundle are materialized within the package.

All update assets and the existing installer/package are published with `SHA256SUMS`. Their URLs must belong to the official EVORA release. HTTPS and SHA-256 protect transport and file integrity; this protocol does not add a separate publisher signature. The manifest's published checksum is checked before any paths or byte ranges are used. Each compressed object and its bounded decompressed output are verified separately.

GitHub's release asset service must support HTTP byte ranges. A server returning the complete bundle instead causes an explicit full-package fallback without consuming the whole response. Interrupted ranges resume from the private local cache.

## Installation and recovery

Settings shows the actual incremental download size and changed-file count. **Restart and update** is available after verification and when processing and analysis have finished. Case changes are blocked while the update is installing.

The backend copies the installed, verified helper to its private staging directory. That copy asks the desktop to close gracefully, waits for the desktop and Python processes to exit, and validates the installation and staged files again. It only replaces files in the managed application inventory. It never replaces the user's database, evidence vault, or settings.

Every replacement has a complete backup and a durable journal entry before it is applied. The target is replaced atomically so the launcher remains present if installation is interrupted. The new installed inventory is written last. The helper restarts EVORA and waits up to four minutes for the desktop to confirm the expected backend version. A failed startup restores the old files and restarts the previous version; a successful startup commits the transaction and removes backups. Linux uses a small launcher that preserves the selected database, evidence folder, graph settings, port, and browser preference across restarts. Its default data folder remains `~/evora_data`, with existing `./evora_data` databases recognized for compatibility. Data under the backend program folder is rejected. The launcher prevents concurrent launches and waits for backend startup before reporting a healthy version.

Normal desktop startup recovers an interrupted transaction before starting the backend.

Database migrations in releases must remain compatible with rollback to the preceding application. The updater restores application files, not database contents.

The Linux archive can be extracted and installed by running its `install.sh`; the installer preserves legacy data folders and requires EVORA to be closed. It installs to the current user’s application directory without sudo.

A missing helper or inventory, incompatible manifest, modified file slated for removal, failed health check, unsupported byte ranges, or an incremental download larger than the installer uses the complete-package flow. The fallback remains available after a failed update.

## Verification

```sh
go test -C desktop ./internal/patcher ./cmd/updater
python -m unittest backend.tests.test_incremental_updates backend.tests.test_updates
# On Linux, also test the real launcher, application API and rollback:
python -m unittest backend.tests.test_linux_updates
```

The Go helper lifecycle tests run real child processes and exercise both successful restart and failed-health rollback. The release jobs run native platform checks before packaging. Linux tests install a real package, run the application through the launcher, apply a changed-file update through its API, verify original evidence and the encrypted database, and exercise failed-startup rollback.
