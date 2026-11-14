# Architecture

The React workspace communicates with FastAPI over the loopback HTTP API. The backend owns database access, evidence storage and processing. The API schemas are defined in `specs/openapi.yaml`.

## Persistence

SQLite is authoritative for local accounts, case access, evidence metadata, immutable extraction outputs, analysis snapshots, findings, review and audit history. Original evidence bytes are preserved separately with recorded hashes. Account-password encryption protects SQLite; original files and the derived graph have separate filesystem protection.

Neo4j stores versioned graph partitions identified by case and analysis run. Graph projection is rebuildable from persisted outputs. A completed analysis is published only after graph/source coherence checks succeed.

## Processing

Uploads are stored before extraction is explicitly requested. Each processing run records its method and output provenance. Reprocessing creates a new run rather than rewriting historical output. Structured parsers, local text extraction and image/video detection produce source-located observations. Optional model operations use the configured provider and sharing controls.

## Desktop runtime

The Windows desktop supervisor owns the backend lifecycle. The backend manages the bundled Java/Neo4j process, authenticates over a private loopback port and keeps graph data outside the installation directory. Source and Linux deployments can use an external Neo4j service.

## Workspace

Case views cover overview, evidence, timeline, locations, findings and reports. Source inspection retains original-file references and exact historical output selectors. Maps combine reported GPS and labeled approximate place mentions; online basemaps are separate from model-provider settings.

See [contracts](CONTRACTS.md), [bundled graph](bundled-graph.md), [database encryption](database-encryption.md) and [model reports](model-reports.md).
