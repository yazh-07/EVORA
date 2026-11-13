"""Case-authorized geographic projection from immutable, validated source rows."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
import hashlib
from pathlib import Path
import re
from typing import Annotated
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from backend.auth import CaseAccessGrant, require_case_access
from backend.evidence import invalid_input
from backend.observations import _SELECTED, _validated_count, _utc_order, _valid_record, _not_found
from backend.parsers.normalization import normalize_timestamp

router = APIRouter()
_ROW = re.compile(r'(row [1-9][0-9]*|rows [1-9][0-9]*-[1-9][0-9]*), (device_id|latitude|longitude)$')


def _key(value):
    return unicodedata.normalize('NFKC', value).casefold().strip()


@lru_cache(maxsize=1)
def _places():
    index = defaultdict(list)
    for place in json.loads((Path(__file__).parent / 'geodata/places.json').read_text()):
        for alias in {_key(x) for x in place['aliases']}:
            index[alias].append(place)
    return index


def project_locations(records):
    groups = defaultdict(dict)
    approximate = []
    for item in records:
        if item['kind'].startswith('gps.'):
            match = _ROW.fullmatch(item['source_locator'])
            if not match or item['kind'] != 'gps.' + {'device_id': 'device', 'latitude': 'latitude', 'longitude': 'longitude'}[match[2]]:
                raise ValueError('Invalid GPS row')
            key = (item['evidence_id'], item['processing_run_id'], match[1])
            if item['kind'] in groups[key]:
                raise ValueError('Duplicate coordinate field')
            groups[key][item['kind']] = item
        elif item['kind'] == 'text.mention.location':
            for place in _places().get(_key(item['raw_value']), []):
                approximate.append(dict(id=item['id'] + ':' + place['name'], evidence_id=item['evidence_id'],
                    processing_run_id=item['processing_run_id'], observation_id=item['id'],
                    source_locator=item['source_locator'], basis='place_mention', label=place['name'],
                    device=None, observed_at_utc=item.get('observed_at_utc'), observed_at_raw=item.get('observed_at_raw', ''),
                    geometry=place['geometry'], precision=place['kind'], accuracy_m=None))
    points = []
    for (evidence_id, run_id, row), values in groups.items():
        if set(values) != {'gps.device', 'gps.latitude', 'gps.longitude'}:
            raise ValueError('Incomplete GPS row')
        device, latitude, longitude = (values['gps.' + key] for key in ('device', 'latitude', 'longitude'))
        raw = device.get('observed_at_raw', '')
        utc = normalize_timestamp(raw).utc_value
        if any(x.get('observed_at_raw', '') != raw or x.get('observed_at_utc') != utc for x in values.values()):
            raise ValueError('Conflicting GPS times')
        lat, lon = Decimal(latitude['normalized_value']), Decimal(longitude['normalized_value'])
        if not lat.is_finite() or not lon.is_finite() or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Invalid coordinates')
        points.append(dict(id=latitude['id'], evidence_id=evidence_id, processing_run_id=run_id,
            observation_id=latitude['id'], source_locator=latitude['source_locator'], basis='gps',
            label=device['raw_value'], device=device['raw_value'], observed_at_raw=raw, observed_at_utc=utc,
            geometry=dict(type='Point', coordinates=[float(lon), float(lat)]), precision='reported_coordinates', accuracy_m=None))
    return sorted(points + approximate, key=lambda x: (x['observed_at_utc'] or '', x['evidence_id'], x['id']))


@router.get('/api/v1/cases/{caseId}/locations', operation_id='listLocations')
def list_locations(caseId: UUID, request: Request, grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
                   limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
                   offset: Annotated[int, Query(ge=0)] = 0):
    if any(key not in {'limit', 'offset'} or len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise invalid_input()
    parameters = dict(case_id=str(grant.case_id), evidence_id=None, run_id=None)
    with request.app.state.database.connect() as connection:
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        connection.create_function('evora_observation_valid', 4, _valid_record, deterministic=True)
        connection.execute('BEGIN')
        _validated_count(connection, parameters)
        revision = hashlib.sha256('|'.join(row['id'] for row in connection.execute(_SELECTED + 'SELECT id FROM selected ORDER BY evidence_id', parameters)).encode()).hexdigest()
        rows = connection.execute(_SELECTED + "SELECT value FROM records WHERE json_extract(value,'$.kind') IN ('gps.device','gps.latitude','gps.longitude','text.mention.location')", parameters).fetchall()
        try:
            items = project_locations([json.loads(row['value']) for row in rows])
        except (ValueError, KeyError, InvalidOperation, TypeError):
            raise _not_found() from None
    return JSONResponse(dict(case_id=str(grant.case_id), items=items[offset:offset + limit], total=len(items), limit=limit,
        offset=offset, map_detail='world_overview', gazetteer='Natural Earth 1:110m', scope='latest_completed_processing', revision=revision), headers={'Cache-Control': 'no-store'})
