# Process all evidence

Open a case's Evidence tab and click **Process all**, then **Start batch**. The queue includes all case evidence pages, regardless of the library's current search or kind filter. Uploads added after discovery are picked up by the next batch.

The browser sends one source at a time through the existing authorized processing endpoints. Completed sources are skipped. Existing queued/running work is monitored instead of duplicated. Each new request has its own idempotency key. Individual failures remain visible and do not conceal successful sources. A request with an unconfirmed outcome is labeled unconfirmed and is never automatically posted again. The next explicit batch checks processing history first.

Basic processing extracts documents/CSV records and runs local image/video detection. To include scene descriptions and model-assisted OCR, enable **Include image descriptions, OCR and video scene analysis**. The panel displays the selected image model and destination. Hosted providers require a connected provider, online mode and explicit batch consent before any normalized image or sampled frame is sent. Provider/model/endpoint expectations are fixed for the batch and verified by existing backend endpoints; changing settings cannot silently redirect queued media to a different destination.

Images with only basic completed output can still receive description/OCR enrichment. Existing completed vision output is skipped. Inspect a source's individual controls to intentionally request a new analysis or change sampling. Batch video uses a 5-second sample interval, a 12-frame cap and no speech transcription. Standalone audio is marked skipped and retains its individual transcription workflow.

Progress shows completed, failed, skipped and unconfirmed items, with individual run IDs when available. The header's bell-shaped **Activity** icon shows the running batch count. Click it to see the case, current source, progress, waiting files and items needing attention. You can stop a case's remaining queue from this panel without returning to its Evidence tab.

The batch belongs to the current app window and authenticated session. Switching tabs or cases keeps it running. Returning to Evidence restores the same batch and its results. Signing out, replacing the local session or closing/reloading the window stops future requests. **Stop queue** does not cancel a server job already accepted; that job may still finish. The UI states this explicitly. Backend job cancellation is not implemented. The activity panel currently tracks Process all batches; individual source processing and case-analysis jobs retain their own status controls.

Run case analysis after processing to include the new outputs; the batch does not silently start investigation analysis.

Reviewers cannot start the batch. Existing backend case access checks, file preflight, immutable output publication and original-file integrity remain authoritative. This update adds no backend endpoint or schema change.

Validation: the frontend regression suite covers pagination, active/completed run reconciliation, errors, consent, fixed provider expectations, cancellation, session changes and response lineage. `npm --prefix frontend run test:bulk-processing` uses an isolated real FastAPI/SQLite server, the project test interpreter via `EVORA_TEST_PYTHON`, and a regenerated OpenAPI bundle. It verifies 105 stored originals across two evidence pages, extraction lineage, malformed-input isolation and no duplicate completed runs. It does not contact a model provider or prove model accuracy.


The optional real-browser regression is `npm --prefix frontend run test:activity-browser` after a production build. Set `EVORA_PLAYWRIGHT_MODULE` and `EVORA_CHROME_PATH` when Playwright/Chrome are outside the normal dependency/browser paths. It creates its own temporary local-account workstation and verifies header activity, navigation to another tab and the case list during processing, queue stopping, resume, completed-run reconciliation, mobile layout and JavaScript errors. It never uses an existing workstation database.
