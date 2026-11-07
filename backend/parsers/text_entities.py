"""P13 source-literal rules and immutable text candidate projection, no identity resolution."""
from bisect import bisect_left
from dataclasses import dataclass
from ipaddress import ip_address
import re
from uuid import UUID, uuid4

from backend.parsers.candidate_entities import CandidateEntity
from backend.parsers.normalization import TimeNormalization
from backend.parsers.text_document import TextLineResult, TextObservation

ENTITY_VERSION = 'text-candidates/2'
NORMALIZER_VERSION = 'text-identifiers/2'
KINDS = frozenset(('person','organization','location','date','device','account','phone','ip'))
_IDENTIFIER = re.compile(r'(?<![\w-])(?:D|AC)-[0-9]+(?![\w-])')
_ISO_DATE = re.compile(r'(?<![0-9])\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))?(?![0-9])')
_PHONE = re.compile(r'(?<![\w+\-])\+[0-9]{8,15}(?![\w\-])')
_IP = re.compile(r'(?<![\w:.%])[0-9A-Fa-f:.%]+(?![\w:.%])')
_LOCATOR = re.compile(r'line ([1-9][0-9]*); chars=(0|[1-9][0-9]*):(0|[1-9][0-9]*)')


class TextEntityError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Text candidate projection rejected: ' + code + '.')


def canonical(kind, value):
    return str(ip_address(value)) if kind == 'ip' else value


def identifier_spans(text):
    spans = []
    for match in _IDENTIFIER.finditer(text):
        spans.append(dict(start=match.start(), end=match.end(),
                          kind='device' if match.group().startswith('D-') else 'account'))
    for match in _ISO_DATE.finditer(text):
        spans.append(dict(start=match.start(),end=match.end(),kind='date'))
    for match in _PHONE.finditer(text):
        spans.append(dict(start=match.start(), end=match.end(), kind='phone'))
    for match in _IP.finditer(text):
        raw = match.group().rstrip('.')
        if len(raw) > 64 or '%' in raw:
            continue
        try:
            ip_address(raw)
        except ValueError:
            continue
        spans.append(dict(start=match.start(), end=match.start()+len(raw), kind='ip'))
    return spans


def merge_spans(text, model_spans):
    """Literal identifiers override overlapping model predictions; exact duplicates once."""
    identifiers = identifier_spans(text)
    literals = sorted(identifiers, key=lambda span: span['start'])
    starts = [span['start'] for span in literals]
    maximum_end = []
    for span in literals:
        maximum_end.append(max(span['end'], maximum_end[-1] if maximum_end else 0))
    combined = identifiers.copy()
    filenames = list(re.finditer(r'\b[\w.-]+\.(?:txt|csv|png|jpg|jpeg|mp4|pdf|json|log)\b', text, re.I))
    for span in model_spans:
        raw = text[span['start']:span['end']]
        if raw in {'UTC', 'GMT', 'IP'} or any(m.start() <= span['start'] and span['end'] <= m.end() for m in filenames):
            continue
        preceding = bisect_left(starts, span['end']) - 1
        if preceding < 0 or maximum_end[preceding] <= span['start']:
            combined.append(span)
    return [dict(start=start,end=end,kind=kind) for start,end,kind in
            sorted({(x['start'],x['end'],x['kind']) for x in combined})]


@dataclass(frozen=True, slots=True)
class MentionObservation:
    id: UUID
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    kind: str
    source_locator: str
    raw_value: str
    normalized_value: str
    entity_key: str

    def to_wire(self):
        return dict(id=str(self.id),case_id=str(self.case_id),evidence_id=str(self.evidence_id),
            processing_run_id=str(self.processing_run_id),kind=self.kind,source_locator=self.source_locator,
            raw_value=self.raw_value,normalized_value=self.normalized_value,entity_key=self.entity_key,
            extraction_confidence=0)


@dataclass(frozen=True, slots=True)
class MentionResult:
    observation: MentionObservation
    time: TimeNormalization = TimeNormalization('',None,'not_provided',None)
    coordinate_status: str = 'not_applicable'


@dataclass(frozen=True, slots=True)
class TextProjection:
    observations: tuple
    entities: tuple[CandidateEntity, ...]


def validate_lines(rows, *, case_id):
    if not isinstance(rows,tuple) or not isinstance(case_id,UUID):
        raise TextEntityError('INVALID_CONTEXT')
    seen,context,previous,locations = set(),None,None,[]
    for index,result in enumerate(rows,1):
        if not isinstance(result,TextLineResult) or not isinstance(result.observation, TextObservation):
            raise TextEntityError('INVALID_SOURCE')
        source=result.observation
        if (any(not isinstance(x,UUID) for x in (source.id,source.case_id,source.evidence_id,source.processing_run_id))
                or source.case_id!=case_id or source.id in seen or not isinstance(source.raw_value,str)
                or '\r' in source.raw_value or '\n' in source.raw_value or '\x00' in source.raw_value
                or not isinstance(source.source_locator,str)):
            raise TextEntityError('INVALID_SOURCE')
        match=_LOCATOR.fullmatch(source.source_locator)
        if not match or int(match[1])!=index:
            raise TextEntityError('INVALID_LOCATOR')
        start,end=int(match[2]),int(match[3])
        if end-start!=len(source.raw_value) or (previous is None and start!=0) or (
                previous is not None and start-previous not in (1,2)):
            raise TextEntityError('INVALID_LOCATOR')
        current=(source.evidence_id,source.processing_run_id)
        if context is not None and context!=current:
            raise TextEntityError('MIXED_RUN')
        context,previous=current,end;seen.add(source.id);locations.append((start,end))
    return locations


def project_text_entities(rows, mentions, *, case_id, max_mentions=100000):
    locations=validate_lines(rows,case_id=case_id)
    if not isinstance(mentions,list) or len(mentions)>max_mentions:
        raise TextEntityError('MENTION_LIMIT')
    prepared,seen=[],set()
    for span in mentions:
        if (not isinstance(span,dict) or set(span)!={'line','start','end','kind'} or
            any(type(span[k]) is not int for k in ('line','start','end')) or
            not isinstance(span['kind'],str) or span['kind'] not in KINDS or not 0<=span['line']<len(rows)):
            raise TextEntityError('INVALID_SPAN')
        line,start,end,kind=(span[k] for k in ('line','start','end','kind'))
        text=rows[line].observation.raw_value
        if not 0<=start<end<=len(text) or not text[start:end].strip() or (line,start,end,kind) in seen:
            raise TextEntityError('INVALID_SPAN')
        value=text[start:end]
        try:
            normalized=canonical(kind,value)
        except ValueError:
            raise TextEntityError('INVALID_SPAN') from None
        seen.add((line,start,end,kind));prepared.append((line,start,end,kind,value,normalized))
    output=list(rows);groups={}
    for line,start,end,kind,raw,normalized in sorted(prepared):
        source=rows[line].observation;offset=locations[line][0];key=kind+':'+normalized
        mention=MentionObservation(uuid4(),case_id,source.evidence_id,source.processing_run_id,
            'text.mention.'+kind,f'line {line+1}; chars={offset+start}:{offset+end}',raw,normalized,key)
        output.append(MentionResult(mention))
        refs=groups.setdefault((kind,normalized),(set(),set()))
        refs[0].add(source.evidence_id);refs[1].update((source.id,mention.id))
    entities=tuple(CandidateEntity(uuid4(),case_id,kind,value,kind+':'+value,
        tuple(sorted(evidence,key=str)),tuple(sorted(refs,key=str)))
        for (kind,value),(evidence,refs) in sorted(groups.items()))
    return TextProjection(tuple(output),entities)
