# API and persistence contracts

`specs/openapi.yaml` defines the HTTP schemas and operation IDs. `frontend/src/api/schema.d.ts` is generated from it; update declarations with `npm --prefix frontend run generate:api` and check freshness with `npm --prefix frontend run check:api`.

- Case-scoped routes enforce access before returning evidence or derived records. Inaccessible resources use concealed not-found responses.
- Original evidence bytes and recorded hashes are preserved. Extraction and correction history use new immutable outputs rather than replacing originals.
- Processing and analysis starts use idempotency keys. An ambiguous network result must not silently submit new work with a different key.
- Analysis inputs freeze evidence, observations and processing-run references. Historical views retain their completed analysis/output selectors across pagination.
- SQL output persistence precedes graph projection and verification. Pending or failed graph partitions do not become completed analysis results.
- Source citations identify the case, evidence, processing output and locator. Transcript corrections retain revision references.
- Model scores and candidate relationships do not establish physical identity or verified conclusions. Model output must retain source provenance and review context.

Runtime implementation and tests establish behavior; a declared schema alone does not establish that every operation is implemented.
