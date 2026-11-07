"""Real SQL-only publication and exact graph-source validation without a Neo4j service."""
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from uuid import uuid4
from backend import analysis
from backend.errors import AccessError
from backend.graph_projection import get_projected_graph, rebuild_graph_partition
from backend.tests import test_analysis as analysis_tests


class StandaloneModeTests(IsolatedAsyncioTestCase):
    upload=analysis_tests.AnalysisTests.upload
    process=analysis_tests.AnalysisTests.process
    start=analysis_tests.AnalysisTests.start
    poll=analysis_tests.AnalysisTests.poll

    async def asyncSetUp(self):
        await analysis_tests.AnalysisTests.asyncSetUp(self)
        self.app.state.qa_model=''
        self.enterContext(patch.object(analysis,'Neo4jGraphDatabase',side_effect=RuntimeError('No graph service configured')))

    async def test_sql_only_analysis_retains_valid_source_backed_graph(self):
        await self.upload()
        await self.upload('gps.csv','gps')
        run=await self.poll(await self.start())
        self.assertEqual(run['status'],'completed',run)
        self.assertIsNone(self.app.state.graph_database)
        graph=get_projected_graph(self.app.state.database,None,case_id=self.case,analysis_run_id=run['id'])
        self.assertTrue(any(e['kind']=='assigned_ip' for e in graph['edges']))
        sources=set(run['input_snapshot']['evidence_ids']);observations=set(run['input_snapshot']['observation_ids'])
        for node in graph['nodes']:
            self.assertTrue(set(node['evidence_ids'])<=sources)
            self.assertTrue(set(node.get('properties',{}).get('observation_ids',[]))<=observations)
        for edge in graph['edges']:
            self.assertTrue(set(edge['evidence_ids'])<=sources)
            self.assertTrue(set(edge['observation_ids'])<=observations)
        response=await self.client.get(self.base+'/graph',params={'analysis_run_id':run['id']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json(),graph)
        self.assertTrue(rebuild_graph_partition(self.app.state.database,None,case_id=self.case,analysis_run_id=run['id']))

    async def test_sql_only_rebuild_does_not_bypass_resource_validation(self):
        await self.upload()
        run=await self.poll(await self.start())
        for case,selected in [(str(uuid4()),run['id']),(self.case,str(uuid4()))]:
            with self.assertRaises(AccessError) as error:
                rebuild_graph_partition(self.app.state.database,None,case_id=case,analysis_run_id=selected)
            self.assertEqual(error.exception.status_code,404)
