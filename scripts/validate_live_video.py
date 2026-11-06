"""Opt-in isolated API validation using a real vision service and local speech model.

EVORA_SPEECH_MODEL_PATH=/downloaded/whisper python scripts/validate_live_video.py \
    --video /path/to/clip.mp4 --model vision-model --endpoint http://127.0.0.1:11434 \
    --output /tmp/evora-video-validation
The supplied video is transmitted only to the specified loopback Ollama endpoint.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from backend.app import create_app
from backend.image_understanding import safe_endpoint


async def run(args):
    endpoint=safe_endpoint(args.endpoint,'ollama')
    args.output.mkdir(parents=True,exist_ok=False)
    app=create_app(args.output/'case.sqlite',storage_dir=args.output/'evidence')
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://localhost',headers={'X-Evora-Request':'1'}) as client:
            async def call(method,path,status=200,**kwargs):
                result=await client.request(method,'/api/v1'+path,**kwargs)
                assert result.status_code==status,(result.status_code,result.text)
                return result.json()
            await call('POST','/auth/setup',json=dict(username='video-validation',display_name='Video Validation',password='isolated video validation passphrase'))
            await call('PUT','/settings',json=dict(qa_provider='ollama',qa_url=endpoint,vision_model=args.model))
            case=await call('POST','/cases',201,json={'title':'Live controlled video acceptance'})
            base='/cases/'+case['id']
            data=args.video.read_bytes()
            evidence=await call('POST',base+'/evidence',201,data=dict(kind='video',source_label='Explicit live video validation sample'),files={'file':(args.video.name,data,'video/mp4')})
            run=await call('POST',base+'/evidence/'+evidence['id']+'/video-analysis',202,
                headers={'Idempotency-Key':str(uuid4())},json=dict(expected_provider='ollama',expected_model=args.model,expected_endpoint=endpoint,
                    max_frames=2,sample_interval_seconds=5,transcribe_speech=True,confirm_external_processing=False))
            terminal=await call('GET',base+'/evidence/'+evidence['id']+'/processing-runs/'+run['id'])
            records=await call('GET',base+'/observations',params={'processing_run_id':run['id'],'limit':100})
            report=dict(source_sha256=hashlib.sha256(data).hexdigest(),run=terminal,observations=records['items'])
            (args.output/'results.json').write_text(json.dumps(report,indent=2))
            assert terminal['status']=='completed',terminal
            kinds={item['kind'] for item in records['items']}
            assert {'video.scene','video.ocr','video.provenance'}<=kinds
            assert 'transcript.segment' in kinds or 'transcript.status' in kinds
            print('Completed real vision and local speech processing:',{kind:sum(item['kind']==kind for item in records['items']) for kind in sorted(kinds)})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--endpoint',default='http://127.0.0.1:11434')
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(run(parser.parse_args()))
