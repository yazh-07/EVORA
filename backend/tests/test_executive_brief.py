import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from backend import analysis, qa_synthesis


class ExecutiveBriefTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(state=SimpleNamespace(qa_model='local-model', qa_url='http://model.test'))
        self.run = dict(id=str(uuid4()), case_id=str(uuid4()))
        eid = str(uuid4())
        self.context = dict(evidence=[dict(id=eid, filename='network.csv')], entities=[],
            observations=[dict(id=str(uuid4()), evidence_id=eid, kind='network.device',
                normalized_value='D-7', source_locator='row 2')])
        self.answer = dict(summary='Review device activity.', hypothesis='A device appears in the log.')

    def test_disabled_empty_and_environment_configuration(self):
        self.app.state.qa_model = None
        with patch.object(qa_synthesis, '_chat') as chat:
            self.assertIsNone(analysis._executive_brief(self.app, self.run, self.context))
        chat.assert_not_called()
        del self.app.state.qa_model
        with patch.dict(os.environ, EVORA_QA_MODEL='env-model'), patch.object(qa_synthesis, '_chat',
                return_value=(self.answer, 'env-model')) as chat:
            self.assertEqual(analysis._executive_brief(self.app, self.run, self.context)['details']['model'], 'env-model')
            self.context['observations'] = []
            self.assertIsNone(analysis._executive_brief(self.app, self.run, self.context))
        self.assertEqual(chat.call_count, 1)

    def test_invalid_answers_and_provider_errors_fall_back(self):
        for result in (None, [], {}, {'summary': '', 'hypothesis': 'x'},
                {'summary': 42, 'hypothesis': 'x'}, {'summary': 'x', 'hypothesis': 'x' * 12001}):
            with self.subTest(result=str(result)[:80]), patch.object(qa_synthesis, '_chat', return_value=(result, 'local')):
                self.assertIsNone(analysis._executive_brief(self.app, self.run, self.context))
        for error in (TimeoutError(), httpx.ConnectError('offline'), ValueError('bad JSON')):
            with patch.object(qa_synthesis, '_chat', side_effect=error):
                self.assertIsNone(analysis._executive_brief(self.app, self.run, self.context))

    def test_real_ollama_protocol_requests_hypothesis_schema_and_bounded_timeout(self):
        requests, options = [], []
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=dict(done=True, message=dict(content=json.dumps(self.answer))))
        real_client = httpx.Client
        def client(**kwargs):
            options.append(kwargs)
            return real_client(transport=httpx.MockTransport(respond))
        with patch.object(qa_synthesis.httpx, 'Client', side_effect=client):
            brief = analysis._executive_brief(self.app, self.run, self.context)
        self.assertTrue(brief['details']['ai_generated'])
        self.assertEqual(requests[0]['format']['required'], ['hypothesis', 'summary'])
        self.assertEqual(options[0]['timeout'].read, 30)

    def test_context_sampling_keeps_multiple_sources_and_excludes_private_storage(self):
        original = self.context['observations'][0]
        self.context['evidence'][0]['storage_path'] = '/private/original'
        self.context['observations'] = [dict(original, id=str(uuid4()), raw_value='x' * 10000) for _ in range(500)]
        second = dict(original, id=str(uuid4()), evidence_id=str(uuid4()))
        self.context['observations'].append(second)
        with patch.object(qa_synthesis, '_chat', return_value=(self.answer, 'local')) as chat:
            brief = analysis._executive_brief(self.app, self.run, self.context)
        payload = chat.call_args.args[2]
        self.assertLess(len(json.dumps(payload)), 30000)
        self.assertNotIn('storage_path', json.dumps(payload))
        self.assertIn(second['id'], brief['observation_ids'])
