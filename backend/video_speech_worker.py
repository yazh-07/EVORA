"""Bounded subprocess entry point; reads an already downloaded local Whisper model."""
import json
from pathlib import Path
import sys
import wave


def main():
    from faster_whisper import WhisperModel
    import numpy as np
    # FFmpeg already produced canonical PCM. Avoid codec/version-dependent PyAV decoding.
    with wave.open(sys.argv[2], 'rb') as audio:
        if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (1,16000,2) or audio.getnframes()>3600*16000:
            raise ValueError('Invalid normalized speech audio')
        samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2').astype(np.float32)/32768
    model=WhisperModel(sys.argv[1],device='cpu',compute_type='int8',local_files_only=True,cpu_threads=4,num_workers=1)
    segments,info=model.transcribe(samples,beam_size=5,vad_filter=True,condition_on_previous_text=False)
    output=[]
    for segment in segments:
        if len(output)>=5000:raise ValueError('Segment limit')
        if segment.text.strip():
            output.append(dict(start_ms=max(0,round(segment.start*1000)),end_ms=round(segment.end*1000),text=segment.text.strip()))
    Path(sys.argv[3]).write_text(json.dumps(dict(segments=output,language=info.language)))


if __name__=='__main__':main()
