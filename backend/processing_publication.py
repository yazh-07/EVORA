"""P14C verify persisted SQL/private provenance before publishing completion."""
from backend.processing_provenance import RECORD_VERSION, _json, _payload

_OUTPUT_FIELDS = ('observations_json', 'entities_json', 'events_json', 'uncertainty_json')
_FROZEN_FIELDS = ('id', 'case_id', 'evidence_id', 'actor_id', 'key_digest', 'fingerprint',
                  'config_json', 'processor_version', 'created_at')


def verify_publication(connection, run, prepared_output, finished_at):
    """Read our actual transaction's writes; never commit or publish here.

    Exact string comparison covers all private output bytes, including uncertainty.
    Reconstructing P14 from SQL validates wire/source/participant joins and digest,
    rather than trusting an in-memory producer or successful INSERT invocation.
    """
    def invalid():
        return ValueError('Unverified processing publication')
    if not connection.in_transaction:
        raise invalid()
    stored_run = connection.execute('SELECT r.* FROM processing_runs r JOIN evidence e '
        'ON e.id=r.evidence_id AND e.case_id=r.case_id WHERE r.id=?', (run['id'],)).fetchone()
    output = connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone()
    private = connection.execute('SELECT * FROM processing_provenance WHERE run_id=?', (run['id'],)).fetchone()
    if stored_run is None or output is None or private is None:
        raise invalid()
    if (stored_run['status'] != 'running' or stored_run['finished_at'] is not None or stored_run['error'] is not None
            or any(stored_run[key] != run[key] for key in _FROZEN_FIELDS)
            or any(row['case_id'] != run['case_id'] or row['evidence_id'] != run['evidence_id'] for row in (output, private))):
        raise invalid()
    stored_output = tuple(output[key] for key in _OUTPUT_FIELDS)
    if stored_output != tuple(prepared_output):
        raise invalid()
    expected = _payload(stored_run, stored_output, finished_at)
    if (private['record_version'] != RECORD_VERSION or private['finished_at'] != finished_at
            or private['payload_json'] != _json(expected)):
        raise invalid()
