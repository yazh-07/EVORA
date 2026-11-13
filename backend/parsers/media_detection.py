"""Local visual candidates with exact source pixels; no identity recognition.

Cascade weights are retained verbatim. extraction_confidence is their sigmoid,
not a calibrated probability. Candidates are scoped to each source detection;
we never claim that similar faces across frames are the same person.
"""
from dataclasses import dataclass
from io import BytesIO
import hashlib
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid5

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from backend.parsers.candidate_entities import CandidateEntity, CandidateObservation
from backend.parsers.normalization import NormalizationResult, TimeNormalization, normalize_timestamp
from backend import plates
from backend.parsers.normalization import NormalizedObservation
from backend.parsers.source_events import SourceEvent, SourceEventResult

PARSER_VERSION = 'media-detection/3'
PROCESSOR_VERSION = 'processing-lifecycle/15'
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_DATA_ROWS = 10000  # detections
MAX_FRAMES = 3600
MAX_PIXELS = 25_000_000
MAX_DECODED_FRAMES = 216000
_CASCADES = (
    ('person:face', 'haarcascade_frontalface_default.xml'),
    ('person:fullbody', 'haarcascade_fullbody.xml'),
    ('person:upperbody', 'haarcascade_upperbody.xml'),
    ('vehicle:license_plate', 'haarcascade_russian_plate_number.xml'),
)


class MediaDetectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Media processing rejected: ' + code)


def _cascade_path(filename):
    for root in (Path('/usr/share/opencv5/haarcascades'), Path(cv2.data.haarcascades)):
        path = root / filename
        if path.is_file():
            return path
    raise MediaDetectionError('CLASSIFIER_UNAVAILABLE')


def model_info():
    return dict(opencv=cv2.__version__, pillow=Image.__version__, numpy=np.__version__,
                cascades={name: hashlib.sha256(_cascade_path(name).read_bytes()).hexdigest()
                          for _, name in _CASCADES}, confidence_transform='sigmoid_uncalibrated', plates=plates.model_info())


def _classifiers():
    result = []
    for label, filename in _CASCADES:
        classifier = cv2.CascadeClassifier(str(_cascade_path(filename)))
        if classifier.empty():
            raise MediaDetectionError('CLASSIFIER_UNAVAILABLE')
        result.append((label, filename, classifier))
    return result


def detect_frame(frame, classifiers):
    """Return native-resolution boxes and the actual final-stage decision weights."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for label, filename, classifier in classifiers:
        boxes, _, weights = classifier.detectMultiScale3(
            gray, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24), outputRejectLevels=True)
        for box, weight in zip(boxes, weights):
            weight = float(np.asarray(weight).item())
            if math.isfinite(weight):
                yield label, tuple(int(x) for x in box), weight, filename


@dataclass(frozen=True, slots=True)
class VisualObservation(CandidateObservation):
    detector_weight: float = 0.0
    detector: str = ''

    def to_wire(self):
        return CandidateObservation.to_wire(self) | dict(detector_weight=self.detector_weight,
                                                        detector=self.detector)


@dataclass(frozen=True, slots=True)
class MediaProjection:
    observations: tuple
    entities: tuple
    events: tuple


def _image_frames(source):
    try:
        with Image.open(BytesIO(source)) as picture:
            if picture.width * picture.height > MAX_PIXELS:
                raise MediaDetectionError('PIXEL_LIMIT')
            exif = picture.getexif()
            exif = exif.get_ifd(34665) if 34665 in exif else exif
            raw = str(exif.get(36867, '')).replace(':', '-', 2)
            offset = exif.get(36881, '')
            time = normalize_timestamp(raw + str(offset)) if raw else TimeNormalization('', None, 'missing_capture_time', None)
            # Keep the original stored pixel orientation so boxes address source pixels.
            frame = cv2.cvtColor(np.asarray(picture.convert('RGB')), cv2.COLOR_RGB2BGR)
            yield 0, 0.0, frame, time
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        if isinstance(error, MediaDetectionError):
            raise
        raise MediaDetectionError('INVALID_IMAGE') from None


def _video_frames(source):
    with TemporaryDirectory(prefix='evora-media-') as directory:
        path = Path(directory) / 'source.media'
        path.write_bytes(source)
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise MediaDetectionError('INVALID_VIDEO')
            fps = capture.get(cv2.CAP_PROP_FPS)
            count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
            if not math.isfinite(fps) or fps <= 0:
                raise MediaDetectionError('INVALID_FRAME_RATE')
            if count > MAX_DECODED_FRAMES or count / fps > MAX_FRAMES:
                raise MediaDetectionError('FRAME_LIMIT')
            width, height = capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            if width * height > MAX_PIXELS:
                raise MediaDetectionError('PIXEL_LIMIT')
            index, sampled, next_second = 0, 0, 0.0
            previous_offset = -1.0
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if index >= MAX_DECODED_FRAMES:
                    raise MediaDetectionError('FRAME_LIMIT')
                if frame.shape[0] * frame.shape[1] > MAX_PIXELS:
                    raise MediaDetectionError('PIXEL_LIMIT')
                # Prefer container presentation timestamps (handles variable frame rate).
                pts = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
                offset = pts if math.isfinite(pts) and pts > previous_offset else index / fps
                previous_offset = offset
                if offset + 1e-9 >= next_second:
                    sampled += 1
                    if sampled > MAX_FRAMES:
                        raise MediaDetectionError('FRAME_LIMIT')
                    raw = f'time_offset={offset:.6f}s'
                    yield index, offset, frame, TimeNormalization(raw, None, 'relative_media_time', None)
                    next_second = math.floor(offset) + 1.0
                index += 1
            if index == 0 or (count > 0 and index + 1 < count):
                raise MediaDetectionError('INVALID_VIDEO')
        finally:
            capture.release()


def parse_media(source, *, kind, case_id, evidence_id, processing_run_id):
    if not isinstance(source, bytes) or kind not in ('image', 'video'):
        raise MediaDetectionError('INVALID_SOURCE')
    if any(not isinstance(value, UUID) for value in (case_id, evidence_id, processing_run_id)):
        raise MediaDetectionError('INVALID_CONTEXT')
    if len(source) > MAX_SOURCE_BYTES:
        raise MediaDetectionError('BYTE_LIMIT')
    observations, entities, events = [], [], []
    plate_model = plates.model_info()
    classifiers = _classifiers()
    frames = _image_frames(source) if kind == 'image' else _video_frames(source)
    try:
        for index, offset, frame, time in frames:
            hits = plates.detect(frame) if plate_model else []
            detections = [item for item in detect_frame(frame, classifiers) if not plate_model or item[0] != 'vehicle:license_plate']
            detections.extend(('vehicle:license_plate', tuple(hit['box']), hit['detector_score'], 'onnx:plate-detector') for hit in hits)
            readings = {tuple(hit['box']): hit for hit in hits}
            for label, box, weight, detector in detections:
                if len(observations) >= MAX_DATA_ROWS:
                    raise MediaDetectionError('DETECTION_LIMIT')
                x, y, w, h = box
                if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > frame.shape[1] or y+h > frame.shape[0]:
                    raise MediaDetectionError('INVALID_BOX')
                locator = f'frame={index}; time_offset={offset:.6f}s; box={x},{y},{w},{h}'
                oid = uuid5(processing_run_id, label + ':' + locator)
                entity_id = uuid5(oid, 'candidate')
                entity_kind = 'visual_candidate'
                # Source-scoped labels prevent fabricated cross-evidence identity matches.
                name = f'{evidence_id}:frame-{index}:{entity_kind}-{len(entities)+1}'
                key = f'{entity_kind}:{name}'
                value = f'{label} [{x}, {y}, {w}, {h}]'
                score = weight if detector == 'onnx:plate-detector' else 1 / (1 + math.exp(-max(-700, min(700, weight))))
                observation = VisualObservation(oid, case_id, evidence_id, processing_run_id,
                    'image.detection' if kind == 'image' else 'video.frame_detection',
                    locator, value, value, time.raw_value, score, time.utc_value, key, weight, detector)
                observations.append(NormalizationResult(observation, time, 'not_applicable'))
                if detector == 'onnx:plate-detector':
                    reading = readings[box]
                    plate_text = NormalizedObservation(uuid5(oid, 'reading'), case_id, evidence_id, processing_run_id,
                        'image.plate_reading' if kind == 'image' else 'video.plate_reading', locator,
                        reading['text'] or 'Unreadable plate', reading['text'], time.raw_value, reading['ocr_score'], time.utc_value)
                    observations.append(NormalizationResult(plate_text, time, 'not_applicable'))
                entities.append(CandidateEntity(entity_id, case_id, entity_kind, name, key,
                                                (evidence_id,), (oid,), score))
                event = SourceEvent(uuid5(oid, 'event'), case_id, 'visual.detected',
                    f'Visual candidate {value}; {locator}; identity unverified.',
                    (evidence_id,), (oid,), (entity_id,), time.raw_value, time.utc_value, score)
                events.append(SourceEventResult(event, time, PARSER_VERSION))
    except cv2.error:
        raise MediaDetectionError('DECODE_OR_CLASSIFIER_FAILED') from None
    finally:
        frames.close()
    return MediaProjection(tuple(observations), tuple(entities), tuple(events))


def parse_image(source, **context):
    return parse_media(source, kind='image', **context)


def parse_video(source, **context):
    return parse_media(source, kind='video', **context)
