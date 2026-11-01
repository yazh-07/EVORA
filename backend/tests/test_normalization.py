"""P03 synthetic normalization goldens and actual immutable-source integration."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
import hashlib
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
from backend.parsers.network_csv import parse_network_csv
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.normalization import (NORMALIZER_VERSION, NormalizationError,
    normalize_timestamp, normalize_coordinate, normalize_observations)

ROOT=Path(__file__).resolve().parents[2]
GPS_HEADER=b'timestamp,device_id,latitude,longitude\n'
GPS_ROW=b'2026-01-12T15:32:00.123456789+05:30,D-8,+12.9716000,7.75946e1\n'

class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.context=dict(case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())
        self.gps=parse_gps_csv(GPS_HEADER+GPS_ROW,**self.context)
        self.network=parse_network_csv((ROOT/'fixtures/synthetic-case/network.csv').read_bytes(),**self.context)

    def test_exact_utc_goldens_and_calendar_rollover(self):
        cases={
          '2026-01-12T15:32:00+05:30':'2026-01-12T10:02:00Z',
          '2026-01-12T10:02:00-04:00':'2026-01-12T14:02:00Z',
          '2026-01-01T00:15:00+01:00':'2025-12-31T23:15:00Z',
          '2024-03-01T00:00:00+00:01':'2024-02-29T23:59:00Z',
          '2026-12-31T23:59:59-00:01':'2027-01-01T00:00:59Z',
          '2026-01-12t10:02:00z':'2026-01-12T10:02:00Z',
          '2026-01-12 10:02:00+00:00':'2026-01-12T10:02:00Z',
          '0001-01-01T00:00:00Z':'0001-01-01T00:00:00Z',
        }
        for raw,expected in cases.items():
            with self.subTest(raw=raw):
                result=normalize_timestamp(raw)
                self.assertEqual(result.utc_value,expected)
                self.assertEqual(result.raw_value,raw)
                self.assertEqual(result.status,'resolved')

    def test_fractional_seconds_preserved_without_microsecond_truncation(self):
        for fraction in ['000000000','123456789012345678901234567890','999999999999999999999999']:
            raw=f'2026-01-12T00:00:00.{fraction}+00:01'
            result=normalize_timestamp(raw)
            self.assertEqual(result.utc_value,f'2026-01-11T23:59:00.{fraction}Z')
            self.assertEqual(result.source_offset,'+00:01')
            self.assertEqual(result.raw_value,raw)

    def test_unknown_missing_ambiguous_and_invalid_reasons(self):
        cases={
            '2026-01-12T10:02:00':'missing_timezone',
            '2026-01-12T10:02:00-00:00':'unknown_offset',
            '2026-01-12T10:02:00 IST':'ambiguous_timezone',
            '2026-11-01T01:30:00 [America/New_York]':'ambiguous_timezone',
            '2026-01-12T10:02:00+24:00':'invalid_timezone',
            '2026-01-12T10:02:00+01:99':'invalid_timezone',
            '2026-01-12T10:02:00+0530':'invalid_timezone',
            'SECRET not a timestamp':'invalid_timestamp',
            '2026-02-30T10:02:00Z':'invalid_timestamp',
            '2026-01-12T24:00:00Z':'invalid_timestamp',
            '2026-01-12T10:00:60Z':'invalid_timestamp',
        }
        for raw,status in cases.items():
            with self.subTest(raw=raw):
                result=normalize_timestamp(raw)
                self.assertEqual(result.status,status)
                self.assertEqual(result.raw_value,raw)
                self.assertIsNone(result.utc_value)

    def test_zero_offset_known_is_distinct_from_unknown(self):
        for offset in ['Z','z','+00:00']:
            result=normalize_timestamp('2026-01-12T10:02:00'+offset)
            self.assertEqual(result.utc_value,'2026-01-12T10:02:00Z')
            self.assertEqual(result.source_offset,offset)
        self.assertIsNone(normalize_timestamp('2026-01-12T10:02:00-00:00').utc_value)

    def test_utc_range_overflow_keeps_original_without_fabrication(self):
        for raw in ['0001-01-01T00:00:00+00:01','9999-12-31T23:59:59-00:01']:
            result=normalize_timestamp(raw)
            self.assertEqual(result.status,'utc_out_of_range')
            self.assertIsNone(result.utc_value)
            self.assertEqual(result.raw_value,raw)

    def test_coordinate_canonicalization_and_signed_zero(self):
        for raw,expected in [('+12.9716000','12.9716'),('7.75946e1','77.5946'),
                             ('-0.0000','0'),('0e+999999','0'),('0001.2300','1.23'),
                             ('-.00050','-0.0005'),('+90.000','90'),('-180.000','-180')]:
            self.assertEqual(normalize_coordinate(raw,180),expected)

    def test_coordinate_precision_not_rounded_by_decimal_context(self):
        raw='12.1234567890123456789012345678901234567890'
        with localcontext() as context:
            context.prec=2
            normalized=normalize_coordinate(raw,90)
            self.assertEqual(normalized,raw.rstrip('0'))
            self.assertEqual(Decimal(normalized),Decimal(raw))

    def test_extreme_exponent_and_long_precision_use_lossless_scientific_form(self):
        for raw in ['1e-999999999','-123456789e-999999999','0.'+'123456789'*20]:
            normalized=normalize_coordinate(raw,90)
            self.assertIn('e',normalized)
            self.assertEqual(Decimal(normalized),Decimal(raw))
            self.assertLess(len(normalized),len(raw)+30)
        self.assertEqual(normalize_coordinate('1e-999999999',90),'1e-999999999')

    def test_plain_scientific_threshold_preserves_values(self):
        for exponent in [-60,-61,-62,-63,-64]:
            raw=f'1e{exponent}'
            result=normalize_coordinate(raw,90)
            self.assertEqual(Decimal(result),Decimal(raw))
            if exponent>=-62:self.assertNotIn('e',result)
            else:self.assertIn('e',result)

    def test_invalid_coordinates_reject_without_raw_error_echo(self):
        for raw,maximum in [('90.00000000000000000001',90),('180.00000000000001',180),
                            ('NaN',90),('Infinity',90),('SECRET',90),(' 1',90),('1_0',90)]:
            with self.assertRaises(NormalizationError) as caught:normalize_coordinate(raw,maximum)
            self.assertEqual(caught.exception.code,'INVALID_COORDINATE')
            self.assertNotIn('SECRET',str(caught.exception))

    def test_normalizes_real_parser_values_and_preserves_every_source_field(self):
        sources=self.network+self.gps
        before=tuple(source.to_wire() for source in sources)
        results=normalize_observations(sources)
        self.assertEqual(len(results),9)
        for source,result in zip(sources,results):
            for field in ['id','case_id','evidence_id','processing_run_id','kind','source_locator',
                          'raw_value','observed_at_raw','extraction_confidence']:
                self.assertEqual(getattr(result.observation,field),getattr(source,field))
            self.assertIsNot(result.observation,source)
            self.assertEqual(result.version,NORMALIZER_VERSION)
        self.assertEqual(results[-2].observation.normalized_value,'12.9716')
        self.assertEqual(results[-1].observation.normalized_value,'77.5946')
        self.assertEqual(results[-1].observation.observed_at_utc,'2026-01-12T10:02:00.123456789Z')
        self.assertEqual(tuple(source.to_wire() for source in sources),before)
        self.assertEqual([x.observation.normalized_value for x in results[:6]], [x.normalized_value for x in self.network])

    def test_internal_uncertainty_not_added_to_wire_and_schema_validates(self):
        spec=json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))
        validator=Draft202012Validator({**spec['components']['schemas']['Observation'],'components':spec['components']},format_checker=FormatChecker())
        sources=self.gps+(replace(self.network[0],observed_at_raw='2026-01-12T10:02:00 IST'),)
        results=normalize_observations(sources)
        for result in results:
            wire=result.observation.to_wire();validator.validate(wire)
            for key in ['time','status','source_offset','coordinate_status','version','entity_key']:
                self.assertNotIn(key,wire)
        self.assertNotIn('observed_at_utc',results[-1].observation.to_wire())
        self.assertEqual(results[-1].time.status,'ambiguous_timezone')

    def test_unknown_time_network_rows_remain_available_and_unscored(self):
        for raw,status in [('2026-01-12T10:02:00','missing_timezone'),('SECRET','invalid_timestamp')]:
            source=replace(self.network[0],observed_at_raw=raw)
            result=normalize_observations((source,))[0]
            self.assertEqual(result.time.status,status)
            self.assertEqual(result.observation.raw_value,source.raw_value)
            self.assertEqual(result.observation.extraction_confidence,0)
            self.assertIsNone(result.observation.observed_at_utc)

    def test_immutable_results_and_wire_copies(self):
        result=normalize_observations(self.gps)[0]
        with self.assertRaises(FrozenInstanceError):result.version='changed'
        with self.assertRaises(FrozenInstanceError):result.time.status='changed'
        with self.assertRaises(FrozenInstanceError):result.observation.raw_value='changed'
        wire=result.observation.to_wire();wire['raw_value']='changed'
        self.assertEqual(result.observation.raw_value,'D-8')

    def test_value_idempotence_is_not_processing_run_replay(self):
        first=normalize_observations(self.gps)
        second=normalize_observations(result.observation for result in first)
        self.assertEqual(first,second)
        self.assertEqual(normalize_observations(()),())

    def test_invalid_late_input_is_atomic_and_context_errors_are_safe(self):
        for invalid,code in [(replace(self.gps[1],raw_value='SECRET'),'INVALID_COORDINATE'),
                             (replace(self.gps[0],case_id='SECRET'),'INVALID_CONTEXT'),
                             (replace(self.gps[0],kind='transcript.segment'),'UNSUPPORTED_KIND'),
                             ({'raw':'SECRET'},'INVALID_OBSERVATION')]:
            with self.assertRaises(NormalizationError) as caught:
                normalize_observations((self.gps[0],invalid))
            self.assertEqual(caught.exception.code,code)
            self.assertNotIn('SECRET',str(caught.exception))
        with self.assertRaises(NormalizationError):normalize_timestamp(None)

    def test_separate_contexts_are_preserved_without_joining_identities(self):
        other_context=dict(case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())
        other=parse_gps_csv(GPS_HEADER+GPS_ROW,**other_context)
        results=normalize_observations((self.network[0],other[0]))
        self.assertEqual(results[0].observation.case_id,self.context['case_id'])
        self.assertEqual(results[1].observation.case_id,other_context['case_id'])
        self.assertNotEqual(results[0].observation.id,results[1].observation.id)

class NormalizationOriginalIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_real_network_gps_originals_normalized_without_source_or_storage_mutation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            app=create_app(root/'db.sqlite3',storage_dir=root/'private',token_verifier=SyntheticTokenVerifier({'p03-synthetic-one':'investigator-1','p03-synthetic-two':'investigator-2'}))
            async with app.router.lifespan_context(app),AsyncClient(transport=ASGITransport(app),base_url='http://test',headers={'Authorization':'Bearer p03-synthetic-one'}) as client:
                case=(await client.post('/api/v1/cases',json={'title':'Synthetic P03 case'})).json()
                url=f"/api/v1/cases/{case['id']}/evidence"
                originals=[('network.csv','network_log',(ROOT/'fixtures/synthetic-case/network.csv').read_bytes(),parse_network_csv),('gps.csv','gps',GPS_HEADER+GPS_ROW,parse_gps_csv)]
                all_sources=[];metadata=[]
                for name,kind,source,parser in originals:
                    response=await client.post(url,data={'kind':kind,'source_label':'Synthetic P03'},files={'file':(name,source,'text/csv')})
                    self.assertEqual(response.status_code,201);evidence=response.json()
                    downloaded=await client.get(url+'/'+evidence['id']+'/content')
                    self.assertEqual(downloaded.status_code,200);self.assertEqual(downloaded.content,source)
                    self.assertEqual(hashlib.sha256(source).hexdigest(),evidence['sha256'])
                    # Unpersisted run context only: P04's producer remains a separate task.
                    all_sources.extend(parser(downloaded.content,case_id=UUID(case['id']),evidence_id=UUID(evidence['id']),processing_run_id=uuid4()))
                    metadata.append((evidence,source))
                with app.state.database.connect() as connection:
                    rows_before=[tuple(row) for row in connection.execute('SELECT * FROM evidence ORDER BY id')]
                before=[item.to_wire() for item in all_sources]
                results=normalize_observations(all_sources)
                self.assertEqual(len(results),9)
                self.assertEqual(results[-2].observation.normalized_value,'12.9716')
                self.assertEqual(results[-1].observation.normalized_value,'77.5946')
                self.assertEqual(results[-1].time.utc_value,'2026-01-12T10:02:00.123456789Z')
                self.assertEqual([item.to_wire() for item in all_sources],before)
                for source,result in zip(all_sources,results):
                    self.assertEqual(result.observation.evidence_id,source.evidence_id)
                    self.assertEqual(result.observation.processing_run_id,source.processing_run_id)
                for evidence,source in metadata:
                    content_url=url+'/'+evidence['id']+'/content'
                    self.assertEqual((await client.get(content_url)).content,source)
                    self.assertEqual((await client.get(content_url,headers={'Authorization':'Bearer p03-synthetic-two'})).status_code,404)
                    self.assertEqual((await client.get(content_url,headers={'Authorization':'invalid'})).status_code,401)
                with app.state.database.connect() as connection:
                    self.assertEqual([tuple(row) for row in connection.execute('SELECT * FROM evidence ORDER BY id')],rows_before)
                    for row in connection.execute('SELECT storage_path,sha256 FROM evidence'):
                        self.assertEqual(hashlib.sha256(Path(row[0]).read_bytes()).hexdigest(),row[1])
