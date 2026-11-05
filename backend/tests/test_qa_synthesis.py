"""Generated claims, provider protocol, source checks and private provenance."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from backend import qa_synthesis
from backend.questions import build_case_context
from backend.observations import _utc_order
from backend.tests import test_questions as questions


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.oid = str(uuid4())
        self.context = dict(observations=[dict(id=self.oid, evidence_id=str(uuid4()),
            source_locator='row 2, device_id', normalized_value='D-7', kind='network.device')])
        self.result = dict(supported=True, claims=[dict(text='The network record mentions D-7.',
                                                      observation_ids=[self.oid])])

    def test_protocol_generates_and_independently_checks_exact_citations(self):
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            value = self.result if len(calls) == 1 else dict(supported=True)
            return httpx.Response(200, json=dict(done=True, model='test-model',
                                                message=dict(content=json.dumps(value))))
        # Patch the factory, each inference receives a fresh client with the same transport.
        real_client = httpx.Client
        with patch.object(qa_synthesis.httpx, 'Client', side_effect=lambda **kw:
                          real_client(transport=httpx.MockTransport(respond))):
            citations, model, verification = qa_synthesis.synthesize('D-7?', self.context, 'test-model')
        self.assertEqual(len(calls), 2)
        self.assertFalse(calls[0]['stream'])
        self.assertEqual(calls[0]['format']['type'], 'object')
        self.assertIn('claims', calls[0]['format']['required'])
        self.assertEqual(citations[0]['observation_id'], self.oid)
        self.assertEqual(citations[0]['source_locator'], 'row 2, device_id')
        self.assertEqual(verification['status'], 'verified')

    def test_wrong_device_is_rejected_even_if_model_verifier_would_accept(self):
        result = dict(supported=True, claims=[dict(text='Device D-8 connected.', observation_ids=[self.oid])])
        with patch.object(qa_synthesis, '_chat', return_value=(result, 'test')) as model:
            with self.assertRaisesRegex(qa_synthesis.SynthesisError, 'identifier absent'):
                qa_synthesis.synthesize('Summarize', self.context, 'test')
        self.assertEqual(model.call_count, 1)

    def test_openai_generation_and_verification_use_authenticated_json_mode(self):
        calls = []
        def respond(request):
            calls.append(request)
            value = self.result if len(calls) == 1 else dict(supported=True)
            return httpx.Response(200, json={'model': 'gpt-4o-snapshot', 'choices': [
                {'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]})
        real_client = httpx.Client
        with patch.object(qa_synthesis.httpx, 'Client', side_effect=lambda **kw:
                          real_client(transport=httpx.MockTransport(respond))):
            citations, model, verification = qa_synthesis.synthesize('D-7?', self.context, 'gpt-4o',
                qa_provider='openai', openai_api_key='sk-test', openai_base_url='https://provider.test/api/v1/')
        self.assertEqual(len(calls), 2)
        for request in calls:
            self.assertEqual(str(request.url), 'https://provider.test/api/v1/chat/completions')
            self.assertEqual(request.headers['Authorization'], 'Bearer sk-test')
            payload = json.loads(request.content)
            self.assertEqual(payload['model'], 'gpt-4o')
            self.assertEqual(payload['response_format'], {'type': 'json_object'})
            self.assertNotIn('options', payload)
            self.assertNotIn('temperature', payload)  # Reasoning models disallow this parameter.
            self.assertIn('JSON', payload['messages'][0]['content'])
        self.assertEqual(citations[0]['observation_id'], self.oid)
        self.assertEqual(model, 'gpt-4o-snapshot')
        self.assertEqual(verification['status'], 'verified')

    def test_openai_rejects_incomplete_refused_and_malformed_responses(self):
        valid = {'finish_reason': 'stop', 'message': {'content': json.dumps(self.result)}}
        bodies = [[], {}, {'choices': []}, {'choices': [None]}]
        bodies += [{'choices': [{**valid, 'finish_reason': reason}]} for reason in ['length', 'content_filter', None]]
        bodies += [{'choices': [{**valid, 'message': message}]} for message in [
            None, {'content': None}, {'content': 'not JSON'}, {'content': '[]'},
            {'content': json.dumps(self.result), 'refusal': 'Cannot answer'},
        ]]
        real_client = httpx.Client
        for body in bodies:
            with self.subTest(body=body), patch.object(qa_synthesis.httpx, 'Client', side_effect=lambda **kw:
                    real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))):
                with self.assertRaises(ValueError):
                    qa_synthesis.synthesize('D-7?', self.context, 'gpt-4o',
                        qa_provider='openai', openai_api_key='sk-test')

    def test_openai_requires_key_and_verifies_claims_with_same_provider(self):
        with patch.object(qa_synthesis.httpx, 'Client') as client:
            with self.assertRaisesRegex(qa_synthesis.SynthesisError, 'API key'):
                qa_synthesis.synthesize('D-7?', self.context, 'gpt-4o', qa_provider='openai')
        client.assert_not_called()
        with patch.object(qa_synthesis, '_chat', side_effect=[(self.result, 'gpt-4o'), ({'supported': False}, 'gpt-4o')]) as chat:
            with self.assertRaisesRegex(qa_synthesis.SynthesisError, 'Unsupported'):
                qa_synthesis.synthesize('D-7?', self.context, 'gpt-4o',
                    qa_provider='openai', openai_api_key='sk-test')
        self.assertEqual(chat.call_count, 2)
        self.assertTrue(all(call.kwargs['qa_provider'] == 'openai' for call in chat.call_args_list))

    def test_fabricated_id_missing_citations_and_unentailed_claim_are_rejected(self):
        for ids in ([str(uuid4())], [], [None]):
            result = dict(supported=True, claims=[dict(text='Invented claim', observation_ids=ids)])
            with patch.object(qa_synthesis, '_chat', return_value=(result, 'test')):
                with self.assertRaises(qa_synthesis.SynthesisError):
                    qa_synthesis.synthesize('question', self.context, 'test')
        with patch.object(qa_synthesis, '_chat', side_effect=[(self.result, 'test'), ({'supported': False}, 'test')]):
            with self.assertRaises(qa_synthesis.SynthesisError):
                qa_synthesis.synthesize('question', self.context, 'test')


class GeneratedQuestionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = questions.QuestionTests.asyncSetUp
    new_case = questions.QuestionTests.new_case
    upload = questions.QuestionTests.upload
    process = questions.QuestionTests.process
    stored_observations = questions.QuestionTests.stored_observations
    validate = questions.QuestionTests.validate

    async def test_generated_answer_private_context_and_unknown_provenance(self):
        gps = await self.process(await self.upload('gps'))
        self.app.state.qa_model = 'test-model'
        observation = self.stored_observations()[0]
        claim = 'The selected network observation records ' + observation['normalized_value'] + '.'
        result = dict(supported=True, claims=[dict(text=claim, observation_ids=[observation['id']])])
        with patch.object(qa_synthesis, '_chat', side_effect=[(result, 'test-model'), ({'supported': True}, 'test-model')]):
            answer = (await self.client.post(self.url, json={'question': 'Summarize the recorded network and GPS evidence.'})).json()
        self.validate('CaseAnswer', answer)
        self.assertEqual(answer['answer'], claim)
        self.assertEqual(answer['model_version'], 'ollama:test-model')
        with self.app.state.database.connect() as connection:
            payload = json.loads(connection.execute('SELECT payload_json FROM qa_provenance WHERE id=?',
                                (answer['provenance_id'],)).fetchone()[0])
        context = payload['context']
        self.assertEqual(len(context['evidence']), 2)
        self.assertTrue(all(e['sha256'] for e in context['evidence']))
        self.assertTrue(context['timeline']); self.assertTrue(context['relationships'])
        self.assertEqual(context['entity_counts']['device'], 3)
        self.assertTrue(context['locations'])
        self.assertEqual(payload['verification']['status'], 'verified')
        with patch.object(qa_synthesis, '_chat', side_effect=AssertionError('Must abstain before model')):
            response = (await self.client.post(self.url, json={'question': 'Who committed the crime?'})).json()
        self.assertFalse(response['supported']); self.assertEqual(response['citations'], [])

    async def test_model_failure_and_rejected_claim_return_uncertainty_without_citations(self):
        self.app.state.qa_model = 'test-model'
        with patch('backend.questions.synthesize', side_effect=AssertionError('Unknown ID must abstain')):
            unknown = (await self.client.post(self.url, json={'question': 'Was D-999 connected?'})).json()
        self.assertFalse(unknown['supported']); self.assertEqual(unknown['citations'], [])
        for error in (httpx.ConnectError('Unavailable'), qa_synthesis.SynthesisError('Ungrounded claim')):
            with patch('backend.questions.synthesize', side_effect=error):
                response = await self.client.post(self.url, json={'question': 'D-7?'})
            self.assertEqual(response.status_code, 200)
            answer = response.json()
            self.assertFalse(answer['supported']); self.assertEqual(answer['citations'], [])
            self.assertIn('unavailable', answer['answer'])

    async def test_invalid_provider_metadata_cannot_publish_partial_citations(self):
        self.app.state.qa_model = 'test-model'
        item = self.stored_observations()[0]
        citation = dict(claim='A partial claim', evidence_id=item['evidence_id'],
                        observation_id=item['id'], source_locator=item['source_locator'])
        with patch('backend.questions.synthesize', return_value=([citation], None, {'status': 'verified'})):
            answer = (await self.client.post(self.url, json={'question': 'D-7?'})).json()
        self.assertFalse(answer['supported'])
        self.assertEqual(answer['citations'], [])
