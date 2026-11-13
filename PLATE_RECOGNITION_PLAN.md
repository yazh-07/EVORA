# Plate recognition improvement plan

Status: the initial local detector/OCR upgrade is implemented after the latest “start working” (13 November 2026). The broader evaluation and review roadmap below remains open.

Delivered: explicitly installed YOLOv9-t-640 plate detection plus CCT-s-v2-global OCR, running on CPU in a separate pinned Python 3.13 environment. Original-pixel boxes, raw readings, separate detector/OCR scores and artifact/runtime provenance are retained. Model artifacts are hash-checked and never downloaded while processing evidence. A separate plate display threshold defaults to 0.4. Missing models retain the earlier detection fallback; installed models use the dedicated detector instead of the Russian plate cascade. Reprocess existing images/videos to obtain new readings.

Verification: the committed public sample returns `5AU5341`; the astronaut negative image returns no plate readings. This is a runtime regression check, not an EVORA accuracy benchmark. Basic video still uses approximately one frame per second; this pass does not implement dense tracking, cross-frame consensus, perspective correction, trained regional variants, manual correction history or related-sighting search.

Install using `./scripts/setup-plates.sh`, then restart the workstation. Target-region accuracy still needs representative user footage and a held-out benchmark before claiming reliability.

## Findings from the current code

- `backend/parsers/media_detection.py` uses `haarcascade_russian_plate_number.xml` for every plate detection. It shares grayscale preprocessing and `scaleFactor=1.1`, `minNeighbors=4`, `minSize=(24,24)` with the face/body classifiers. There is no jurisdiction selection or plate-specific quality handling. These are limitations identified from code; the user's particular failed images have not been evaluated.
- The plate output contains a box and a detector label. It does not read the registration number. General image OCR is a separate optional vision-model operation over the full image, resized to a maximum edge of 2048 pixels; it is not a plate-crop recognition pipeline.
- Basic video detection samples approximately one frame per second. Optional video interpretation has a separate sampling configuration. Neither path currently provides plate-specific frame selection and repeated-reading consensus.
- Cascade decision weights are converted through an uncalibrated sigmoid. `MediaInspector.tsx` applies the same display threshold to plate, face, and body observations. A hidden overlay and a missed detection therefore need to be diagnosed separately.
- The real media fixture exercises face detection. The plate test injects a classifier result and verifies publication; it does not measure plate detection or text recognition accuracy.

## Intended workflow

**Open source → find plates → inspect crop and reading → confirm or correct → search related sightings.**

Detection, text recognition, video association, and investigator review are separate outputs. A readable registration number is not proof of ownership or vehicle identity.

## 1. Establish a representative benchmark

Collect representative, permitted test images and clips, including the examples that currently fail. Start with roughly 100–200 labeled images and 20 short clips to expose failure patterns; expand before claiming production accuracy.

Label plate boxes, visible text, unreadable/partial characters, country/layout when known, vehicle/camera, and lighting conditions. Include small distant plates, oblique views, motion blur, glare, night/IR footage, motorcycles, two-line plates, multiple vehicles, and hard negatives such as signs, bumpers, grilles and printed text.

Keep train/tuning/test partitions separate by vehicle, recording, and camera/source. Adjacent frames from one clip must not leak into different partitions. Keep a final holdout untouched during tuning.

Measure detection precision/recall at specified box overlap, false positives per image/video minute, exact full-number accuracy on readable plates, character error rate, incorrect accepted readings, unreadable/abstention rate, processing latency, RAM, and CPU/GPU cost. Report results by condition and plate region. Establish baseline results before setting release targets; a package's published benchmark is not an EVORA result.

## 2. Benchmark a dedicated local detector and recognizer

First candidate: a plate-trained ONNX detector with a plate-specific OCR model, evaluated through the modular [FastALPR](https://github.com/ankandrew/fast-alpr) pipeline. Its official project supports replaceable detection and OCR components and local ONNX backends. Candidate components are [open-image-models](https://github.com/ankandrew/open-image-models) and [FastPlateOCR](https://github.com/ankandrew/fast-plate-ocr).

Compare plate-specific recognition with a compatible [PaddleOCR text recognizer](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_recognition.en.md) on the same crops, particularly if multiple scripts/layouts are required. Choose the actual artifacts only after measuring target-region accuracy, runtime compatibility, artifact terms, model size, and offline packaging. Confirm whether Indian plates, other countries, or both are the primary requirement. If Indian plates are prioritized, include standard, BH-series, two-line, motorcycle, commercial and older/nonstandard examples in the evaluation.

Use CPU inference as the supported baseline and measure optional GPU acceleration. Preserve the existing text-processing runtime; if inference dependencies are incompatible with the pinned Python stack, isolate the plate worker. Pin packages, model hashes and preprocessing versions. Install models explicitly before use, with no automatic downloads during evidence processing.

## 3. Read from useful source pixels

Run plate detection at suitable resolution and evaluate a bounded high-resolution/tiled pass for small plates. Optional vehicle crops can provide additional search regions; retain a full-frame path so incomplete vehicle detection does not discard plates.

Keep the original crop and its exact source coordinates. Apply bounded crop padding, orientation correction, and perspective rectification when reliable corners are available. Map any transformed coordinates back to the original image/frame and retain the transform.

Evaluate a small, reproducible set of non-generative contrast/denoise variants against the unmodified crop. Record blur, glare and pixel-size limitations. Return partial or unreadable results when characters cannot be supported by the pixels. Keep raw OCR, proposed normalization, and alternatives separate; country-format checks can flag or rank candidates without silently rewriting `O/0`, `I/1`, or unusual registrations.

## 4. Use video to obtain better observations

Start with bounded clip ranges, configurable sampling and an on-demand denser pass around candidate sightings. Benchmark the frame rate on local hardware and target vehicle speeds; do not apply an expensive full-frame scan to every long recording by default.

Associate candidates within a clip, handle gaps and nearby vehicles, and retain the sharpest, largest, least-obscured crops. Combine consistent readings across distinct useful frames while preserving disagreements and alternatives. Similar adjacent frames must not artificially inflate confidence. Keep associations source-scoped, with explicit split/merge review; matching strings across recordings are candidate sightings.

Store exact presentation timestamps and original frame references. Allow cancel/resume, progress reporting, and transparent processed/skipped ranges so a partial scan cannot look complete.

## 5. Make results quick to examine

Show a plate crop beside its best reading, a short state (`Unreadable`, `Partial`, `Needs review`, `Reviewed`), and a direct original-image/frame action. Offer a few alternative readings when useful. Keep model/method details behind a disclosure.

Actions: confirm reading, correct text, mark “Not a plate”, redraw/select a crop, and re-run the selected region or short clip. A manual crop must work when automatic detection misses a plate. Preserve machine output and an append-only correction history with author/time.

Use separate plate detection, recognition, and display settings. Label model scores according to their meaning; percentages must not imply calibrated correctness. A region may be detected while its number remains unreadable. A model that is unavailable, a failed scan, and a successful scan with no detections require distinct states.

Add exact-number search and source-linked sightings first. Add partial/fuzzy search later, clearly marked approximate and constrained to authorized case scope. Keep machine candidates separate from reviewed readings; do not automatically merge vehicle/person entities from a matching plate string.

## 6. Preserve backend traceability and existing evidence

Introduce structured plate detections/readings/tracks, with evidence and processing-run references, original box/corners, frame timestamp, raw and normalized text, alternatives, detector/OCR scores, quality flags, model hashes, and review history. Prefer typed API fields over embedding the new result entirely in display strings or opaque JSON.

Make plate processing an independent operation. Missing plate dependencies must not break existing text, face/body or other evidence processing. Preserve historical completed outputs when a new attempt fails. Freeze new plate outputs into an analysis snapshot only after an explicit analysis run; older reports and citations must remain reproducible.

Extend capability/startup checks to identify whether plate detection and OCR are actually ready. Cache reproducible intermediate results by source hash and model/configuration version, with case authorization and derived-artifact access enforced. Log safe error codes and timing, without source images or plate strings in public diagnostics.

## Delivery order and acceptance

1. Baseline dataset and failure audit, including raw detector output versus hidden overlays.
2. Still-image plate detection and OCR, plus original/crop comparison and manual region selection.
3. Review corrections, exact-number search, and typed source-linked outputs.
4. Video sampling, candidate association, best-frame selection and reading consensus.
5. Fine-tuning using curated training examples if the holdout results show a persistent domain gap.

Each stage must improve its measured target without an unexplained increase in false readings, preserve original pixels and history, and work in offline CPU mode. Validate model absence, corrupt files, unsupported layouts, unreadable plates, duplicate boxes, multiple vehicles, video gaps, user corrections, cancellation, and reprocessing. Set numerical accuracy/latency gates after the baseline and hardware are known. No accuracy improvement is claimed by this planning document.
