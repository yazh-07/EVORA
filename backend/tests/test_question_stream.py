import json
import unittest
from unittest.mock import patch
import httpx
from backend.qa_synthesis import DraftClaims, _read_chat_stream, SynthesisError

class DraftTests(unittest.TestCase):
    def test_split_escapes_multiple_claims_and_reasoning_are_not_published(self):
        events=[]
        draft=DraftClaims(lambda kind,value:events.append((kind,value)))
        raw='<think>private reasoning</think>'+json.dumps({'supported':True,'claims':[{'text':'GPS → Chennai "record" 📍','observation_ids':['id']},{'text':'Second claim','observation_ids':['other']}]})
        for char in raw:draft(char)
        combined=''.join(value['text'] for _,value in events)
        self.assertEqual(combined,'GPS → Chennai "record" 📍\n\nSecond claim')
        self.assertNotIn('private reasoning',combined)
        self.assertNotIn('observation_ids',combined)

    def test_real_provider_chunks_reach_callback_before_completion(self):
        seen=[]
        class Chunks(httpx.SyncByteStream):
            def __iter__(self):
                yield b'data: {"choices":[{"delta":{"content":"{\\"supported\\":"}}]}\n\n'
                self_test.assertEqual(seen,['{"supported":'])
                yield b'data: {"choices":[{"delta":{"content":"true}"},"finish_reason":"stop"}]}\n\n'
        self_test=self
        with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Chunks()))) as client:
            result,_=_read_chat_stream(client,'https://example.test/chat',{'model':'fixture'}, {},seen.append)
        self.assertEqual(result,{'supported':True})

    def test_interrupted_provider_stream_is_rejected(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'data: {"choices":[{"delta":{"content":"{}"}}]}\n\n'))) as client:
            with self.assertRaises(SynthesisError):
                _read_chat_stream(client,'https://example.test/chat',{'model':'fixture'}, {},lambda value:None)
