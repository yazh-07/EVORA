"""Explicit sampled video interpretation, local speech and geometric candidate tracks."""
from io import BytesIO
import hashlib
import importlib.util
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID, uuid4, uuid5

import cv2
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import Field

from backend import image_understanding as vision
from backend.auth import CaseAccessGrant, authenticated_actor, require_case_access
from backend.errors import AccessError
from backend.parsers.normalization import NormalizedObservation, NormalizationResult, TimeNormalization

VERSION = 'video-understanding/1'
PROCESSOR_VERSION = 'processing-lifecycle/10'
router = APIRouter()


def speech_config():
    path = Path(os.environ.get('EVORA_SPEECH_MODEL_PATH', '')).resolve()
    if not os.environ.get('EVORA_SPEECH_MODEL_PATH') or not (path / 'model.bin').is_file() or importlib.util.find_spec('faster_whisper') is None:
        raise AccessError(400, 'SPEECH_NOT_CONFIGURED', 'Local speech transcription requires faster-whisper and EVORA_SPEECH_MODEL_PATH pointing to a downloaded model directory.')
    files = sorted(p for p in path.iterdir() if p.is_file())
    if len(files) > 64 or any(p.stat().st_size > 4 * 1024**3 for p in files):
        raise ValueError('Speech model size limit')
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.name.encode() + b'\0')
        with file.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                digest.update(block)
    return dict(path=str(path), artifact_sha256=digest.hexdigest(), engine='faster-whisper', runtime_version=version('faster-whisper'))


@router.get('/api/v1/media-capabilities', dependencies=[Depends(authenticated_actor)])
def capabilities():
    ready = bool(os.environ.get('EVORA_SPEECH_MODEL_PATH') and
        (Path(os.environ['EVORA_SPEECH_MODEL_PATH']) / 'model.bin').is_file() and importlib.util.find_spec('faster_whisper'))
    return dict(video_audio_tools=bool(shutil.which('ffmpeg') and shutil.which('ffprobe')), local_speech_ready=ready)


def validate_config(config):
    if (not isinstance(config, dict) or set(config) != {'version','vision','sample_interval_seconds','max_frames','speech'} or
        config['version'] != VERSION or type(config['sample_interval_seconds']) is not int or
        not 1 <= config['sample_interval_seconds'] <= 60 or type(config['max_frames']) is not int or
        not 1 <= config['max_frames'] <= 60):
        raise ValueError('Invalid video configuration')
    vision.validate_config(config['vision'])
    speech = config['speech']
    if speech is not None and (not isinstance(speech, dict) or set(speech) != {'path','artifact_sha256','engine','runtime_version'} or
        speech['engine'] != 'faster-whisper' or not isinstance(speech['path'], str) or
        not re.fullmatch('[0-9a-f]{64}', speech.get('artifact_sha256', '')) or not isinstance(speech['runtime_version'], str)):
        raise ValueError('Invalid speech configuration')
    return config


def observation(kind, value, locator, *, case_id, evidence_id, processing_run_id, offset=None):
    raw_time = '' if offset is None else f'time_offset={offset:.6f}s'
    item = NormalizedObservation(uuid5(processing_run_id, kind+':'+locator), case_id, evidence_id,
        processing_run_id, kind, locator, value, value, raw_time, 0.0)
    return NormalizationResult(item, TimeNormalization(raw_time, None, 'not_provided' if offset is None else 'relative_media_time', None), 'not_applicable')


def _iou(a, b):
    x,y,w,h = a; xx,yy,ww,hh = b
    inter = max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
    return inter / (w*h+ww*hh-inter)


def tracks(detections):
    """Greedy one-to-one IoU linking; no identity, interpolation or cross-clip links."""
    parsed=[]
    for result in detections:
        item=result.observation
        match=re.fullmatch(r'frame=(\d+); time_offset=([\d.]+)s; box=(\d+),(\d+),(\d+),(\d+)', item.source_locator)
        if item.kind != 'video.frame_detection' or not match:
            continue
        parsed.append(dict(id=str(item.id), frame=int(match[1]), seconds=float(match[2]),
            box=tuple(int(match[i]) for i in range(3,7)), label=item.raw_value.split(' [')[0]))
    groups=[]
    for frame in sorted({item['frame'] for item in parsed}):
        used=set()
        for item in [entry for entry in parsed if entry['frame']==frame]:
            candidates=[(i,_iou(group[-1]['box'],item['box'])) for i,group in enumerate(groups)
                if i not in used and group[-1]['label']==item['label'] and 0 < item['seconds']-group[-1]['seconds'] <= 1.5]
            best=max(candidates,key=lambda pair:pair[1],default=(-1,0))
            if best[1] >= .3:
                groups[best[0]].append(item);used.add(best[0])
            else:
                groups.append([item]);used.add(len(groups)-1)
    return [group for group in groups if len(group)>1]


def _speech(source, directory, config, context):
    result=subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=index',
        '-of','json',str(source)],capture_output=True,timeout=15,check=True)
    if not json.loads(result.stdout).get('streams'):
        return [observation('transcript.status','no_audio','media:audio=none',**context)], dict(status='no_audio')
    if speech_config() != config:
        raise ValueError('Speech model changed before execution')
    wav=Path(directory)/'audio.wav'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-map','0:a:0','-vn','-ac','1',
        '-ar','16000','-c:a','pcm_s16le','-t','3601','-y',str(wav)],capture_output=True,timeout=120,check=True)
    output=Path(directory)/'speech.json'
    subprocess.run([sys.executable,'-m','backend.video_speech_worker',config['path'],str(wav),str(output)],
        capture_output=True,timeout=240,check=True)
    if output.stat().st_size>2*1024*1024:
        raise ValueError('Speech output limit')
    body=json.loads(output.read_text())
    if not isinstance(body, dict) or not isinstance(body.get('segments'), list) or len(body['segments'])>5000:
        raise ValueError('Invalid speech output')
    items=[]
    for segment in body['segments']:
        start,end,text=segment['start_ms'],segment['end_ms'],segment['text']
        if type(start) is not int or type(end) is not int or not 0<=start<end<=3600000 or not isinstance(text,str) or not text.strip() or len(text)>12000:
            raise ValueError('Invalid speech segment')
        locator=f'media:start_ms={start};end_ms={end}'
        items.append(observation('transcript.segment',text.strip(),locator,offset=start/1000,**context))
    if speech_config() != config:
        raise ValueError('Speech model changed during execution')
    if not items:
        items=[observation('transcript.status','silence','media:audio=present',**context)]
    return items, dict(status='transcribed' if body['segments'] else 'silence',language=body.get('language'),
        artifact_sha256=config['artifact_sha256'],engine=config['engine'],runtime_version=config['runtime_version'],
        audio_sha256=hashlib.sha256(wav.read_bytes()).hexdigest())


def extract(app, data, config, detections, *, actor_id, **context):
    validate_config(config)
    items=[]; manifest=[]
    with TemporaryDirectory(prefix='evora-video-') as directory:
        source=Path(directory)/'video.media';source.write_bytes(data)
        capture=cv2.VideoCapture(str(source))
        try:
            fps=capture.get(cv2.CAP_PROP_FPS); count=capture.get(cv2.CAP_PROP_FRAME_COUNT)
            if not capture.isOpened() or not math.isfinite(fps) or fps<=0 or not math.isfinite(count) or not 1<=count<=216000 or count/fps>3600:
                raise ValueError('Invalid video timing')
            # Spread capped samples across the entire clip, rather than truncating its beginning.
            desired=list(range(0,int(count),max(1,round(fps*config['sample_interval_seconds']))))
            if len(desired)>config['max_frames']:
                desired=sorted({round(i*(count-1)/max(1,config['max_frames']-1)) for i in range(config['max_frames'])})
            selected=set(desired);index=0
            while True:
                ok,frame=capture.read()
                if not ok:break
                if index in selected:
                    if not app.state.case_access.allows(actor_id,context['case_id']):
                        raise ValueError('Source access revoked')
                    pts=capture.get(cv2.CAP_PROP_POS_MSEC)/1000
                    offset=pts if math.isfinite(pts) and pts>=0 and (not manifest or pts>manifest[-1]['seconds']) else index/fps
                    output=BytesIO();Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).save(output,format='PNG')
                    child_context={**context,'processing_run_id':uuid5(context['processing_run_id'],f'video-frame-{index}')}
                    results=vision.extract(app,output.getvalue(),config['vision'],**child_context)
                    locator=f'frame={index}; time_offset={offset:.6f}s'
                    metadata={}
                    for result in results:
                        item=result.observation
                        if item.kind=='image.provenance':metadata=json.loads(item.raw_value);continue
                        kind={'image.description':'video.scene','image.ocr':'video.ocr','image.limitations':'video.limitations'}[item.kind]
                        items.append(observation(kind,item.raw_value,locator,offset=offset,**context))
                    manifest.append(dict(frame=index,seconds=offset,frame_sha256=metadata.pop('original_sha256'),model=metadata))
                index+=1
                if index>216000:raise ValueError('Decoded frame limit')
            if not manifest or len(manifest)!=len(selected) or index+1<count:
                raise ValueError('Incomplete video decoding')
        finally:capture.release()
        speech=dict(status='not_requested')
        if config['speech'] is not None:
            if not app.state.case_access.allows(actor_id,context['case_id']):
                raise ValueError('Source access revoked')
            extra,speech=_speech(source,directory,config['speech'],context);items.extend(extra)
    for number,group in enumerate(tracks(detections),1):
        value=json.dumps(dict(track=f'candidate-{number}',method='adjacent-sample IoU >= 0.3',identity_verified=False,detections=group))
        items.append(observation('video.track',value,f'track={number}; time_offset={group[0]["seconds"]:.6f}s',offset=group[0]['seconds'],**context))
    provenance=dict(version=VERSION,opencv_version=cv2.__version__,original_sha256=hashlib.sha256(data).hexdigest(),decoded_frames=index,
        fps=fps,sampled_frames=manifest,speech=speech,coverage='Sampled frames only; intervening events can be missed. Tracks are geometric candidates, not identity matches.')
    items.append(observation('video.provenance',json.dumps(provenance,sort_keys=True),'video=0; coverage=sampled',**context))
    return tuple(items)


class VideoRequest(vision.ImageRequest):
    sample_interval_seconds: int = Field(default=5,ge=1,le=60)
    max_frames: int = Field(default=12,ge=1,le=60)
    transcribe_speech: bool = False


@router.post('/api/v1/cases/{caseId}/evidence/{evidenceId}/video-analysis',operation_id='analyzeVideo',status_code=202)
def start_video_analysis(caseId: UUID,evidenceId: UUID,body: VideoRequest,request: Request,background: BackgroundTasks,
        grant: Annotated[CaseAccessGrant,Depends(require_case_access)]):
    from backend.processing import _versions,_json,_wire,_now,run_job
    from backend.processing_dispatch import adapter_for
    keys=request.headers.getlist('idempotency-key')
    try:
        if len(keys)!=1 or request.query_params:raise ValueError()
        key=str(UUID(keys[0]))
    except ValueError:raise AccessError(400,'INVALID_INPUT','A UUID idempotency key is required.') from None
    digest=hashlib.sha256(key.encode()).hexdigest()
    fingerprint=hashlib.sha256(_json(dict(path=request.url.path,body=body.model_dump())).encode()).hexdigest()
    with request.app.state.database.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM processing_runs WHERE actor_id=? AND case_id=? AND key_digest=?',(grant.actor.id,str(caseId),digest)).fetchone()
        if old:
            if old['fingerprint']!=fingerprint:raise AccessError(409,'IDEMPOTENCY_CONFLICT','Conflicting video-analysis request.')
            return JSONResponse(_wire(old),status_code=202)
        evidence=c.execute('SELECT * FROM evidence WHERE case_id=? AND id=?',(str(caseId),str(evidenceId))).fetchone()
        if not evidence:raise AccessError(404,'NOT_FOUND','Evidence unavailable.')
        if evidence['kind']!='video':raise AccessError(415,'VIDEO_REQUIRED','Select a video source.')
        frozen=vision.freeze_config(request.app,body.confirm_external_processing)
        if (body.expected_provider,body.expected_model,body.expected_endpoint.rstrip('/'))!=(frozen['provider'],frozen['model'],frozen['endpoint']):
            raise AccessError(409,'VISION_SETTINGS_CHANGED','Vision settings changed. Refresh and confirm the destination again.')
        if body.transcribe_speech and not (shutil.which('ffmpeg') and shutil.which('ffprobe')):
            raise AccessError(400,'AUDIO_TOOLS_REQUIRED','Install ffmpeg and ffprobe for local audio extraction.')
        enrichment=validate_config(dict(version=VERSION,vision=frozen,sample_interval_seconds=body.sample_interval_seconds,
            max_frames=body.max_frames,speech=speech_config() if body.transcribe_speech else None))
        config={key:evidence[key] for key in ('kind','sha256','size_bytes')}
        config.update(_versions(adapter_for('video')))
        config.update(processor_version=PROCESSOR_VERSION,video_understanding=enrichment)
        run_id=str(uuid4())
        c.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (run_id,str(caseId),str(evidenceId),grant.actor.id,digest,fingerprint,_json(config),PROCESSOR_VERSION,_now(),'queued'))
        result=_wire(c.execute('SELECT * FROM processing_runs WHERE id=?',(run_id,)).fetchone())
    background.add_task(run_job,request.app,run_id)
    return JSONResponse(result,status_code=202,headers={'Cache-Control':'no-store'})
