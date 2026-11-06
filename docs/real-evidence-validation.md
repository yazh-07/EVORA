# Live image and evidence validation — 6 November 2026

**Result: the workflows pass the checks below, but the tested model's answers are not consistently reliable. This is not a finding that everything works or that the application is validated for forensic use.**

Subsequent [reliability repairs](reliability-fixes-2026-11-07.md) add a deterministic uniform-pixel guard, enforce model-derived Q&A qualification and tighten citation validation. Those repairs address specific defects from this report; they do not establish general model accuracy. This document retains the earlier observations unchanged.

## Samples and execution

No investigator case dataset was available. Validation used a real photograph already present at `fixtures/media/astronaut.png`, a public scanned text excerpt, and a generated blank negative control. These are public test samples, not evidence from a real investigation. The scan comes from [scikit-image's versioned data repository](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/page.png).

Inference ran against a real local Ollama 0.34.0 instance with [qwen3-vl:2b-instruct](https://ollama.com/library/qwen3-vl:2b-instruct). No model responses were mocked for the live acceptance run. The GPU driver was unavailable, so inference used the CPU. A disposable Neo4j 5.26.0 Community instance supported the final graph test. Tests used separate accounts, SQLite files, and evidence directories under `/tmp/evora-real-evidence/`; existing case storage was untouched.

Machine-readable results, including original hashes, model digest, returned observations, question answers, and processing timings, are in [the live results](validation/live-image-results.json). This is a small acceptance sample, not a representative accuracy benchmark. The scanned page is a familiar public test image; success on it does not establish performance on unseen documents.

## What passed

- All three images completed actual description/OCR processing.
- Scanned text matched a manually transcribed reference after whitespace normalization in the initial complete live run: similarity 1.0. This measure uses `difflib.SequenceMatcher`, not a general OCR accuracy score.
- The blank negative control produced an empty text transcription.
- Stored originals remained byte-for-byte identical; recorded original SHA-256 values matched input bytes. Model digest and preparation provenance were retained.
- Repeating a request with the same idempotency key returned the existing run.
- A deliberately missing model caused a failed rerun without replacing the earlier completed results.
- Image observations entered the frozen analysis snapshot. The final real case analysis completed and its graph was available through the API.
- Unauthenticated observation access was denied; logging back in preserved access to saved results.
- A question asking who was guilty returned unsupported with no citations.

## Accuracy failures

1. **Small text on the photograph was misread.** A live result included `COLEMAN HAMLEY TOGETHER` and `BURN V. C. 01`, which are not accurate transcriptions of the visible patch text. Successful processing does not imply correct OCR.
2. **The blank image description invented details.** One run described thin black horizontal lines on an entirely white image. Empty OCR did not prevent a hallucinated description.
3. **Case Q&A selected the wrong source and its verifier accepted it.** Asked for the heading on the scanned page, one run answered with text from the photograph's patches and returned `supported: true`. The citation pointed to the photograph, rather than the scanned page. A subsequent run answered the heading correctly, but both runs omitted the requested qualification that the text was model-derived. A second model pass is not an independent factual guarantee. Both recorded runs are retained in the results file, with separate post-run source/qualification review fields.

These failures remain unresolved. Source disambiguation, qualification of model-derived claims, and stronger rejection of unsupported answers need work before relying on this model configuration for investigative conclusions. Original images and extracted text require human comparison.

## Other verification

| Check | Result |
| --- | --- |
| Complete backend suite | 874 tests, OK, 7 skipped |
| Frontend suite | 374 passed, 0 failed |
| Production build, API schema check, TypeScript | Passed |
| Neo4j connection/schema suite with live integration enabled | 17 tests passed |
| Graph projection and analysis suites with live integration enabled | 33 tests passed |
| Browser image workflow | Passed; this separate test uses an explicitly labeled provider double |

The browser test covered hosted-provider consent, image content submission, result display, provenance, reload without automatic transmission, failure recovery, and mobile layout. It is not a live hosted-provider accuracy test. No hosted API key was configured, so live hosted inference was not tested. Executive-brief generation with a live configured text model was not established by this run. Other modalities' accuracy, exports, and the complete investigation workflow were not validated against a real case dataset.

The first disposable graph instance failed because its 512 MiB data allocation could not accommodate database log preallocation. Recreating the test instance with a 2 GiB allocation resolved that setup issue; the final analysis completed. An early harness assertion also included ordinary image detector scores when checking the four vision observations; that harness assertion was corrected before the complete runs.

## Repeating the live test

Build the frontend, start an Ollama service with a downloaded vision model, and configure a **disposable** Neo4j database through `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`. Download the scanned image from the versioned source above. Use a new output directory for every run:

```sh
python scripts/validate_live_images.py \
  --model qwen3-vl:2b-instruct \
  --endpoint http://127.0.0.1:11435 \
  --scan /tmp/evora-real-evidence/page.png \
  --output /tmp/evora-live-new-run
```

The script launches and stops its own application server. It leaves its isolated database, source copies, backend log, and `results.json` in the requested output directory. Review both successful processing and semantic accuracy; a completed run is not an accuracy pass. Service credentials and provider secrets are not included in the committed results.
