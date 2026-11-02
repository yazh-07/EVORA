"""P14 private success provenance; no HTTP surface or raw-content logging."""
import hashlib
import json
import re
from uuid import UUID

from backend.auth import CaseAccessGrant
from backend.entities import _valid_entity
from backend.errors import AccessError
from backend.events import _valid_event
from backend.observations import _utc_order, _valid_record

RECORD_VERSION = 'processing-provenance/1'
PROCESSOR_VERSION = 'processing-lifecycle/2'
MESSAGE_PROCESSOR_VERSION = 'processing-lifecycle/3'
_OUTPUT_FIELDS = ('observations_json', 'entities_json', 'events_json', 'uncertainty_json')
_VERSIONS = ('parser_version', 'normalizer_version', 'entity_version', 'event_version', 'processor_version')
_PARAMETERS = ('max_source_bytes', 'max_data_rows')


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def initialize_provenance(connection):
    """Add empty private storage; never invent historical execution records."""
    connection.executescript("""
      BEGIN IMMEDIATE;
      CREATE TABLE IF NOT EXISTS processing_provenance (
        run_id TEXT PRIMARY KEY REFERENCES processing_runs(id),
        case_id TEXT NOT NULL REFERENCES cases(id), evidence_id TEXT NOT NULL REFERENCES evidence(id),
        record_version TEXT NOT NULL, finished_at TEXT NOT NULL, payload_json TEXT NOT NULL
      ) WITHOUT ROWID;
      DROP TRIGGER IF EXISTS processing_provenance_context;
      CREATE TRIGGER processing_provenance_context BEFORE INSERT ON processing_provenance
        WHEN NOT EXISTS(SELECT 1 FROM processing_runs r JOIN processing_outputs o ON o.run_id=r.id
          WHERE r.id=NEW.run_id AND r.status='running' AND r.processor_version IN ('processing-lifecycle/2','processing-lifecycle/3')
          AND r.case_id=NEW.case_id AND r.evidence_id=NEW.evidence_id
          AND o.case_id=r.case_id AND o.evidence_id=r.evidence_id)
        BEGIN SELECT RAISE(ABORT,'Invalid processing provenance context'); END;
      CREATE TRIGGER IF NOT EXISTS processing_provenance_no_update BEFORE UPDATE ON processing_provenance
        BEGIN SELECT RAISE(ABORT,'Immutable processing provenance'); END;
      CREATE TRIGGER IF NOT EXISTS processing_provenance_no_delete BEFORE DELETE ON processing_provenance
        BEGIN SELECT RAISE(ABORT,'Immutable processing provenance'); END;
      CREATE TRIGGER IF NOT EXISTS processing_provenance_no_replace BEFORE INSERT ON processing_provenance
        WHEN EXISTS(SELECT 1 FROM processing_provenance WHERE run_id=NEW.run_id)
        BEGIN SELECT RAISE(ABORT,'Immutable processing provenance'); END;
      DROP TRIGGER IF EXISTS processing_completion_provenance;
      CREATE TRIGGER processing_completion_provenance BEFORE UPDATE OF status ON processing_runs
        WHEN NEW.status='completed' AND NEW.processor_version IN ('processing-lifecycle/2','processing-lifecycle/3') AND NOT EXISTS(
          SELECT 1 FROM processing_provenance p WHERE p.run_id=NEW.id AND p.case_id=NEW.case_id
          AND p.evidence_id=NEW.evidence_id AND p.record_version='processing-provenance/1'
          AND p.finished_at=NEW.finished_at)
        BEGIN SELECT RAISE(ABORT,'Missing processing provenance'); END;
      COMMIT;
    """)


def _canonical(identifier):
    return str(UUID(identifier))


def _payload(run, output, finished_at):
    """Validate private context and derive manifests from actual persisted wire.

    Digest covers the exact UTF-8 JSON strings of all four stored output columns,
    framed as a canonical JSON object. It is integrity linkage, not authentication.
    No source text/locators, paths, actor credentials or raw idempotency keys enter
    the record; output contents remain in their existing private output store.
    """
    config = json.loads(run['config_json'])
    if not isinstance(config, dict): raise ValueError('Invalid frozen provenance configuration')
    parameters = _PARAMETERS + (('max_device_mentions',) if config.get('kind') == 'message' else ())
    processor = MESSAGE_PROCESSOR_VERSION if config.get('kind') == 'message' else PROCESSOR_VERSION
    if (set(config) != set(_VERSIONS + parameters) |
            {'kind', 'sha256', 'size_bytes', 'provenance_version'}):
        raise ValueError('Invalid frozen provenance configuration')
    if (config['provenance_version'] != RECORD_VERSION or run['processor_version'] != processor
            or config['processor_version'] != run['processor_version']
            or config['kind'] not in {'network_log', 'gps', 'message'}
            or any(not isinstance(config[key], str) or not config[key] for key in _VERSIONS)
            or not isinstance(config['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', config['sha256'])
            or type(config['size_bytes']) is not int or config['size_bytes'] < 0
            or any(type(config[key]) is not int or config[key] < 1 for key in parameters)
            or _utc_order(finished_at) is None or _utc_order(run['created_at']) is None):
        raise ValueError('Invalid frozen provenance values')
    case_id, evidence_id, run_id = run['case_id'], run['evidence_id'], run['id']
    for identifier in (case_id, evidence_id, run_id):
        if _canonical(identifier) != identifier:
            raise ValueError('Invalid provenance context')
    if len(output) != 4 or any(not isinstance(value, str) for value in output):
        raise ValueError('Invalid provenance output')
    observations, entities, events, uncertainty = [json.loads(value) for value in output]
    if any(not isinstance(values, list) for values in (observations, entities, events, uncertainty)):
        raise ValueError('Invalid provenance output arrays')
    if config['kind'] == 'message' and events:
        raise ValueError('Message candidate processing does not extract Events')
    manifests = {}
    for name, records, validator in (
            ('observation_ids', observations, lambda raw: _valid_record(raw, case_id, evidence_id, run_id)),
            ('entity_ids', entities, lambda raw: _valid_entity(raw, case_id, evidence_id)),
            ('event_ids', events, lambda raw: _valid_event(raw, case_id, evidence_id))):
        if any(not validator(_json(record)) for record in records):
            raise ValueError('Invalid provenance output records')
        ids = [record['id'] for record in records]
        if len(set(map(_canonical, ids))) != len(ids):
            raise ValueError('Duplicate provenance output references')
        manifests[name] = sorted(ids, key=_canonical)
    # This run publishes one original's outputs. Verify exact same-run source joins.
    by_id = {_canonical(record['id']): record for record in observations}
    entity_sources = {}
    for record in entities + events:
        refs = {_canonical(x) for x in record['observation_ids']}
        if not refs <= by_id.keys() or {_canonical(x) for x in record['evidence_ids']} != {evidence_id}:
            raise ValueError('Invalid provenance source references')
        if 'candidate_key' in record:
            if any('entity_key' in by_id[oid] and by_id[oid]['entity_key'] != record['candidate_key'] for oid in refs):
                raise ValueError('Invalid provenance candidate key')
            entity_sources[_canonical(record['id'])] = refs
    for event in events:
        refs = {_canonical(x) for x in event['observation_ids']}
        if any(not (entity_sources.get(_canonical(eid), set()) & refs) for eid in event['entity_ids']):
            raise ValueError('Invalid provenance participant references')
    digest = hashlib.sha256(_json(dict(zip(_OUTPUT_FIELDS, output))).encode('utf-8')).hexdigest()
    return dict(record_version=RECORD_VERSION, case_id=case_id, evidence_id=evidence_id,
        processing_run_id=run_id, input={key: config[key] for key in ('kind', 'sha256', 'size_bytes')},
        execution=dict(versions={key: config[key] for key in _VERSIONS},
                       parameters={key: config[key] for key in parameters}, method='deterministic', model=None),
        outputs=manifests, output_sha256=digest, accepted_at=run['created_at'], finished_at=finished_at)


def record_processing_provenance(connection, run, output, finished_at):
    """Insert in caller's publication transaction; never commit separately."""
    payload = _payload(run, output, finished_at)
    connection.execute('INSERT INTO processing_provenance VALUES (?,?,?,?,?,?)',
        (run['id'], run['case_id'], run['evidence_id'], RECORD_VERSION, finished_at, _json(payload)))


def read_processing_provenance(app, grant: CaseAccessGrant, evidence_id: UUID, run_id: UUID):
    """Internal authorized reader, deliberately absent from the public HTTP API."""
    def unavailable():
        return AccessError(404, 'NOT_FOUND', 'Resource not found.')
    if (not isinstance(grant, CaseAccessGrant) or not isinstance(evidence_id, UUID) or not isinstance(run_id, UUID)
            or not app.state.case_access.allows(grant.actor.id, grant.case_id)):
        raise unavailable()
    with app.state.database.connect() as connection:
        connection.execute('BEGIN')
        run = connection.execute('SELECT r.* FROM processing_runs r JOIN evidence e '
            'ON e.id=r.evidence_id AND e.case_id=r.case_id WHERE r.id=? AND r.case_id=? AND r.evidence_id=?',
            (str(run_id), str(grant.case_id), str(evidence_id))).fetchone()
        if run is None or run['status'] != 'completed':
            raise unavailable()
        record = connection.execute('SELECT * FROM processing_provenance WHERE run_id=?', (str(run_id),)).fetchone()
        output = connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (str(run_id),)).fetchone()
        if record is None or output is None:
            raise unavailable()
        if any(row['case_id'] != str(grant.case_id) or row['evidence_id'] != str(evidence_id) for row in (record, output)):
            raise unavailable()
        try:
            expected = _payload(run, tuple(output[key] for key in _OUTPUT_FIELDS), run['finished_at'])
            # Compare canonical serialized JSON as well as context: Python bool/int
            # equality must not accept a corrupt true in place of integer 1.
            if (record['record_version'] != RECORD_VERSION or record['finished_at'] != run['finished_at']
                    or _json(json.loads(record['payload_json'])) != _json(expected)):
                raise ValueError('Invalid private provenance')
        except (ValueError, TypeError, KeyError):
            raise unavailable() from None
    return expected
