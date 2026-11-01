"""P01 synthetic parser acceptance and real F03/F05 original integration."""
import csv
from dataclasses import FrozenInstanceError
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.parsers.network_csv import (HEADER, MAX_SOURCE_BYTES, MAX_DATA_ROWS,
    NetworkCSVError, parse_network_csv)

HEADER_BYTES = b'timestamp,device_id,ip_address,event\n'
ROW = b'2026-01-12T10:01:00Z,D-7,203.0.113.7,connected\n'
FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures/synthetic-case/network.csv'

class NetworkCSVTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(case_id=uuid4(), evidence_id=uuid4(), processing_run_id=uuid4())

    def parse(self, data):
        return parse_network_csv(data, **self.context)

    def rejects(self, source, code):
        with self.assertRaises(NetworkCSVError) as caught:
            self.parse(source)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn('SECRET', str(caught.exception))

    def test_fixture_values_locators_schema_and_unique_ids(self):
        data = FIXTURE.read_bytes()
        digest = hashlib.sha256(data).digest()
        output = self.parse(data)
        self.assertEqual(len(output), 6)
        self.assertEqual([item.raw_value for item in output], ['D-7','203.0.113.7','connected','D-9','203.0.113.9','connected'])
        self.assertEqual(output[0].source_locator, 'row 2, device_id')
        self.assertEqual(output[4].source_locator, 'row 3, ip_address')
        self.assertEqual(output[0].observed_at_raw, '2026-01-12T10:01:00Z')
        self.assertEqual(output[3].observed_at_raw, '2026-01-12T10:02:00Z')
        spec = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))
        validator = Draft202012Validator({**spec['components']['schemas']['Observation'], 'components':spec['components']},format_checker=FormatChecker())
        self.assertEqual(len({item.id for item in output}), 6)
        for item in output:
            wire = item.to_wire()
            validator.validate(wire)
            for key, value in self.context.items(): self.assertEqual(wire[key], str(value))
            self.assertEqual(item.raw_value, item.normalized_value)
            self.assertEqual(item.extraction_confidence, 0)
            self.assertNotIn('observed_at_utc', wire)
            self.assertNotIn('entity_key', wire)
        self.assertEqual(hashlib.sha256(data).digest(), digest)

    def test_immutable_results_and_wire_copies(self):
        item = self.parse(HEADER_BYTES + ROW)[0]
        with self.assertRaises(FrozenInstanceError): item.raw_value = 'modified'
        wire = item.to_wire(); wire['raw_value']='modified'
        self.assertEqual(item.raw_value, 'D-7')

    def test_bom_line_endings_and_no_final_newline(self):
        for ending in [b'\n', b'\r\n', b'\r']:
            for bom in [b'', b'\xef\xbb\xbf']:
                output = self.parse(bom + HEADER_BYTES.rstrip(b'\n') + ending + ROW.rstrip(b'\n'))
                self.assertEqual(len(output), 3)
                self.assertEqual(output[0].source_locator, 'row 2, device_id')

    def test_quoted_commas_quotes_multiline_unicode_and_ipv6_preserved(self):
        buffer=StringIO(newline=''); writer=csv.writer(buffer)
        writer.writerow(HEADER)
        values=['not-yet-normalized +05:30', ' Device,"SECRET"\r\nCandidate ', '2001:0db8::1', 'connected, "candidate"']
        writer.writerow(values)
        writer.writerow(['unknown-zone','D-8','127.0.0.1','still unverified'])
        result=self.parse(buffer.getvalue().encode('utf-8'))
        self.assertEqual(result[0].raw_value,values[1])
        self.assertEqual(result[1].raw_value,values[2])
        self.assertEqual(result[2].raw_value,values[3])
        self.assertEqual(result[0].observed_at_raw,values[0])
        self.assertEqual(result[0].source_locator,'rows 2-3, device_id')
        self.assertEqual(result[3].source_locator,'row 4, device_id')

    def test_headers_and_empty_original(self):
        self.assertEqual(self.parse(HEADER_BYTES), ())
        for source in [b'',b'\xef\xbb\xbf',HEADER_BYTES.upper()+ROW,
                       b'timestamp,device_id,ip_address,extra\n'+ROW,
                       b'device_id,timestamp,ip_address,event\n'+ROW,
                       b'timestamp,device_id,ip_address,event,event\n'+ROW,
                       b'timestamp,device_id,ip_address\n'+ROW]:
            self.rejects(source,'INVALID_HEADER')

    def test_missing_extra_and_blank_fields_and_blank_records(self):
        for row in [b'\n', b't,D,127.0.0.1\n', b't,D,127.0.0.1,e,extra\n',
                    b',D,127.0.0.1,e\n', b't,  ,127.0.0.1,e\n', b't,D,,e\n', b't,D,127.0.0.1,""\n']:
            self.rejects(HEADER_BYTES+row,'INVALID_ROW')

    def test_bad_ip_literals(self):
        for ip in ['SECRET.invalid','999.1.1.1','127.0.0.1/24',' 127.0.0.1','fe80::1%eth0','1234']:
            self.rejects(HEADER_BYTES+f't,D,{ip},e\n'.encode(),'INVALID_IP')

    def test_bad_encoding_and_quotes(self):
        self.rejects(HEADER_BYTES+b't,D,127.0.0.1,\xff','INVALID_UTF8')
        for row in [b't,D,127.0.0.1,"SECRET', b't,D,127.0.0.1,a"SECRET',
                    b't,D,127.0.0.1,"SECRET"trailing', b't,D,127.0.0.1,SECRET\x00']:
            self.rejects(HEADER_BYTES+row,'MALFORMED_CSV')

    def test_invalid_later_record_returns_no_partial_result(self):
        self.rejects(HEADER_BYTES+ROW+b't,D,SECRET,e\n','INVALID_IP')
        self.assertEqual(len(self.parse(HEADER_BYTES+ROW)),3)

    def test_byte_boundary_and_no_implicit_small_field_cap(self):
        prefix=HEADER_BYTES+b't,D,127.0.0.1,'
        data=prefix+b'x'*(MAX_SOURCE_BYTES-len(prefix))
        self.assertEqual(len(data),MAX_SOURCE_BYTES)
        result=self.parse(data)
        self.assertEqual(len(result[2].raw_value),MAX_SOURCE_BYTES-len(prefix))
        self.rejects(data+b'x','BYTE_LIMIT')

    def test_row_boundary(self):
        data=HEADER_BYTES+b't,D,127.0.0.1,e\n'*MAX_DATA_ROWS
        result=self.parse(data)
        self.assertEqual(len(result),3*MAX_DATA_ROWS)
        self.assertEqual(result[-1].source_locator,f'row {MAX_DATA_ROWS+1}, event')
        del result
        self.rejects(data+b't,D,127.0.0.1,e\n','ROW_LIMIT')

    def test_invalid_context_or_source_is_not_echoed(self):
        self.rejects('SECRET','INVALID_SOURCE')
        with self.assertRaises(NetworkCSVError) as caught:
            parse_network_csv(HEADER_BYTES,case_id='SECRET',evidence_id=uuid4(),processing_run_id=uuid4())
        self.assertEqual(caught.exception.code,'INVALID_CONTEXT')
        self.assertNotIn('SECRET',str(caught.exception))

    def test_csv_writer_generated_logical_values_roundtrip(self):
        for value in ['plain','with,comma','with"quote','with\nnewline','with\r\ncrlf',' with spaces ','Unicode '+chr(0x1f9ea)]:
            buffer=StringIO(newline='');writer=csv.writer(buffer)
            writer.writerow(HEADER);writer.writerow(['raw timestamp',value,'::1',value])
            output=self.parse(buffer.getvalue().encode())
            self.assertEqual(output[0].raw_value,value)
            self.assertEqual(output[2].raw_value,value)

class NetworkCSVOriginalIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_real_authorized_originals_and_case_isolation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            app=create_app(root/'metadata.sqlite3',storage_dir=root/'private',token_verifier=SyntheticTokenVerifier({'p01-synthetic-one':'investigator-1','p01-synthetic-two':'investigator-2'}))
            async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app),base_url='http://test',headers={'Authorization':'Bearer p01-synthetic-one'}) as client:
                case=(await client.post('/api/v1/cases',json={'title':'Synthetic P01 case'})).json()
                url=f"/api/v1/cases/{case['id']}/evidence"
                original=FIXTURE.read_bytes()
                upload=await client.post(url,data={'kind':'network_log','source_label':'Synthetic P01'},files={'file':('network.csv',original,'text/csv')})
                self.assertEqual(upload.status_code,201)
                evidence=upload.json()
                downloaded=await client.get(url+'/'+evidence['id']+'/content')
                self.assertEqual(downloaded.status_code,200)
                self.assertEqual(downloaded.content,original)
                self.assertEqual(hashlib.sha256(downloaded.content).hexdigest(),evidence['sha256'])
                # Run UUID is explicitly synthetic context; P04 has not implemented a run producer yet.
                result=parse_network_csv(downloaded.content,case_id=UUID(case['id']),evidence_id=UUID(evidence['id']),processing_run_id=uuid4())
                self.assertEqual(len(result),6)
                self.assertTrue(all(str(item.case_id)==case['id'] and str(item.evidence_id)==evidence['id'] for item in result))
                self.assertEqual((await client.get(url+'/'+evidence['id']+'/content')).content,original)
                self.assertEqual((await client.get(url+'/'+evidence['id']+'/content',headers={'Authorization':'Bearer p01-synthetic-two'})).status_code,404)
                self.assertEqual((await client.get(url+'/'+evidence['id']+'/content',headers={'Authorization':'invalid'})).status_code,401)
                with app.state.database.connect() as connection:
                    path=Path(connection.execute('SELECT storage_path FROM evidence WHERE id=?',(evidence['id'],)).fetchone()[0])
                self.assertEqual(path.read_bytes(),original)
