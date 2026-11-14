# Security, provenance and limitations

## Access and storage

Case APIs enforce workstation-account permissions. Inaccessible case resources return not-found responses. These controls depend on the backend and operating system remaining trusted; they do not protect against an administrator modifying application files or storage directly.

The SQLite database uses account-password encryption. Original evidence, Neo4j data and provider credentials are stored separately and need filesystem protection. Encryption of the database does not encrypt those files. See [database encryption](database-encryption.md), [local accounts](local-accounts.md) and [provider credential storage](chatgpt-connection.md#storage-and-disconnect).

## Provenance

Evidence intake records original byte hashes and sizes. Processing creates immutable output and provenance records; reprocessing preserves earlier runs. Analysis snapshots pin their input outputs and source references. Transcript corrections retain revisions and actor history.

Citations and hashes support traceability. They cannot establish the authenticity of material before intake or prevent a privileged attacker from replacing the application and its records. Public audit records use resource references; private model provenance can contain sensitive case context.

## Interpretation limits

- Triage scores prioritize review and are not evidence of guilt or ownership.
- Candidate links, visual tracks and plate readings require source inspection; they do not establish a person's identity.
- Model descriptions, OCR, transcripts and generated reports can be wrong. Grounding checks reduce unsupported output but cannot prove factual accuracy.
- Video descriptions cover sampled frames. Speech timestamps are estimates, and speaker identity is not established.
- Device clocks and missing time zones can make temporal correlations uncertain.
- Approximate map markers represent supported place mentions rather than a verified device or person location.

Synthetic tests check defined behavior and failure handling. They are not field accuracy benchmarks. Evaluate extraction models on representative permitted evidence before relying on their results.
