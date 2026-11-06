# Video scenes, text, speech and candidate tracks

Open an uploaded video's evidence inspector and use **Video scenes, text and speech**. Configure an image-capable model in Settings, either shared with Q&A or separate. A text-only model cannot inspect frames. Ordinary extraction still runs local visual detectors; the explicit video action adds model-derived results in a new immutable processing run.

Choose a sampling interval (1–60 seconds) and a frame cap (1–60, default 12). With a long clip, capped frames are spread across its extent rather than silently processing only the beginning. A one-frame cap necessarily covers only one instant. Each frame is a separate image-model request. Hosted execution requires explicit confirmation of the endpoint, model and frame cap. Frames are normalized through the existing image pipeline; audio is never sent to that provider by this feature. Provider usage charges may apply.

Results include:

- Timestamped sampled-frame descriptions (`video.scene`), visible text (`video.ocr`) and model-reported limitations. Timestamp buttons seek the opened video player.
- Geometric candidate tracks (`video.track`) over existing local detections, with member observation IDs, frame numbers, timestamps and boxes. Association uses one-to-one greedy IoU matching at 0.3 or above, with at most 1.5 seconds between detections of the same category. Tracks do not interpolate boxes, establish identity, cross clips or recover long occlusions; they can fragment or switch subjects.
- Optional local speech transcription, with timestamped `transcript.segment` records in the existing transcript viewer. Existing correction/history features remain available. `transcript.status` distinguishes absent audio from no speech recognized (`silence`); silence is a model result, not a verified acoustic finding.
- A provenance observation (`video.provenance`) containing the original hash, decoded frame count, OpenCV version, exact sampled frames, normalization/submitted-image hashes, model identity/digest when available, prompt hashes and local speech model/audio hashes. Original videos stay unchanged.

New observations enter the next case-analysis snapshot and are available to Q&A. Prompts mark video and speech records as model-derived and tracks as unverified associations. A successful extraction does not guarantee factual accuracy. General case analysis does not independently watch every original video.

## Local speech setup

Install FFmpeg and ffprobe and the optional package into the Python environment that runs the backend:

```sh
python -m pip install -r requirements-speech.txt
```

Download a CTranslate2-format Whisper model directory separately. Point `EVORA_SPEECH_MODEL_PATH` to that directory (containing `model.bin`, configuration, tokenizer and vocabulary) before starting the backend. The application never downloads speech models during evidence processing. Select a multilingual model for multilingual material; the `tiny.en` model used in validation is English-only.

```sh
export EVORA_SPEECH_MODEL_PATH=/absolute/path/to/downloaded/whisper-model
python -m backend.run
```

Enable **Transcribe speech locally** on the video. The checkbox remains disabled when the engine/model or audio tools are unavailable. Speech runs in a bounded CPU subprocess using int8 inference, voice activity detection, local files only, and canonical 16 kHz mono PCM audio. Speech observations use an unavailable-confidence placeholder of zero. Timestamps are model estimates, not exact word alignment; diarization, speaker identity and translation are not implemented.

## Limits and failures

The existing visual decoder limits still apply: 50 MiB original size, 25 million pixels per frame, up to 216,000 decoded frames and a one-hour video bound. Descriptions cover sampled frames only; brief actions or text can be missed. This is frame-based interpretation, not a continuous audiovisual model. Speech is bounded to one hour, 5,000 segments, 2 MiB worker output and a 240-second inference subprocess timeout. Audio extraction has a 120-second timeout. Every frame inference uses the existing bounded image request; a frame cap can still take many minutes on a CPU.

If any requested frame, decode or speech stage fails, the entire new run fails without publishing partial results. Earlier completed results remain selected. A later ordinary extraction can become the newest output; historical outputs retain their references. Re-run video enrichment when its results should be the current output. Existing deployment requirements for graph publication still apply.

## Validation performed

- Real codec decoding, capped samples across a clip, per-frame uniqueness, OCR/descriptions, candidate tracks, original hashes, private provenance, idempotent replay and analysis-snapshot inclusion were tested through the API with a labeled vision provider double.
- Consent, wrong source type, missing speech configuration, failed-frame atomicity and absent-audio handling were tested. Tracking checks cover separate nearby candidates, category changes and gaps.
- The browser test exercises consent, frame limits, result display, timestamp seeking, provenance, failure recovery and mobile layout. It uses a vision protocol double, not an accuracy benchmark.

Source live-validation outputs were intentionally excluded; model accuracy and live-service access are not established by deterministic protocol doubles.

To repeat the live API test, configure the speech environment and a local vision service, then run `python scripts/validate_live_video.py --video /path/to/clip.mp4 --model YOUR_VISION_MODEL --endpoint http://127.0.0.1:11434 --output ~/.hermes/cache/scratch/new-video-test`. Use a new output directory under `~/.hermes/cache/scratch/`. Browser acceptance runs with `node frontend/test/video-understanding.integration.mjs` and the same Playwright/Python environment overrides used by the image test. Test artifacts are isolated from existing cases.
