# Evidence processing

In a case’s Evidence tab, click **Process** to process pending sources, or select files first. Use Processing options to reprocess completed files. The queue reads all case evidence pages; uploads added later are picked up by the next batch.

**Analyze images and video** is enabled by default. It uses the image model selected in Settings for scene descriptions and visible text. Hosted processing requires a connected provider, online mode and consent to the displayed destination for each batch. Turn the option off for local detections only. Sources with basic detection output remain pending for image/video analysis until that enrichment completes.

Video batches use a five-second sampling interval and a twelve-frame cap. Open a source’s **Reanalyze video → Sampling** controls to change these limits or request configured local speech transcription. Standalone audio is skipped.

Results open a populated extraction, preferring scene descriptions for media. Each extraction retains its own completed output, so a later failed attempt or detection-only run does not hide earlier descriptions and OCR. Reanalysis controls sit below saved results.

The browser sends one source at a time. Existing work is monitored, completed outputs are skipped, and uncertain requests are not automatically retried. The Activity button shows queue progress and failures. **Stop queue** stops future submissions; accepted server work can still finish. Switching tabs or cases keeps a batch running. Signing out or closing/reloading the window stops future requests.

Run case analysis afterward to include new observations. Reviewers can inspect results but cannot start processing.

## Checks

`npm --prefix frontend run test:bulk-processing` checks the queue against disposable FastAPI/SQLite storage. Image and video browser checks run with `node frontend/test/image-understanding.integration.mjs` and `node frontend/test/video-understanding.integration.mjs`. Set `EVORA_TEST_PYTHON`, `EVORA_PLAYWRIGHT_MODULE` and `EVORA_CHROME_PATH` for local test installations. The media checks use a labeled local provider double; they do not measure model accuracy.
