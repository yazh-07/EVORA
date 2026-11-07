"""Exercise a frozen standalone executable with isolated data and a model protocol double."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


class Model(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, *_args):
        pass

    def do_POST(self):
        type(self).calls += 1
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        payload=json.loads(request['messages'][1]['content'])
        if 'claims' in payload:
            result={'supported':True}
        elif 'scope' in payload:
            observation=payload['context']['observations'][0]
            result={'sections':[{'heading':heading,'claims':[] if index else [{
                'text':f"{observation['kind']} records {observation['normalized_value']}.",
                'observation_ids':[observation['id']]}]} for index,heading in enumerate([
                    'Executive summary','Recorded chronology','Evidence assessment','Uncertainties and follow-up'])]}
        else:
            result={'hypothesis':'Synthetic processing output requires investigator review.','summary':'Synthetic optional brief.'}
        body=json.dumps({'model':'standalone-protocol-test','done':True,'done_reason':'stop','message':{'content':json.dumps(result)}}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)


def main():
    binary=Path(sys.argv[1]).resolve()
    model=ThreadingHTTPServer(('127.0.0.1',0),Model)
    thread=threading.Thread(target=model.serve_forever,daemon=True);thread.start()
    child=None
    with TemporaryDirectory(prefix='evora-frozen-standalone-') as temporary:
        root=Path(temporary);database=root/'case.sqlite3'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        environment={key:value for key,value in os.environ.items() if not key.startswith('NEO4J_')}
        environment.update(EVORA_QA_PROVIDER='ollama',EVORA_QA_MODEL='standalone-protocol-test',EVORA_QA_URL=f'http://127.0.0.1:{model.server_port}')
        client=httpx.Client(base_url=origin,headers={'X-Evora-Request':'1'},timeout=60,trust_env=False)
        log=(root/'backend.log').open('ab')
        def start():
            nonlocal child
            child=subprocess.Popen([str(binary),'--no-browser','--no-tray','--port',str(port),'--database',str(database),'--storage',str(root/'evidence')],env=environment,stdout=log,stderr=subprocess.STDOUT)
            for _ in range(160):
                try:
                    response=client.get('/api/v1/auth/status')
                    if response.status_code==200:return response.json()
                except httpx.HTTPError:
                    pass
                if child.poll() is not None:raise RuntimeError('Frozen backend exited: '+(root/'backend.log').read_text(errors='replace')[-3000:])
                time.sleep(.25)
            raise RuntimeError('Frozen backend startup timed out')
        def stop():
            nonlocal child
            if child is not None and child.poll() is None:
                child.terminate();child.wait(timeout=30)
        def post(path,body=None,status=200,**options):
            response=client.post('/api/v1'+path,json=body,**options)
            assert response.status_code==status,(path,response.status_code,response.text)
            return response.json()
        def poll(path):
            for _ in range(200):
                response=client.get('/api/v1'+path);assert response.status_code==200,response.text
                run=response.json()
                if run['status'] in ('completed','failed'):
                    assert run['status']=='completed',run
                    return run
                time.sleep(.1)
            raise AssertionError('Processing did not finish')
        try:
            assert start()['setup_required'] is True
            password='synthetic native smoke passphrase'
            post('/auth/setup',{'username':'native-smoke','display_name':'Native smoke','password':password})
            assert database.read_bytes()[:16]!=b'SQLite format 3\0'
            case=post('/cases',{'title':'Standalone native smoke'},status=201)['id']
            csv=b'timestamp,device_id,ip_address,event\n2026-01-12T10:00:00Z,D-7,192.0.2.7,connected\n'
            response=client.post(f'/api/v1/cases/{case}/evidence',data={'kind':'network_log','source_label':'Synthetic gateway'},files={'file':('gateway.csv',csv,'text/csv')})
            assert response.status_code==201,response.text
            evidence=response.json()['id']
            processing=post(f'/cases/{case}/evidence/{evidence}/processing-runs',status=202,headers={'Idempotency-Key':'00000000-0000-4000-8000-000000000001'})
            poll(f"/cases/{case}/evidence/{evidence}/processing-runs/{processing['id']}")
            analysis=post(f'/cases/{case}/analysis-runs',status=202,headers={'Idempotency-Key':'00000000-0000-4000-8000-000000000002'})
            run=poll(f"/cases/{case}/analysis-runs/{analysis['id']}")
            graph=client.get(f'/api/v1/cases/{case}/graph',params={'analysis_run_id':run['id']}).json()
            assert any(edge['kind']=='assigned_ip' for edge in graph['edges']),graph
            report=post(f'/cases/{case}/reports',{'analysis_run_id':run['id'],'finding_ids':[],'scope':'Summarize recorded gateway observations','allow_remote':False})
            assert report['citations'] and report['analysis_run_id']==run['id'],report
            assert Model.calls>=2
            assert client.get(f'/api/v1/cases/{case}/evidence/{evidence}/content').content==csv
            stop()
            assert start()['database_locked'] is True
            assert client.get('/api/v1/auth/me').status_code==401
            post('/auth/login',{'username':'native-smoke','password':password})
            response=client.get(f'/api/v1/cases/{case}/graph',params={'analysis_run_id':run['id']})
            assert response.status_code==200 and response.json()==graph,response.text
            print('PASS frozen standalone: encrypted database, actual CSV processing, analysis and graph without Neo4j, model report with exact source citations (protocol double), original bytes and password unlock after restart.')
        finally:
            stop();client.close();log.close();model.shutdown();model.server_close()


if __name__=='__main__':
    main()
