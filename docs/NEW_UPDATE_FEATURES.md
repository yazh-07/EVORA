# EVORA — Updated Application Features

**Updated:** 7 November 2026
**Scope:** The redesigned investigation workspace and offline local account system, including the existing forensic tools available through the new workflow.

This document describes implemented capabilities. Installation requirements and current limitations appear at the end so file storage, extraction, analysis, and reporting support are clear.

## 1. Investigation workflow

The application organizes each case into five primary sections:

| Section | What you can do |
| --- | --- |
| **Overview** | Check evidence readiness and choose the next investigative action. |
| **Evidence** | Add originals, inspect files, start extraction, and review source observations. |
| **Timeline** | Compare extracted events chronologically across evidence sources. |
| **Investigation** | Review findings, explore relationships, browse entities, prioritize sources, and ask evidence questions. |
| **Report** | Assemble selected findings, investigator notes, and source references into an exportable draft. |

- Open cases from a searchable, paginated case browser.
- Create a case with a recognizable title and optional scope or investigative questions.
- Return to the case list from an active investigation.
- Keep visited panels and their working state available while switching sections.
- Load tools when first opened, reducing unnecessary initial activity.
- Expand technical references when needed instead of displaying every internal identifier at once.

## 2. Offline workstation operation

- Run the interface and API locally on one workstation.
- Use local accounts without internet access, email verification, or a cloud identity provider.
- Start the application through `python -m backend.run`.
- Serve the application on `127.0.0.1:8000` by default.
- Select a different database, evidence directory, or port through launcher arguments.
- Keep account information, case records, session records, and audit history in the local SQLite database; retain original evidence in the configured evidence directory.
- Use installed Ollama models for local AI assistance, or configure a hosted OpenAI-compatible provider in online mode.
- Start with cloud AI providers disabled; administrators can explicitly enable online mode in Settings or use the `--online` launcher option.
- Reject model endpoints outside `localhost` or literal loopback addresses in offline mode.

Dependencies, Neo4j where required, Ollama, and model files must be installed before disconnecting the workstation. See [Runtime requirements](#18-runtime-requirements-and-startup).

## 3. First-launch administrator setup

- Detect whether the workstation has already been configured.
- Create the first administrator using a username, display name, and password.
- Require at least 12 characters for a newly created password.
- Support case-insensitive usernames containing letters, numbers, periods, underscores, and hyphens.
- Provide a recovery code during initial setup.
- Require acknowledgement of the recovery code before entering the workspace.
- Prevent another first-launch setup after an account exists.
- Protect against concurrent setup requests creating multiple initial administrators.
- Provide no default username or default password.

The recovery code is shown once and should be saved outside the workstation.

## 4. Login, sessions, and password recovery

- Sign in using a local username and password.
- Replace manual access-token entry with automatic browser session handling.
- Restore a valid session after a page reload.
- Show the signed-in user's display name and role in the header.
- Sign out from the header.
- Lock the interface after 30 minutes of inactivity.
- Apply a 12-hour absolute session limit.
- Keep background data refreshes from extending the server's inactivity window.
- Notify other tabs in the same browser profile when the session changes.
- Clear case state and cancel pending reads when the session changes.
- Reject successful API responses associated with a different account after a cookie change.
- Let signed-in users change their own password after confirming the current password.
- Require users to replace administrator-issued temporary passwords before opening cases.
- Let the setup administrator recover access using the saved recovery code.
- Replace the recovery code after successful recovery and invalidate the previous code.
- Revoke existing account sessions after recovery or password changes.
- Throttle repeated setup, login, recovery, and password-verification attempts.

## 5. Account administration and permissions

Open **Account** in the header to manage the local account. Administrators also receive account and case-access controls.

| Role | Available access |
| --- | --- |
| **Administrator** | Manage local accounts, workstation settings, and all existing cases. |
| **Investigator** | Create cases and work on cases to which they have access. |
| **Read-only reviewer** | Read assigned cases; case-changing API operations are rejected. Own password changes and session operations remain available. |

Administrators can:

- Create investigator, reviewer, and additional administrator accounts.
- Set a temporary password for a new account.
- Change an account's role.
- Disable and re-enable accounts.
- Reset an account's password, requiring replacement at next login.
- Assign or revoke access to a selected case.
- View the latest 100 account audit events.

Administrative account updates revoke that user's existing sessions. The application prevents disabling or demoting the last active administrator. Existing case memberships and historical investigator identities remain intact when local accounts are introduced.

## 6. Case overview and guidance

- View the total number of original evidence sources in a case.
- See how many sources have a completed latest extraction attempt.
- Identify sources that have not been processed or whose latest attempt failed.
- See how many sources are queued or running.
- Receive a suggested next step based on the current evidence and selected analysis.
- Jump directly to evidence intake, source review, the timeline, findings, or reporting.
- Refresh readiness counts from real evidence and processing histories.
- Open an investigative hypothesis briefing when the selected analysis contains one.

Readiness counts describe the latest processing attempts. Analytical results remain tied to the selected completed analysis.

## 7. Evidence intake

- Drag and drop multiple original files into an upload queue.
- Choose multiple files using the file picker.
- Review filenames and sizes before upload.
- Automatically suggest evidence types from file extensions, MIME families, and selected text/CSV headers.
- Override the suggested evidence type.
- Edit each source's descriptive label.
- Provide an optional acquisition timestamp in UTC for remaining batch uploads.
- Remove items from the upload queue.
- Track whether an item is ready, uploading, uploaded, or failed.
- Upload queued files sequentially.
- Stop the queue when an upload fails so the error can be addressed.
- Retry remaining files without resubmitting items already confirmed as uploaded.
- Use the separate single-file form for individual source metadata.
- Record original bytes, filename, size, media type, source label, and SHA-256 integrity metadata.
- Explain whether the selected format supports extraction or original storage only.

### Evidence categories

The interface supports these evidence categories:

| Category | Extraction or inspection support |
| --- | --- |
| Document | UTF-8 plain-text extraction; original storage for other uploaded document formats. |
| Image | Visual candidate extraction, plus explicit vision-model scene descriptions and model-assisted OCR for supported single images. |
| Video | Visual candidate extraction and source playback where decoding/browser support permits. |
| Audio | Original storage and playback; review of transcript records when already available. |
| Network log | Extraction from the supported network CSV layout. |
| GPS | Extraction from the supported location CSV layout. |
| Message | Extraction from the supported message CSV layout. |
| Mobile log | Extraction from the supported exported-mobile CSV layout. |
| Transaction | Extraction from the supported transaction CSV layout. |

Automatic type detection is a suggestion. Processing validates the actual content and required layout.

## 8. Evidence library and source inspection

- Browse original sources in a paginated evidence table.
- Search the current page by filename, source label, evidence identifier, or hash.
- Filter the current page by evidence category.
- Sort the current page by newest upload, source name, or largest file.
- Open a source in a full-width inspection area.
- Inspect acquisition information, upload time, size, media type, and integrity metadata.
- Download an original after checking its size and SHA-256 against the stored record.
- Preview supported UTF-8 text after verifying the original bytes.
- Display text as plain text, including content that resembles HTML or scripts.
- Open evidence from a timeline event, finding, relationship, or answer citation.
- Follow citation locators to referenced source observations or processing outputs where available.

Inline text preview is limited to files of at most 2 MB and displays at most the first 100,000 characters. Download the original to inspect the complete file.

## 9. Extraction and processing

- Start a processing run for a supported source.
- See queued, running, completed, and failed statuses.
- Read plain-language explanations of processing progress and failures.
- Inspect processor version, run identifiers, timestamps, and failure diagnostics.
- Retry a failed status check.
- Start a new processing run when another extraction attempt is needed.
- Review extracted observations alongside their raw and normalized values.
- Inspect observation kinds, extraction scores, timestamps, and source locators.
- Pin observations to a completed processing run.
- Preserve previous completed outputs when a newer attempt is pending or fails.

Source extraction produces candidates and observations that still require investigator verification.

## 10. Media and transcript inspection

- Explicit video analysis adds timestamped descriptions and OCR of capped, sampled frames.
- Candidate tracks associate nearby visual detection boxes within the clip without verifying identity.
- Optional Faster Whisper speech transcription runs locally and feeds the transcript viewer and correction history.
- Hosted frame processing requires consent; audio remains local. Failed runs preserve earlier completed results.
- See [Video analysis setup and limits](video-analysis.md).

- Inspect supported original images and videos.
- Display available detection boxes over the media.
- Toggle detection overlays and apply the configured detection-score threshold.
- Select detections and inspect their associated observations.
- Navigate supported frame or time-offset citation locations.
- Play or download supported audio/video sources after original-byte verification.
- Review available transcript segments and their source-relative timing.
- Search transcript text.
- Inspect transcript correction history.
- Submit permitted transcript corrections with a reason.
- Preserve corrections as a new derived processing output.
- Run a new analysis to include revised transcript evidence.

Automatic video speech transcription requires the optional local speech engine, downloaded model and audio tools. Visual candidates and tracks do not identify a person or establish vehicle ownership.

### Image descriptions and model-assisted OCR

- **ChatGPT plan** connects eligible accounts through **Continue with ChatGPT**, without a manually supplied API key. Local EVORA accounts remain separate. Text, image and sampled-video requests use the official plan-specific Responses API; speech stays local. See [ChatGPT connection](chatgpt-connection.md) for setup, eligibility, credential storage and verification limits.

- Image processing can reuse the selected Q&A model when it supports images, or use a separate vision model.
- **Fetch image-capable models** provides a searchable provider list for choosing a separate image model while preserving a text-only Q&A model.
- OpenRouter model discovery supports unsaved online settings, labels advertised image-capable models, and shows specific connection errors. Use `https://openrouter.ai/api/v1` and full provider/model IDs.

- Configure a separate vision-capable model using local Ollama or a hosted OpenAI-compatible provider.
- Explicitly request a scene description and visible-text transcription for a selected image.
- Confirm the exact hosted destination and model before transmitting an image.
- Preserve line breaks in returned text and display generated output separately from the original.
- Record model/provider identity, available model digest, prompt hash, source hash, submitted-image hash, and normalization details.
- Save results in an immutable processing output, available to subsequent case analysis and Q&A.
- Keep prior completed outputs when vision processing fails.
- Prevent automatic retransmission when saved results are read or the page reloads.
- Reject cloud-backed Ollama entries in the local vision path.

This is model-assisted text extraction with whole-image provenance; dedicated OCR confidence and text-region boxes are not provided. See [Image descriptions and OCR](image-description-and-ocr.md).

## 11. Case analysis and history

- Run analysis using the latest completed processing output for each source.
- Follow analysis status through completion or failure.
- Retry case analysis after a failure.
- Retain previous analysis results.
- Select a completed analysis from the history selector.
- Keep analytical views tied to the same selected analysis.
- Keep passive result discovery from replacing an investigator's explicit analysis selection.
- Inspect analysis and snapshot references in expandable details.

## 12. Timeline

- Load extracted event records across all event pages for the case.
- Present dated events in chronological order using normalized UTC instants.
- Keep undated events in a separate view.
- Search event summaries, kinds, and available original timestamps.
- Filter by evidence source.
- Filter dated events by an inclusive UTC date range.
- View matching counts across the loaded case collection.
- Reveal additional events incrementally in groups of 50.
- Open the evidence source supporting an event.
- Inspect original timestamps, normalized timestamps, extraction scores, event IDs, and observation references.

The timeline is a live extracted-event view independent of the selected analysis. Missing or relative times are not assigned invented absolute timestamps.

## 13. Findings and review

- Browse findings from the selected completed analysis.
- Inspect relationships, corroboration, conflicts, gaps, clusters, anomalies, and hypotheses.
- Filter finding kinds on the current findings page.
- Expand rule, score, source, reference, and limitation details.
- Resolve supporting records against the analysis's frozen input snapshot.
- Inspect cited observation values and source locations.
- Follow supporting or contradicting evidence references.
- Review available reliability and uncertainty information.
- Record a human decision of **accepted**, **rejected**, or **needs investigation** with a reason.
- Read previous review decisions, reviewer identities, reasons, and timestamps.

An accepted finding records an investigator's review decision. It does not establish identity, guilt, causality, or resolution of a contradiction.

## 14. Relationships, entities, and evidence priority

### Relationship exploration

- View the selected analysis as a graph of source evidence, candidate entities, events, and relationships.
- Inspect graph nodes and relationship details.
- Search nodes by label, kind, or source identifier.
- Filter displayed node types.
- Zoom, pan, reset the view, and reposition nodes.
- Hide raw log events.
- Focus on a selected node and its direct neighbors.
- Open supporting evidence and available relationship citations.
- Choose source-description or filename labeling through settings.

### Entity and event inspection

- Browse extracted candidate entities and events in paginated views.
- Inspect candidate labels, categories, extraction scores, timestamps, and supporting references.
- Open evidence associated with a candidate.

### Evidence priority

- Review automated evidence scores and P1–P4 priorities.
- Inspect contributing factors and explanations.
- Compare priority evaluations and score changes over time.
- View automated priority history.
- Set a manual priority override with a required reason when authorized.
- Inspect effective priorities alongside automated results.

## 15. Local AI assistance

- Ask case-specific questions about available evidence through **Ask about the case**.
- Use suggested questions to start an inquiry.
- Read formatted answers and source citations.
- Open cited evidence at available source locators.
- Keep separate answers in the open session's question history.
- Show insufficient-evidence responses when the system cannot support an answer.
- Inspect model, retrieval, or provenance references when supplied.
- Read an optional AI-generated executive hypothesis when present in a completed analysis.
- Distinguish AI-generated briefing content from rule-based hypotheses and display the model used for generated content.

AI features require an installed and running compatible local model service. Hypotheses use bounded, potentially sampled context and require independent verification. Brief generation currently runs before analysis publication and can delay completion while the model responds or times out.

## 16. Report drafting and export

- Build a report from a selected completed analysis.
- Enter a report title, scope, investigative questions, and investigator notes.
- Load actual review decisions for findings in that analysis.
- Select accepted findings by default.
- Include or exclude individual findings explicitly.
- Keep unreviewed and other review states identified in the output.
- Refresh review decisions before exporting.
- Preview the report text.
- Download a plain-text report.
- Print the report or save PDF through the browser's print interface.

The report includes:

- Preparation time, case reference, and selected analysis reference.
- Analysis completion time, algorithm version, and input-snapshot hash.
- Investigator-entered scope and notes.
- Selected findings and their recorded review status.
- Reviewer identity, reason, and review time where available.
- AI-generated hypothesis labels and model names where applicable.
- Finding rules, reported scores, source references, and observation IDs.
- Recorded finding limitations and missing information.
- The selected analysis's evidence manifest, including filenames, source labels, IDs, SHA-256 hashes, sizes, and acquisition times.
- Report scope and interpretation limitations.

Report drafts remain in memory for the open case. Switching sections preserves the draft, but leaving the case, reloading, signing out, or selecting another analysis can discard it. Export before doing so. Reports do not embed original files or provide a complete chain-of-custody export.

## 17. Security, integrity, and interface features

### Account and session protection

- Store salted Argon2id password hashes instead of plaintext passwords.
- Store hashes of opaque session identifiers and recovery codes.
- Use HttpOnly and SameSite=Strict session cookies; add Secure when served over HTTPS.
- Check allowed hosts and same-origin mutation requests.
- Enforce role permissions and case access on the backend.
- Invalidate sessions after account changes and discard stale client responses.
- Maintain append-only account audit records alongside existing case audit records.
- Preserve historical audit identities when adding local accounts to an existing database.

### Interface

- Support light and dark themes and remember the selected theme in the browser.
- Use short, smooth transitions when switching sections, opening or closing dialogs, expanding details, and interacting with controls.
- Honor reduced-motion preferences by disabling decorative animations and transitions.
- Use direct workstation labels and restrained surfaces; generated material remains explicitly identified for review.
- Adapt layouts for desktop and narrow screens.
- Provide keyboard-operable primary navigation, focus indicators, labeled forms, status messages, and error feedback.
- Keep original-source access available throughout investigative workflows.
- Keep internal identifiers available through expandable details and provenance references.

Application login does not encrypt stored evidence. Filesystem permissions, disk encryption, and appropriate backups remain workstation administration responsibilities.

## 18. Runtime requirements and startup

Install dependencies and prepare required services while an internet connection or offline installation packages are available:

```sh
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
```

Start the offline workstation:

```sh
python -m backend.run
```

Open **http://127.0.0.1:8000**, create the first administrator, and save the recovery code.

Example custom local paths and port:

```sh
python -m backend.run --database storage/evora.sqlite3 --storage storage/evidence --port 8000
```

- Use a Python and Node environment compatible with the repository's pinned dependencies and engine versions.
- Configure an installed local Neo4j instance for production graph analysis and projection. Browser tests using a Neo4j test double do not replace this requirement.
- Install and start Ollama with the desired model before using local AI assistance.
- Codec and browser support determine whether particular media files can be decoded or played.
- Use the default offline launcher for local cookie-based accounts. Older synthetic bearer-token adapters exist for explicitly configured test harnesses.

## 19. Current limitations and features not included

The update does not yet provide:

- Persistent shared notebooks or server-saved report drafts.
- Task assignments, general evidence tagging, or collaborative editing.
- Versioned report storage or a complete case/chain-of-custody export package.
- Automatic identity reconciliation or a verified identification system.
- General PDF/DOCX text extraction, dedicated OCR-engine confidence/text boxes, or packet-capture analysis.
- Automatic audio-only evidence transcription, speaker diarization and speaker identification. Video speech transcription is available with the optional local engine configured.
- Case-wide evidence-library search; the library's search, category filter, and sorting apply to the current page.
- A timeline of every observation or a conversion of all media-relative offsets to absolute time.
- Evidence encryption through the login password.
- Email-based password recovery or a hidden administrator recovery bypass.

Unsupported extraction formats can still be preserved as originals when intake accepts them. Stored originals and successfully extracted records are distinct capabilities.

## 20. Verification of this update

The implementation was checked with:

| Check | Recorded result |
| --- | --- |
| Backend suite | 864 tests run; passed with 7 skipped. |
| Frontend suite | 374 tests passed. |
| Production build | Passed. |
| TypeScript and API schema checks | Passed. |
| Workspace browser acceptance | Passed against real FastAPI/SQLite producers with the explicit Neo4j test double. |
| Local-account browser acceptance | Passed using a disposable local database and the offline launcher. |

Browser checks covered setup, login, account creation, case assignment, temporary-password replacement, reviewer permissions, session restoration, cross-tab logout, recovery-code rotation, offline provider restrictions, responsive layouts, evidence workflows, and report export.

Live Neo4j, live AI model behavior, all possible codecs, and forensic certification are outside those browser acceptance results.

## Related documentation

- [Image descriptions and model-assisted OCR](image-description-and-ocr.md)
- [Offline local accounts and administration](local-accounts.md)
- [Investigation workspace implementation notes](workspace-revamp.md)
