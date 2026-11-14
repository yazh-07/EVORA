# Model use and evidence grounding

Model requests use the provider selected in Settings. **Local models only** blocks hosted inference. Hosted image and video processing requires confirmation of the destination and model. Connecting a provider or fetching its model catalog does not transmit evidence.

## Case Q&A

Retrieval uses the authorized case and its selected completed analysis snapshot. Context can include source observations, candidate graph relationships, findings and triage factors. References retain their evidence, processing-run and source-locator identifiers.

Answers must pass citation and grounding checks before publication. Unsupported questions return an unsupported result. Valid citations identify the supplied source; they do not establish that a model's interpretation is correct. Candidate associations and model scores do not establish identity or guilt.

Private Q&A provenance records the retrieval inputs, prompt/model information and verification results. Public audit records use action and resource references rather than raw questions, answers or evidence text.

## Data handling

Original evidence remains in the local vault. Hosted processing transmits the content needed for the selected operation to the configured provider. Retention and account terms depend on that provider; EVORA cannot guarantee a provider's handling of submitted data.

Protect the workstation, database, vault, graph and provider credentials with operating-system access controls. See [ChatGPT connection](chatgpt-connection.md), [image processing](image-description-and-ocr.md) and [security and limitations](THREAT_PROVENANCE_LIMITATIONS.md).
