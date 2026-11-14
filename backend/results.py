"""Read-only, operation-specific extraction results from immutable source outputs.

Selection is per operation: a newer detection-only output cannot hide earlier OCR
or transcripts. No config, model paths, credentials or private provenance is exposed.
"""
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from backend.audit import _PROCESSING_ERRORS
from backend.auth import CaseAccessGrant, require_case_access
from backend.evidence import invalid_input
from backend.observations import _not_found, _utc_order, _valid_record

router = APIRouter()
Operation = Literal['detection', 'description', 'ocr', 'transcript', 'records', 'plates']
OPERATIONS = ('detection', 'description', 'ocr', 'transcript', 'records', 'plates')


def operation_for(kind):
    if kind in ('image.plate_reading', 'video.plate_reading'):
        return 'plates'
    if kind in ('image.detection', 'video.frame_detection'):
        return 'detection'
    if kind in ('image.description', 'video.scene'):
        return 'description'
    if kind in ('image.ocr', 'video.ocr'):
        return 'ocr'
    if kind.startswith('transcript.'):
        return 'transcript'
    if kind.endswith(('.provenance', '.limitations', '.track')):
        return None
    return 'records'


def declared_operations(config, evidence_kind):
    # Transcript corrections retain the complete source output and its frozen config.
    if config.get('materializer_version'):
        return declared_operations(config.get('original_config', {}), evidence_kind) | {'transcript'}
    kind = config.get('kind')
    if kind in ('image', 'video'):
        operations = {'detection'}
        if config.get('model', {}).get('plates'):
            operations.add('plates')
        if config.get('image_understanding') or config.get('video_understanding'):
            operations |= {'description', 'ocr'}
        if config.get('video_understanding', {}).get('speech'):
            operations.add('transcript')
        return operations
    if kind in ('document', 'network_log', 'mobile_log', 'gps', 'message', 'transaction'):
        return {'records'}
    # Unknown/legacy configurations are not evidence that a task was attempted.
    return set()


def _read_output(connection, run, case_id, evidence_id):
    row = connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone()
    if row is None or (row['case_id'], row['evidence_id']) != (case_id, evidence_id):
        raise _not_found()
    try:
        items = json.loads(row['observations_json'])
        if not isinstance(items, list) or any(not _valid_record(json.dumps(item), case_id, evidence_id, run['id']) for item in items):
            raise ValueError()
        if len({item['id'].lower() for item in items}) != len(items):
            raise ValueError()
        return items
    except (ValueError, TypeError, KeyError):
        raise _not_found() from None


def _coverage(items, operation):
    notes = []
    for item in items:
        if item['kind'] in ('image.limitations', 'video.limitations') and operation in ('description', 'ocr'):
            if item['raw_value'].strip():
                notes.append(item['raw_value'])
        if item['kind'] == 'video.provenance':
            try:
                metadata = json.loads(item['raw_value'])
                samples = metadata.get('sampled_frames')
                if isinstance(samples, list) and operation in ('description', 'ocr'):
                    notes.append(f'{len(samples)} sampled frames; events between samples may be missed.')
                if operation == 'transcript' and isinstance(metadata.get('speech'), dict):
                    language = metadata['speech'].get('language')
                    if isinstance(language, str):
                        notes.append(f'Reported language: {language}')
            except (ValueError, AttributeError, TypeError):
                notes.append('Coverage metadata unavailable.')
    if operation == 'plates':
        notes.append('Local plate OCR candidates. Read scores are not calibrated probabilities; verify against the original crop.')
    if operation == 'detection':
        notes.append('Candidate detections only. Identity unknown; repeated boxes are not unique people.')
    if not notes:
        notes.append('Coverage not recorded.' if operation != 'records' else 'Extracted fields; multiple fields may belong to one source row.')
    return list(dict.fromkeys(notes))


@router.get('/api/v1/cases/{caseId}/evidence/{evidenceId}/results', operation_id='getEvidenceResults')
def evidence_results(caseId: UUID, evidenceId: UUID, request: Request,
                     grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
                     operation: Operation | None = None, processing_run_id: UUID | None = None,
                     limit: Annotated[int, Query(ge=1, le=100)] = 50,
                     offset: Annotated[int, Query(ge=0)] = 0):
    if any(key not in {'operation', 'processing_run_id', 'limit', 'offset'} or len(request.query_params.getlist(key)) != 1
           for key in request.query_params):
        raise invalid_input()
    case_id, evidence_id = str(grant.case_id), str(evidenceId)
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN')
        evidence = connection.execute('SELECT kind FROM evidence WHERE id=? AND case_id=?', (evidence_id, case_id)).fetchone()
        if evidence is None:
            raise _not_found()
        runs = connection.execute('SELECT * FROM processing_runs WHERE case_id=? AND evidence_id=?', (case_id, evidence_id)).fetchall()
        if processing_run_id:
            runs = [run for run in runs if run['id'] == str(processing_run_id) and run['status'] == 'completed']
            if not runs:
                raise _not_found()
        if any(_utc_order(run['created_at']) is None or (run['finished_at'] and _utc_order(run['finished_at']) is None) for run in runs):
            raise _not_found()
        runs = sorted(runs, key=lambda run: (_utc_order(run['finished_at'] or run['created_at']) or '', run['id']), reverse=True)
        latest, completed, outputs = {}, {}, {}
        for run in runs:
            try:
                config = json.loads(run['config_json'])
                if not isinstance(config, dict):
                    raise ValueError()
                declared = declared_operations(config, evidence['kind'])
            except (ValueError, TypeError, AttributeError):
                raise _not_found() from None
            items = _read_output(connection, run, case_id, evidence_id) if run['status'] == 'completed' else []
            # Actual validated output can establish an operation for legacy configurations.
            declared |= {op for item in items if (op := operation_for(item['kind'])) is not None}
            for op in declared:
                previous = latest.get(op)
                if previous is None or ((_utc_order(run['created_at']) or '', run['id']) > (_utc_order(previous['created_at']) or '', previous['id'])):
                    latest[op] = run
                if run['status'] == 'completed' and op not in completed:
                    completed[op] = run
                    outputs[op] = items
        available = ('detection', 'description', 'ocr') if evidence['kind'] == 'image' else (
            ('detection', 'description', 'ocr', 'transcript') if evidence['kind'] == 'video' else (
                ('transcript',) if evidence['kind'] == 'audio' else ('records',)))
        if operation and operation not in available and operation not in latest:
            raise invalid_input()
        operations = []
        for op in OPERATIONS:
            if op not in available and op not in latest:
                continue
            attempt, result = latest.get(op), completed.get(op)
            selected_items = [item for item in outputs.get(op, []) if operation_for(item['kind']) == op]
            manifest = dict(operation=op, status=attempt['status'] if attempt else ('unsupported' if evidence['kind'] == 'audio' else 'not_run'),
                            count=len(selected_items) if result else None, output_run_id=result['id'] if result else None,
                            latest_run_id=attempt['id'] if attempt else None, updated_at=result['finished_at'] if result else None,
                            notes=_coverage(outputs[op], op) if result else [])
            if attempt and attempt['status'] == 'failed':
                manifest['error'] = attempt['error'] if attempt['error'] in _PROCESSING_ERRORS else 'PROCESSING_FAILED'
            operations.append(manifest)
        # Open useful content rather than an empty detection output. Explicit
        # operation and historical-output selectors still take precedence.
        preferred = ('description', 'ocr', 'plates', 'detection', 'transcript', 'records')
        populated = {entry['operation'] for entry in operations if entry['output_run_id'] and entry['count']}
        chosen = operation or next((op for op in preferred if op in populated),
            next((entry['operation'] for entry in operations if entry['output_run_id']), operations[0]['operation']))
        items = sorted((item for item in outputs.get(chosen, []) if operation_for(item['kind']) == chosen),
                       key=lambda item: (item['source_locator'], item['kind'], item['id']))
        result = dict(case_id=case_id, evidence_id=evidence_id, operations=operations, operation=chosen,
                      items=items[offset:offset + limit], total=len(items), limit=limit, offset=offset)
    return JSONResponse(result, headers={'Cache-Control': 'no-store'})
