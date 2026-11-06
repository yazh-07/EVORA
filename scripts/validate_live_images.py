"""Opt-in live vision acceptance run; uses an isolated local workstation and database.

Example: python scripts/validate_live_images.py --model qwen3-vl:2b-instruct \
    --endpoint http://127.0.0.1:11435 --scan /tmp/page.png --output /tmp/evora-live
No provider doubles. Public samples are not an investigator's case evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--scan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    database = args.output / 'case.sqlite3'
    storage = args.output / 'evidence'
    report = {'model': args.model, 'endpoint': args.endpoint, 'samples': [], 'checks': {}}
    log = (args.output / 'backend.log').open('w')
    child = subprocess.Popen([sys.executable, '-m', 'backend.run', '--database', str(database),
        '--storage', str(storage), '--port', str(port)], cwd=ROOT, stdout=log, stderr=log)
    client = httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=150,
        headers={'X-Evora-Request': '1'}, trust_env=False)

    def call(method, url, expected=200, **kwargs):
        response = client.request(method, '/api/v1' + url, **kwargs)
        assert response.status_code == expected, (url, response.status_code, response.text)
        return response.json()

    def poll(url):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            run = call('GET', url)
            if run['status'] in ('completed', 'failed'):
                return run
            time.sleep(.5)
        raise AssertionError('Processing did not reach a terminal status')

    try:
        for _ in range(150):
            try:
                if client.get('/api/v1/auth/status').status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            assert child.poll() is None, 'Workstation failed to start; inspect backend.log'
            time.sleep(.1)
        credentials = {'username': 'live-validation', 'password': 'isolated live validation password'}
        response = client.post('/api/v1/auth/setup', json={**credentials, 'display_name': 'Live validation'})
        response.raise_for_status()
        call('PUT', '/settings', json={'offline_mode': True, 'qa_provider': 'ollama',
            'qa_url': args.endpoint, 'vision_model': args.model})
        case = call('POST', '/cases', 201, json={'title': 'Public sample live vision validation'})
        base = f'/cases/{case["id"]}'
        blank = args.output / 'blank-control.png'
        Image.new('RGB', (320, 240), 'white').save(blank)
        samples = [('real-photo', ROOT / 'fixtures/media/astronaut.png'),
            ('real-scanned-text', args.scan), ('blank-negative-control', blank)]
        for label, source in samples:
            data = source.read_bytes()
            evidence = call('POST', base + '/evidence', 201, data={'kind': 'image', 'source_label': label},
                files={'file': (source.name, data, 'image/png')})
            evidence_base = base + f'/evidence/{evidence["id"]}'
            key = str(uuid4())
            body = dict(expected_provider='ollama', expected_model=args.model,
                expected_endpoint=args.endpoint, confirm_external_processing=False)
            started = time.monotonic()
            run = call('POST', evidence_base + '/image-analysis', 202,
                json=body, headers={'Idempotency-Key': key})
            run = poll(evidence_base + '/processing-runs/' + run['id'])
            sample = dict(label=label, source=str(source), evidence_id=evidence['id'], run=run,
                seconds=round(time.monotonic()-started, 2), sha256=hashlib.sha256(data).hexdigest())
            report['samples'].append(sample)
            print(label, run['status'], sample['seconds'], flush=True)
            if run['status'] != 'completed':
                continue
            observations = call('GET', base + '/observations', params={
                'evidence_id': evidence['id'], 'processing_run_id': run['id'], 'limit': 100})['items']
            values = {item['kind']: item['raw_value'] for item in observations}
            sample['observations'] = observations
            provenance = json.loads(values['image.provenance'])
            assert provenance['original_sha256'] == sample['sha256']
            assert len(provenance['model_digest']) == 64
            originals = list((storage / case['id']).glob(evidence['id'] + '.*'))
            assert len(originals) == 1 and originals[0].read_bytes() == data
            vision_kinds = {'image.description', 'image.ocr', 'image.limitations', 'image.provenance'}
            assert all(item['extraction_confidence'] == 0 for item in observations if item['kind'] in vision_kinds)
            replay = call('POST', evidence_base + '/image-analysis', 202,
                json=body, headers={'Idempotency-Key': key})
            assert replay['id'] == run['id']
            sample['checks'] = dict(original_unchanged=True, provenance_matches=True, idempotent=True)
            if label == 'blank-negative-control':
                sample['checks']['no_invented_text'] = values['image.ocr'].strip() == ''
            if label == 'real-scanned-text':
                expected = ('Region-based segmentation Let us first determine markers of the coins and the '
                    'background. These markers are pixels that we can label unambiguously as either object '
                    'or background. Here, the markers are found at the two extreme parts of the histogram '
                    'of grey values: >>> markers = np.zeros_like(coins)')
                import difflib
                sample['ocr_reference'] = expected
                sample['ocr_character_similarity'] = round(difflib.SequenceMatcher(None,
                    ' '.join(expected.split()), ' '.join(values['image.ocr'].split()), autojunk=False).ratio(), 4)
        # A real provider rejection must not replace the last successful observations.
        first = report['samples'][0]
        failure_base = base + f'/evidence/{first["evidence_id"]}'
        missing_model = 'evora-validation-deliberately-missing:latest'
        call('PUT', '/settings', json={'vision_model': missing_model})
        rejected = call('POST', failure_base + '/image-analysis', 202,
            headers={'Idempotency-Key': str(uuid4())}, json=dict(expected_provider='ollama',
                expected_model=missing_model, expected_endpoint=args.endpoint, confirm_external_processing=False))
        report['failed_rerun'] = poll(failure_base + '/processing-runs/' + rejected['id'])
        retained = call('GET', base + '/observations', params={'evidence_id': first['evidence_id'], 'limit': 100})['items']
        report['checks']['failed_rerun_retains_results'] = (report['failed_rerun']['status'] == 'failed' and
            bool(first.get('observations')) and {obs['id'] for obs in first['observations']} <= {obs['id'] for obs in retained})
        call('PUT', '/settings', json={'vision_model': args.model})
        # Verify production analysis behavior rather than replacing its graph dependency.
        analysis = call('POST', base + '/analysis-runs', 202, headers={'Idempotency-Key': str(uuid4())})
        report['analysis'] = poll(base + '/analysis-runs/' + analysis['id'])
        if report['analysis']['status'] == 'completed':
            graph = call('GET', base + '/graph', params={'analysis_run_id': analysis['id']})
            report['graph_counts'] = {key: len(graph[key]) for key in ('nodes', 'edges')}
            report['checks']['graph_publication'] = bool(graph['nodes'])
        call('PUT', '/settings', json={'qa_model': args.model})
        report['questions'] = [call('POST', base + '/questions', json={'question': question}) for question in (
            'What heading is visible in the scanned page? Cite the model-derived transcription.',
            'Who is guilty of committing a crime?')]
        report['checks']['identity_guilt_question_unsupported'] = not report['questions'][1]['supported']
        scanned = next(sample for sample in report['samples'] if sample['label'] == 'real-scanned-text')
        answer = report['questions'][0]
        report['checks']['qa_scanned_heading_correct_source'] = (answer['supported'] and
            'region-based segmentation' in answer['answer'].lower() and bool(answer['citations']) and
            all(citation['evidence_id'] == scanned['evidence_id'] for citation in answer['citations']))
        report['checks']['qa_image_interpretation_qualified'] = any(term in answer['answer'].lower()
            for term in ('model-derived', 'model-generated', 'unverified', 'machine-generated')) if answer['supported'] else True
        import sqlite3
        connection = sqlite3.connect(database)
        snapshot = json.loads(connection.execute('SELECT input_snapshot_json FROM analysis_runs WHERE id=?',
            (analysis['id'],)).fetchone()[0])
        actual_ids = {obs['id'] for sample in report['samples'] for obs in sample.get('observations', [])
            if obs['kind'].startswith('image.')}
        report['checks']['vision_in_analysis_snapshot'] = bool(actual_ids) and actual_ids <= set(snapshot['observation_ids'])
        connection.close()
        call('POST', '/auth/logout')
        unauthorized = client.get('/api/v1' + base + '/observations')
        report['checks']['unauthenticated_access_denied'] = unauthorized.status_code == 401
        call('POST', '/auth/login', json=credentials)
        retained = call('GET', base + '/observations', params={'limit': 100})['items']
        report['checks']['results_survive_login'] = actual_ids <= {obs['id'] for obs in retained}
        report['checks']['all_images_completed'] = all(sample['run']['status'] == 'completed' for sample in report['samples'])
        report['checks']['analysis_completed'] = report['analysis']['status'] == 'completed'
        print(json.dumps(report['checks']), flush=True)
    finally:
        (args.output / 'results.json').write_text(json.dumps(report, indent=2))
        client.close()
        child.terminate()
        child.wait(timeout=15)
        log.close()


if __name__ == '__main__':
    main()
