"""P14 private success provenance; no HTTP surface or raw-content logging."""
import hashlib
import json
import re
from uuid import UUID

from backend.auth import CaseAccessGrant
from backend.deeper_processing import CONFIG_FIELDS as DEEPER_FIELDS, deeper_metadata
from backend.entities import _valid_entity
from backend.errors import AccessError
from backend.events import _valid_event
from backend.observations import _utc_order, _valid_record

RECORD_VERSION = 'processing-provenance/1'
PROCESSOR_VERSION = 'processing-lifecycle/2'
MESSAGE_PROCESSOR_VERSION = 'processing-lifecycle/3'
DOCUMENT_PROCESSOR_VERSION = 'processing-lifecycle/4'
MOBILE_PROCESSOR_VERSION = 'processing-lifecycle/5'
TRANSACTION_PROCESSOR_VERSION = 'processing-lifecycle/6'
TRANSCRIPT_PROCESSOR_VERSION = 'transcript-correction/1'
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
          WHERE r.id=NEW.run_id AND r.status='running' AND r.processor_version IN ('processing-lifecycle/2','processing-lifecycle/3','processing-lifecycle/4','processing-lifecycle/5','processing-lifecycle/6','processing-lifecycle/7','processing-lifecycle/8','processing-lifecycle/9','processing-lifecycle/10','processing-lifecycle/11','processing-lifecycle/12','processing-lifecycle/13','processing-lifecycle/14','processing-lifecycle/15','processing-lifecycle/16','transcript-correction/1')
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
        WHEN NEW.status='completed' AND NEW.processor_version IN ('processing-lifecycle/2','processing-lifecycle/3','processing-lifecycle/4','processing-lifecycle/5','processing-lifecycle/6','processing-lifecycle/7','processing-lifecycle/8','processing-lifecycle/9','processing-lifecycle/10','processing-lifecycle/11','processing-lifecycle/12','processing-lifecycle/13','processing-lifecycle/14','processing-lifecycle/15','processing-lifecycle/16','transcript-correction/1') AND NOT EXISTS(
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
    deeper = deeper_metadata(config)
    parameters = _PARAMETERS + (('max_device_mentions',) if config.get('kind') == 'message' else ())
    processor = MESSAGE_PROCESSOR_VERSION if config.get('kind') == 'message' else PROCESSOR_VERSION
    if config.get('kind') == 'document':
        parameters = ('max_source_bytes', 'max_source_lines')
        processor = DOCUMENT_PROCESSOR_VERSION
    if config.get('kind') == 'mobile_log':
        processor = MOBILE_PROCESSOR_VERSION
    if config.get('kind') == 'transaction':
        parameters = _PARAMETERS + ('max_amount_chars',)
        processor = TRANSACTION_PROCESSOR_VERSION
    model = None
    method = 'deterministic'
    if config.get('kind') in ('image', 'video'):
        from backend.parsers.media_detection import PROCESSOR_VERSION as MEDIA_VERSION
        processor = MEDIA_VERSION if run['processor_version'] == MEDIA_VERSION else 'processing-lifecycle/8'
        parameters += ('max_frames', 'max_pixels', 'max_decoded_frames')
        model = config.get('model')
        if not isinstance(model, dict) or not model.get('cascades'):
            raise ValueError('Missing visual model provenance')
        method = 'local_opencv_haar_with_onnx_plates' if config.get('model', {}).get('plates') else 'local_opencv_haar'
    vision = config.get('image_understanding')
    video = config.get('video_understanding')
    if video is not None:
        from backend.video_understanding import validate_config as validate_video, PROCESSOR_VERSION as VIDEO_VERSION
        validate_video(video)
        if config.get('kind') != 'video' or vision is not None:
            raise ValueError('Invalid video understanding source')
        processor = run['processor_version'] if run['processor_version'] in ('processing-lifecycle/10', VIDEO_VERSION) else VIDEO_VERSION
        method = 'opencv_haar_plus_sampled_video_vision_local_speech_and_geometric_tracks'
    if vision is not None:
        from backend.image_understanding import validate_config, PROCESSOR_VERSION as VISION_VERSION
        validate_config(vision)
        if config.get('kind') != 'image':
            raise ValueError('Invalid image understanding source')
        processor = run['processor_version'] if run['processor_version'] in ('processing-lifecycle/9', VISION_VERSION) else VISION_VERSION
        method = 'opencv_haar_plus_model_image_description_and_text'
    if config.get('kind') == 'document' and run['processor_version'] in ('processing-lifecycle/7','processing-lifecycle/14'):
        processor = run['processor_version']
        parameters += ('max_source_chars', 'max_line_chars', 'max_mentions', 'ner_timeout_seconds', 'ner_workers')
        model = config.get('model')
        if (not isinstance(model, dict) or set(model) !=
                {'name', 'version', 'language', 'artifact_sha256', 'files_sha256', 'runtime'} or
                any(not isinstance(model[key], str) or not model[key] for key in ('name', 'version', 'language')) or
                any(not isinstance(model[key], str) or not re.fullmatch('[0-9a-f]{64}', model[key])
                    for key in ('artifact_sha256', 'files_sha256')) or
                not isinstance(model['runtime'], dict) or set(model['runtime']) != {'python', 'spacy', 'thinc', 'numpy'} or
                any(not isinstance(value, str) or not value for value in model['runtime'].values())):
            raise ValueError('Invalid frozen model provenance')
        method = 'local_cpu_ner_plus_rules'
    if (set(config) != set(_VERSIONS + parameters) |
            {'kind', 'sha256', 'size_bytes', 'provenance_version'} | ({'model'} if model else set()) |
            (DEEPER_FIELDS if deeper else set()) | ({'image_understanding'} if vision is not None else set()) |
            ({'video_understanding'} if video is not None else set()) | ({'source_kind'} if 'source_kind' in config else set())):
        raise ValueError('Invalid frozen provenance configuration')
    if 'source_kind' in config and (config['source_kind'] != 'document' or config['kind'] not in {'mobile_log','network_log','gps','message','transaction'}):
        raise ValueError('Invalid source interpretation')
    if (config['provenance_version'] != RECORD_VERSION or run['processor_version'] != processor
            or config['processor_version'] != run['processor_version']
            or config['kind'] not in {'network_log', 'gps', 'message', 'document', 'mobile_log', 'transaction', 'image', 'video'}
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
    if config['kind'] == 'document' and (events or config['event_version'] != 'not-used' or
            (model is None and (entities or any(config[key] != 'not-used'
                for key in ('normalizer_version', 'entity_version'))))):
        raise ValueError('Plain text processing does not normalize time or extract candidates')
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
    execution = dict(versions={key: config[key] for key in _VERSIONS},
                     parameters={key: config[key] for key in parameters}, method=method, model=model)
    if vision is not None:
        execution['image_understanding'] = vision
    if video is not None:
        execution['video_understanding'] = {**video, 'speech':
            {key:value for key,value in video['speech'].items() if key != 'path'} if video['speech'] is not None else None}
    if deeper is not None:
        execution['deeper_processing'] = deeper
    return dict(record_version=RECORD_VERSION, case_id=case_id, evidence_id=evidence_id,
        processing_run_id=run_id, input={key: config[key] for key in ('kind', 'sha256', 'size_bytes')+ (('source_kind',) if 'source_kind' in config else ())},
        execution=execution,
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
