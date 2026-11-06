# Image descriptions and model-assisted OCR

## Shared model and OpenRouter

In Settings, enable **Use selected model for image description and OCR** to use the Q&A model for both text questions and explicit image processing. The model must support image input. Future image requests follow changes to the selected Q&A model; completed results retain their original model provenance. Turn the option off to specify a separate vision model, or leave that separate field blank to disable image processing.

For OpenRouter, turn off Offline mode, select **Cloud / Custom (OpenAI-compatible)**, enter `https://openrouter.ai/api/v1` and your OpenRouter API key, then fetch models. Use a full `provider/model` ID from that catalog. Models advertising image input are marked **Image input**. An unknown capability is not proof that a model accepts images.

If the Q&A model is text-only, click **Fetch image-capable models**. Search the filtered list and select a model to use for images. This fills the separate vision model and turns off shared-model mode while keeping the Q&A model unchanged. Click **Save Settings** to apply. If the provider does not publish capabilities, the picker explains that a supported model must be entered manually; an empty advertised list has its own message. Fetching this list does not run inference or transmit evidence.

Connection tests honor the administrator's unsaved online/offline selection without saving it. Offline operation still blocks hosted requests until online settings are saved. The catalog may be publicly accessible: a successful model listing is not proof of valid credentials, credits, inference access, or OCR accuracy. Authentication, permission, URL, rate-limit, and timeout failures have specific messages; raw provider error bodies and keys are not shown.

EVORA can send an image to a configured vision-capable model and save two derived outputs: a scene description and a transcription of visible text. It supports local Ollama and hosted providers using the OpenAI-compatible Chat Completions image format. A text-only model cannot inspect image pixels.

## Configure a model

Open **Settings → Model configuration** as an administrator.

### Local mode

1. Leave **Offline mode — local models only** enabled.
2. Choose **Local (Ollama)**.
3. Enter the local Ollama endpoint.
4. Enter an installed vision-capable model's identifier in **Vision model**.
5. Save Settings.

The vision model can differ from the Q&A model. No model is downloaded automatically. The local path checks installed-model capabilities, rejects remote/cloud-backed Ollama entries, and records the local model digest. An untagged local name is matched to its `:latest` entry where available.

### Hosted mode

1. Disable **Offline mode — local models only**.
2. Choose **Cloud / Custom (OpenAI-compatible)**.
3. Enter the provider base URL and API key.
4. Set a **Vision model** identifier supported by that provider for image input and JSON responses.
5. Save Settings.

Remote hosted endpoints require HTTPS. Loopback HTTP endpoints are supported for local compatible servers and testing. API keys remain in backend memory and never enter browser storage or processing provenance. When changing a provider URL, re-enter its key; a saved key cannot be silently sent to another URL.

Provider, endpoint, model, and online/offline selections currently apply to the running service. For startup configuration, use `EVORA_VISION_MODEL`, `EVORA_QA_PROVIDER`, `EVORA_QA_URL`, `OPENAI_API_KEY`, and `OPENAI_BASE_URL` as appropriate. Never put real keys in source files or shell history. The launcher defaults to offline mode; `python -m backend.run --online` explicitly starts with hosted providers enabled. Settings can also switch modes during the session.

The provider and endpoint are shared with Q&A and the executive brief; the vision model identifier is separate. Switching Q&A to a hosted provider also allows extracted text context to be sent there when those language features are invoked. Ordinary image extraction does not automatically call the vision provider.

## Analyze an image

1. Open a case and select an image in **Evidence**.
2. Find **Image description and visible text** in the media inspector.
3. Check the displayed provider and vision model.
4. For a hosted provider, select the confirmation naming the exact destination and model.
5. Click **Describe image and extract text**.
6. Inspect the scene description, visible text, and model-reported limitations against the original image.
7. Open **Image-processing provenance** for model and source details.
8. Run case analysis again to include the new observations in an analytical snapshot.

Read-only reviewers can inspect saved results but cannot request new processing. Consent is tied to the displayed provider, model, and endpoint; the server rejects a submission if those settings changed before acceptance.

## Saved outputs and source handling

Each successful action creates an immutable processing run containing:

- Existing visual candidate detections, regenerated from the original image.
- `image.description`: model-generated scene description.
- `image.ocr`: model-assisted transcription, preserving returned line breaks.
- `image.limitations`: limitations reported by the model, or a statement that verification is still required.
- `image.provenance`: requested/actual model, provider, available local model digest, prompt hash, original SHA-256, submitted-image SHA-256, dimensions, orientation handling, and normalization details.

Before processing, the original bytes are checked against stored size and SHA-256. The vision request receives a PNG copy with EXIF orientation applied, transparent pixels composited onto white, and the longest edge limited to 2048 pixels. This normalization and its submitted-image hash are recorded. Original bytes and metadata remain unchanged; filenames, API keys, and storage paths are not included in the model prompt.

The source locator identifies the whole first image. The feature rejects animated/multi-frame images for vision analysis rather than implying coverage of all frames. It does not generate text bounding boxes or measured OCR confidence; derived observations use an uncalibrated placeholder score of zero, not a claimed accuracy estimate.

The provider response is bounded, parsed as JSON, checked for expected fields and types, and rejected if incomplete, refused, oversized, or malformed. A failed run publishes no partial description/text output and leaves prior completed processing outputs available. A repeated request with the same idempotency key does not transmit the image again.

Reading saved results, refreshing the source, or reloading the page does not automatically transmit an image. A new action requests a new processing run. Historical citation/pinned views may continue showing their original referenced output; they are not silently rewritten to new results.

## How case analysis uses the results

The next case analysis selects the latest completed processing output for the image and freezes its observation references. Image description and OCR observations become available to the analysis context. Q&A can cite their source observation IDs. Prompts identify them as model-derived interpretations/transcriptions that require qualification and verification.

The executive brief uses bounded, sampled context; it does not necessarily read every record. General case analysis does not automatically resend all raw images to a vision model. The explicit image action is what inspects the normalized image pixels.

A later successful ordinary extraction can become the latest output instead of the vision-enriched run. To include current descriptions, choose the desired processing output for source inspection and generate a new enriched run before the next case analysis when needed. Earlier analysis snapshots remain unchanged.

## Limitations

- This is vision-language-model text extraction, not a dedicated OCR engine or a certification of textual accuracy.
- Descriptions and transcriptions can hallucinate, omit details, or misread text. Verify them against the original, particularly names, amounts, identifiers, and dates.
- Small text, handwriting, low contrast, image normalization, or provider-side resizing can reduce readability.
- No returned text means the model reported no readable text, not proof that the image contains none.
- Generated descriptions do not establish identity, ownership, intent, guilt, location, time, or causality.
- Provider-specific model support, quotas, authentication, and usage charges still apply.
- Video descriptions, scanned-PDF processing, dedicated OCR confidence, and text-region boxes are outside this change.
- No cloud API key or local vision model is bundled. Configure one before live use.

## Verification

Backend tests use explicit provider protocol doubles with real image preparation, hash verification, SQLite publication, observation validation, and analysis-snapshot checks. They cover consent, offline restrictions, wrong destinations, idempotent replay, malformed/truncated replies, alpha compositing, and local cloud-alias rejection.

The browser acceptance uses a real local EVORA instance and a disclosed local HTTP provider double:

```sh
EVORA_TEST_PYTHON=python node frontend/test/image-understanding.integration.mjs
```

Playwright and a browser must already be installed. `EVORA_PLAYWRIGHT_MODULE` and `EVORA_CHROME_PATH` can select existing installations. The test exercises online/offline configuration, image confirmation, actual image content blocks, output persistence, source provenance, responsive layout, and no transmission on reload. These protocol tests do not measure a live model's scene-description or OCR accuracy.

## Provider references

- [Official OpenAI image-input documentation](https://developers.openai.com/api/docs/guides/images-vision?api-mode=chat)
- [Ollama vision API](https://docs.ollama.com/capabilities/vision)
