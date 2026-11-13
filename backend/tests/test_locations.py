import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4
from httpx import ASGITransport, AsyncClient
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.locations import project_locations


class LocationsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.app = create_app(Path(self.temp.name)/'db', storage_dir=Path(self.temp.name)/'files', token_verifier=SyntheticTokenVerifier({'one':'investigator-1','two':'investigator-2'}))
        self.life=self.app.router.lifespan_context(self.app);await self.life.__aenter__()
        self.client=AsyncClient(transport=ASGITransport(self.app),base_url='http://test',headers={'Authorization':'Bearer one'})
        self.case=(await self.client.post('/api/v1/cases',json={'title':'Map checks'})).json()['id']
    async def asyncTearDown(self):
        await self.client.aclose();await self.life.__aexit__(None,None,None);self.temp.cleanup()
    async def process(self,kind,filename,content):
        item=(await self.client.post(f'/api/v1/cases/{self.case}/evidence',data={'kind':kind,'source_label':filename},files={'file':(filename,content)})).json()
        run=(await self.client.post(f'/api/v1/cases/{self.case}/evidence/{item["id"]}/processing-runs',headers={'Idempotency-Key':str(uuid4())})).json()
        state=(await self.client.get(f'/api/v1/cases/{self.case}/evidence/{item["id"]}/processing-runs/{run["id"]}')).json()
        self.assertEqual(state['status'],'completed',state)
        return item,run
    async def test_real_gps_coordinates_order_zero_timezone_and_source_links(self):
        item,run=await self.process('gps','gps.csv',b'timestamp,device_id,latitude,longitude\n2026-01-01T12:00:00+05:30,D-1,0,0\n2026-01-01T13:00:00+05:30,D-1,12.97,77.59\n')
        response=await self.client.get(f'/api/v1/cases/{self.case}/locations');self.assertEqual(response.status_code,200,response.text)
        data=response.json();self.assertEqual(data['total'],2);self.assertEqual(data['items'][0]['geometry']['coordinates'],[0,0]);self.assertEqual(data['items'][1]['geometry']['coordinates'],[77.59,12.97]);self.assertEqual(data['items'][0]['observed_at_utc'],'2026-01-01T06:30:00Z')
        self.assertTrue(all(x['evidence_id']==item['id'] and x['processing_run_id']==run['id'] and x['basis']=='gps' and x['accuracy_m'] is None for x in data['items']))
        page=(await self.client.get(f'/api/v1/cases/{self.case}/locations?limit=1&offset=1')).json();self.assertEqual(page['items'],data['items'][1:])
        for query in ['?limit=1001','?unknown=1','?offset=0&offset=1']:
            self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/locations'+query)).status_code,400)
        self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/locations',headers={'Authorization':'Bearer two'})).status_code,404)
    async def test_real_place_extraction_is_explicitly_approximate(self):
        await self.process('document','statement.txt',b'Alice Smith visited Paris.\n')
        response=await self.client.get(f'/api/v1/cases/{self.case}/locations');self.assertEqual(response.status_code,200,response.text)
        items=response.json()['items'];self.assertTrue(items);self.assertTrue(all(x['basis']=='place_mention' and x['device'] is None and x['accuracy_m'] is None for x in items));self.assertTrue(any('Paris' in x['label'] for x in items))
    async def test_reprocessing_replaces_live_points_and_retains_no_mixed_run_pairs(self):
        item,first=await self.process('gps','gps.csv',b'timestamp,device_id,latitude,longitude\n2026-01-01T12:00:00Z,D-1,1,2\n')
        second=(await self.client.post(f'/api/v1/cases/{self.case}/evidence/{item["id"]}/processing-runs',headers={'Idempotency-Key':str(uuid4())})).json()
        items=(await self.client.get(f'/api/v1/cases/{self.case}/locations')).json()['items'];self.assertEqual(len(items),1);self.assertEqual(items[0]['processing_run_id'],second['id']);self.assertNotEqual(first['id'],second['id'])

class ProjectionTests(unittest.TestCase):
    def test_mixed_runs_and_conflicting_values_fail(self):
        base=dict(id=str(uuid4()),evidence_id=str(uuid4()),processing_run_id=str(uuid4()),kind='gps.latitude',source_locator='row 2, latitude',raw_value='10',normalized_value='10',observed_at_raw='2026-01-01T12:00:00Z',observed_at_utc='2026-01-01T12:00:00Z')
        with self.assertRaises(ValueError):project_locations([base])
        with self.assertRaises(ValueError):project_locations([base,base])
        unknown={**base,'kind':'text.mention.location','raw_value':'Unmapped place name from source'}
        self.assertEqual(project_locations([unknown]),[])
