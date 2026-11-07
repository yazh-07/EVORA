# Model-assisted investigation reports

Open a completed case analysis, choose **Report**, describe the scope and select findings. Choose **Generate with model** to use the provider and model configured in Settings: local Ollama, an OpenAI-compatible endpoint (including OpenRouter), or the connected ChatGPT account.

The model writes four sections:

- Executive summary
- Recorded chronology
- Evidence assessment
- Uncertainties and follow-up

The narrative uses processing outputs frozen in the selected analysis. Later uploads or reprocessing do not silently replace those records. Selected findings and their current review decisions provide analytical context. Other source observations in the analysis are also available to the writer; selecting findings does not restrict the report to only those findings' evidence.

Each factual claim must reference observations supplied to the model. The server resolves evidence IDs and source locators itself, checks literal identifiers, decimal values and full timestamps, then requests a separate model entailment check. Unknown citations, malformed output, unsupported claims, incomplete responses and unavailable model connections fail without publishing a partial draft. These checks reduce errors; they cannot establish factual truth or replace investigator review.

Hosted generation requires online mode and explicit sharing consent in the report builder. Extracted source text, findings, review decisions, scope and notes may be sent to the provider configured in Settings. Original uploaded files are not sent by this report endpoint. Local Ollama generation does not require hosted sharing consent.

The context is bounded and balanced across sources. The preview and export state included/total observation and source counts, plus the number of shortened observations. Detection regions, provenance records and repeated extracted mentions are excluded from the prose context where primary source text is available. An omitted or empty section is labelled insufficient source support. Image descriptions, OCR, video scenes and transcripts remain labelled model-derived and unverified.

Edit the narrative and check the investigator-review box before downloading or printing. Editing the narrative clears that confirmation. Changing the analysis, selected findings, scope, notes or loaded review decisions invalidates the generated narrative. A late response cannot restore a draft made from different inputs. Reviewers retain the existing read-only server permissions.

The export includes the narrative, scope, investigator notes, selected findings and review decisions, complete evidence manifest for the selected analysis, source hashes, analysis snapshot hash, source appendix, coverage counts, model/template details and private provenance reference. Download produces a text report; **Print / Save PDF** uses the browser print dialog. Original files and a full chain-of-custody export are not embedded.

Generation records the original model output, context, scope, notes, prompt hashes, checking results and actor in private backend provenance and adds an audit event. Investigator edits remain in the open report workspace and exported document; they are not saved back to that generation record. Export before reloading, signing out or leaving the case.

## Verification

Regenerate the OpenAPI bundle before backend and contract tests. Use the project Python environment and the pinned frontend dependencies:

```sh
node scripts/bundle-openapi.mjs specs/openapi.yaml /tmp/evora-openapi.json frontend
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts
npm --prefix frontend test
npm --prefix frontend run build
```

Set `EVORA_TEST_PYTHON` to the project interpreter and `EVORA_CONTRACT_BUNDLE` to the regenerated bundle for the full-modality, detector-feedback and deeper-processing integration scripts in `frontend/test`. Browser checks additionally require Playwright and Chrome; set `EVORA_PLAYWRIGHT_MODULE` and `EVORA_CHROME_PATH` when they are installed outside the default locations.

Frozen builds can be checked with `python scripts/smoke_release.py <executable>` and `python scripts/smoke_standalone.py <executable>`. The standalone smoke test covers encrypted storage, CSV processing, analysis without Neo4j, report generation with a model protocol double, preserved source bytes and password unlock after restart. Model protocol doubles do not establish live account or model availability.
