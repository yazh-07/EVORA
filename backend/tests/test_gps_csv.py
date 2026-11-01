"""P02 synthetic GPS acceptance and real authorized original integration."""
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
from backend.parsers.gps_csv import (HEADER, MAX_SOURCE_BYTES, MAX_DATA_ROWS,
                                    GPSCSVError, parse_gps_csv)

HEADER_BYTES = b'timestamp,device_id,latitude,longitude\n'
ROW = b'2026-01-12T10:02:00Z,D-8,12.9716,77.5946\n'
FIXTURE = Path(__file__).resolve().parents[2]/'fixtures/synthetic-case/gps.csv'

class GPSCSVTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(case_id=uuid4(), evidence_id=uuid4(), processing_run_id=uuid4())

    def parse(self, source):
        return parse_gps_csv(source, **self.context)

    def row(self, timestamp='2026-01-12T10:02:00Z', device='D-8', latitude='12.9716', longitude='77.5946'):
        buffer=StringIO(newline='');writer=csv.writer(buffer)
        writer.writerow(HEADER);writer.writerow([timestamp,device,latitude,longitude])
        return buffer.getvalue().encode()

    def rejects(self, source, code, line=None):
        with self.assertRaises(GPSCSVError) as caught: self.parse(source)
        self.assertEqual(caught.exception.code,code)
        if line is not None: self.assertEqual(caught.exception.line,line)
        self.assertNotIn('SECRET',str(caught.exception))
        self.assertNotIn('Network CSV',str(caught.exception))

    def test_fixture_schema_context_raw_values_and_locations(self):
        source=FIXTURE.read_bytes();digest=hashlib.sha256(source).digest()
        output=self.parse(source)
        self.assertEqual(len(output),3)
        self.assertEqual([x.raw_value for x in output],['D-8','12.9716','77.5946'])
        self.assertEqual([x.kind for x in output],['gps.device','gps.latitude','gps.longitude'])
        self.assertEqual([x.source_locator for x in output],['row 2, device_id','row 2, latitude','row 2, longitude'])
        self.assertEqual(len({x.id for x in output}),3)
        spec=json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))
        validator=Draft202012Validator({**spec['components']['schemas']['Observation'],'components':spec['components']},format_checker=FormatChecker())
        for item in output:
            wire=item.to_wire();validator.validate(wire)
            for key,value in self.context.items():self.assertEqual(wire[key],str(value))
            self.assertEqual(item.raw_value,item.normalized_value)
            self.assertEqual(item.observed_at_raw,'2026-01-12T10:02:00Z')
            self.assertEqual(item.extraction_confidence,0)
            self.assertNotIn('observed_at_utc',wire);self.assertNotIn('entity_key',wire)
        self.assertEqual(hashlib.sha256(source).digest(),digest)

    def test_results_and_wire_copies_are_immutable(self):
        item=self.parse(HEADER_BYTES+ROW)[0]
        with self.assertRaises(FrozenInstanceError):item.raw_value='changed'
        wire=item.to_wire();wire['raw_value']='changed'
        self.assertEqual(item.raw_value,'D-8')

    def test_bom_endings_and_missing_final_newline(self):
        for ending in [b'\n',b'\r\n',b'\r']:
            for bom in [b'',b'\xef\xbb\xbf']:
                result=self.parse(bom+HEADER_BYTES.rstrip(b'\n')+ending+ROW.rstrip(b'\n'))
                self.assertEqual(result[0].source_locator,'row 2, device_id')
                self.assertEqual(len(result),3)

    def test_coordinate_boundaries_and_signed_zero(self):
        for lat,lon in [('90','180'),('-90','-180'),('+90.000','+180.000'),('-0.000','0e3'),('.5','-1.8e2')]:
            result=self.parse(self.row(latitude=lat,longitude=lon))
            self.assertEqual(result[1].raw_value,lat);self.assertEqual(result[2].raw_value,lon)

    def test_nonfinite_out_of_range_and_nondecimal_coordinates(self):
        for value in ['NaN','Infinity','-Infinity','SECRET','0x10','1_0','12,3',' 12.3','12.3 ','1e999999999999999999999','90.0000000000000000000000000000001','-90.00000000000000000000000001']:
            self.rejects(self.row(latitude=value),'INVALID_COORDINATE',2)
        for value in ['180.00000000000000000001','-180.00000000000000000001','NaN','999']:
            self.rejects(self.row(longitude=value),'INVALID_COORDINATE',2)

    def test_missing_timezone_remains_unknown_and_valid_offsets_are_raw(self):
        for value in ['2026-01-12T10:02:00','2026-01-12T10:02:00.123456789+05:30',
                      '2026-01-12t10:02:00z','2026-01-12 10:02:00-04:00',
                      '2026-01-12T10:02:00-00:00','2026-01-12T10:02:00+23:59']:
            for item in self.parse(self.row(timestamp=value)):
                self.assertEqual(item.observed_at_raw,value)
                self.assertNotIn('observed_at_utc',item.to_wire())

    def test_invalid_explicit_offsets_are_not_silently_normalized(self):
        for value in ['2026-01-12T10:02:00+24:00','2026-01-12T10:02:00-00:60',
                      '2026-01-12T10:02:00+01:99']:
            self.rejects(self.row(timestamp=value),'INVALID_TIMEZONE',2)

    def test_malformed_dates_times_and_zone_names_reject(self):
        for value in ['SECRET','2026-02-30T10:00:00Z','2026-01-12','2026-01-12T24:00:00Z',
                      '2026-01-12T10:60:00Z','2026-01-12T10:00:60Z','2026-01-12T10:02:00 IST',
                      '2026-01-12T10:02:00+0530','2026-01-12T10:02:00+05:30:00',' 2026-01-12T10:02:00Z']:
            self.rejects(self.row(timestamp=value),'INVALID_TIMESTAMP',2)

    def test_quoted_multiline_device_and_raw_numeric_precision(self):
        value=' Device,"SECRET"\r\nCandidate '+chr(0x1f9ea)
        source=self.row(device=value,latitude='+12.9716000',longitude='7.75946e1')
        result=self.parse(source)
        self.assertEqual(result[0].raw_value,value)
        self.assertEqual(result[0].source_locator,'rows 2-3, device_id')
        self.assertEqual(result[1].raw_value,'+12.9716000')
        self.assertEqual(result[2].raw_value,'7.75946e1')

    def test_empty_header_and_changed_headers(self):
        self.assertEqual(self.parse(HEADER_BYTES),())
        for source in [b'',b'\xef\xbb\xbf',HEADER_BYTES.upper()+ROW,
                       b'timestamp,device_id,longitude,latitude\n'+ROW,
                       b'timestamp,device_id,latitude\n'+ROW,
                       b'timestamp,device_id,latitude,longitude,extra\n'+ROW]:
            self.rejects(source,'INVALID_HEADER',1)

    def test_missing_extra_or_blank_required_cells(self):
        for row in [b'\n',b't,D,1\n',b't,D,1,2,extra\n',b',D,1,2\n',
                    b'2026-01-12T00:00:00Z, ,1,2\n',b't,D,,2\n',b't,D,1,""\n']:
            self.rejects(HEADER_BYTES+row,'INVALID_ROW',2)

    def test_encoding_and_quote_errors_do_not_expose_cells(self):
        self.rejects(HEADER_BYTES+b'\xff','INVALID_UTF8')
        for row in [b't,D,1,"SECRET',b't,D,1,a"SECRET',b't,D,1,"SECRET"trailing',b't,D,1,SECRET\x00']:
            self.rejects(HEADER_BYTES+row,'MALFORMED_CSV')

    def test_invalid_late_row_cannot_return_partial_prefix(self):
        self.rejects(HEADER_BYTES+ROW+b'2026-01-12T00:00:00Z,D,91,2\n','INVALID_COORDINATE',3)
        self.assertEqual(len(self.parse(HEADER_BYTES+ROW)),3)

    def test_invalid_context_and_source(self):
        self.rejects('SECRET','INVALID_SOURCE')
        with self.assertRaises(GPSCSVError) as caught:
            parse_gps_csv(HEADER_BYTES,case_id='SECRET',evidence_id=uuid4(),processing_run_id=uuid4())
        self.assertEqual(caught.exception.code,'INVALID_CONTEXT')
        self.assertNotIn('SECRET',str(caught.exception))

    def test_real_byte_boundary_and_overflow(self):
        prefix=HEADER_BYTES+b'2026-01-12T00:00:00Z,';suffix=b',1,2'
        source=prefix+b'x'*(MAX_SOURCE_BYTES-len(prefix)-len(suffix))+suffix
        self.assertEqual(len(source),MAX_SOURCE_BYTES)
        result=self.parse(source)
        self.assertEqual(len(result[0].raw_value),MAX_SOURCE_BYTES-len(prefix)-len(suffix))
        self.rejects(source+b'x','BYTE_LIMIT')

    def test_real_row_boundary_and_overflow(self):
        source=HEADER_BYTES+ROW*MAX_DATA_ROWS
        result=self.parse(source)
        self.assertEqual(len(result),3*MAX_DATA_ROWS)
        self.assertEqual(result[-1].source_locator,f'row {MAX_DATA_ROWS+1}, longitude')
        del result
        self.rejects(source+ROW,'ROW_LIMIT',MAX_DATA_ROWS+2)

class GPSOriginalIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_real_upload_download_and_actor_isolation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            app=create_app(root/'db.sqlite3',storage_dir=root/'private',token_verifier=SyntheticTokenVerifier({'p02-synthetic-one':'investigator-1','p02-synthetic-two':'investigator-2'}))
            async with app.router.lifespan_context(app),AsyncClient(transport=ASGITransport(app),base_url='http://test',headers={'Authorization':'Bearer p02-synthetic-one'}) as client:
                case=(await client.post('/api/v1/cases',json={'title':'Synthetic GPS case'})).json()
                url=f"/api/v1/cases/{case['id']}/evidence"
                source=FIXTURE.read_bytes()
                upload=await client.post(url,data={'kind':'gps','source_label':'Synthetic GPS source'},files={'file':('gps.csv',source,'text/csv')})
                self.assertEqual(upload.status_code,201);evidence=upload.json()
                downloaded=await client.get(url+'/'+evidence['id']+'/content')
                self.assertEqual(downloaded.status_code,200)
                self.assertEqual(downloaded.content,source)
                self.assertEqual(hashlib.sha256(source).hexdigest(),evidence['sha256'])
                # P04 remains separate; run UUID below is explicitly synthetic caller context.
                result=parse_gps_csv(downloaded.content,case_id=UUID(case['id']),evidence_id=UUID(evidence['id']),processing_run_id=uuid4())
                self.assertEqual([item.raw_value for item in result],['D-8','12.9716','77.5946'])
                self.assertTrue(all(str(item.case_id)==case['id'] and str(item.evidence_id)==evidence['id'] for item in result))
                self.assertEqual((await client.get(url+'/'+evidence['id']+'/content')).content,source)
                self.assertEqual((await client.get(url+'/'+evidence['id']+'/content',headers={'Authorization':'Bearer p02-synthetic-two'})).status_code,404)
                self.assertEqual((await client.get(url+'/'+evidence['id']+'/content',headers={'Authorization':'invalid'})).status_code,401)
                with app.state.database.connect() as connection:
                    path=Path(connection.execute('SELECT storage_path FROM evidence WHERE id=?',(evidence['id'],)).fetchone()[0])
                self.assertEqual(path.read_bytes(),source)
