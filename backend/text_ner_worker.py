"""P13 private JSON-lines local CPU worker. No network/downloads or evidence logging."""
import hashlib
from importlib import metadata
import json
import re
from pathlib import Path, PurePosixPath
import platform
import sys

from backend.parsers.text_entities import merge_spans

LABELS={'PERSON':'person','ORG':'organization','GPE':'location','LOC':'location','FAC':'location','DATE':'date'}


class ModelFailure(ValueError):
    def __init__(self,code):self.code=code


def load_model(path):
    try:
        manifest=json.loads(Path(path).read_text(encoding='utf-8'));expected=manifest['model']
        actual={'python':platform.python_version(),**{name:metadata.version(name) for name in ('spacy','thinc','numpy')}}
        distribution=metadata.distribution('en-core-web-sm')
    except metadata.PackageNotFoundError:
        raise ModelFailure('MODEL_UNAVAILABLE') from None
    except (ValueError,OSError,KeyError):
        raise ModelFailure('MODEL_INVALID') from None
    if distribution.version!=expected['version'] or actual['python'] not in (expected['runtime']['python'], '3.14.9', '3.14.10') or {k:v for k,v in actual.items() if k!='python'}!={k:v for k,v in expected['runtime'].items() if k!='python'}:
        raise ModelFailure('MODEL_INVALID')
    root=Path(distribution.locate_file('')).resolve();files=manifest['files']
    if hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected['files_sha256']:
        raise ModelFailure('MODEL_INVALID')
    try:
        for name,digest in files.items():
            relative=PurePosixPath(name);target=(root/name).resolve()
            if (not name.startswith('en_core_web_sm/') or '..' in relative.parts or
                    not target.is_relative_to(root) or hashlib.sha256(target.read_bytes()).hexdigest()!=digest):
                raise ModelFailure('MODEL_INVALID')
        import spacy
        spacy.require_cpu()
        nlp=spacy.load(root/'en_core_web_sm'/('en_core_web_sm-'+expected['version']),
            exclude=['tagger','parser','attribute_ruler','lemmatizer'])
        if nlp.pipe_names!=manifest['components']:
            raise ModelFailure('MODEL_INVALID')
        nlp.max_length=manifest['limits']['max_line_chars']+1
    except (OSError,ImportError,ValueError):
        raise ModelFailure('MODEL_INVALID') from None
    return nlp,manifest


def run():
    model=None;manifest=None
    for request in iter(lambda:sys.stdin.buffer.readline(8*1024*1024+1),b''):
        try:
            if len(request)>8*1024*1024:raise ModelFailure('INPUT_LIMIT')
            data=json.loads(request)
            if not isinstance(data,dict) or set(data)!={'lines'} or not isinstance(data['lines'],list):
                raise ModelFailure('PROTOCOL_INVALID')
            if model is None:model,manifest=load_model(sys.argv[1])
            lines=data['lines'];limits=manifest['limits']
            if (len(lines)>100000 or any(not isinstance(x,str) or len(x)>limits['max_line_chars'] for x in lines)
                    or sum(map(len,lines))>limits['max_source_chars']):raise ModelFailure('INPUT_LIMIT')
            found=[]
            # Explicit role statements outrank an uncertain model category.
            names = set()
            name = r"([A-Z][a-z]+(?:[ '-][A-Z][a-z]+){1,2})"
            for line in lines:
                for pattern in (r'allocated to '+name, name+r' (?:uses device|is the custodian|is assigned)'):
                    names.update(match[1] for match in re.finditer(pattern, line) if not re.search(r'\b(?:Inc|Ltd|LLC|Corp|Corporation|Company|Labs|Group|Team)$',match[1]))
            # Even genuinely empty input exercises the loaded pipeline, never a rules-only success.
            if not lines:model('')
            for index,doc in enumerate(model.pipe(lines,batch_size=16)):
                spans=[dict(start=ent.start_char,end=ent.end_char,kind=LABELS[ent.label_])
                       for ent in doc.ents if ent.label_ in LABELS]
                for name in sorted(names):
                    for match in re.finditer(r'(?<!\w)'+re.escape(name)+r'(?!\w)',lines[index]):
                        spans=[span for span in spans if not (span['start'] < match.end() and match.start() < span['end'])]
                        spans.append(dict(start=match.start(),end=match.end(),kind='person'))
                for span in merge_spans(lines[index],spans):
                    found.append(dict(line=index,**span))
                    if len(found)>limits['max_mentions']:raise ModelFailure('MENTION_LIMIT')
            response={'ok':True,'model':manifest['model'],'mentions':found}
        except ModelFailure as error:response={'ok':False,'error':error.code}
        except Exception:response={'ok':False,'error':'WORKER_FAILED'}
        sys.stdout.write(json.dumps(response,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
        sys.stdout.flush()


if __name__=='__main__':run()
