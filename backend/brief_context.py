"""Deterministic source-balanced brief context; primary content precedes derived noise."""
import json
import re


def select_observations(records, budget=20000):
    groups = {}
    primary = []
    secondary = []
    for record in records:
        kind = record['kind']
        if kind in {'image.detection', 'video.frame_detection', 'image.provenance', 'video.provenance', 'video.track'}:
            continue
        (secondary if kind.startswith('text.mention.') else primary).append(record)
    # A literal source line already contains its NER mentions; do not send it twice.
    literal_sources = {r['evidence_id'] for r in primary if r['kind'] == 'text.line'}
    primary.extend(r for r in secondary if r['evidence_id'] not in literal_sources)
    def order(record):
        locator = record.get('source_locator', '')
        number = re.search(r'(?:line |rows? |frame=)(\d+)', locator)
        return (0 if record['kind'] in {'image.ocr', 'video.ocr'} else 1,
                int(number[1]) if number else 0, locator, record['kind'], record['id'])
    for record in primary:
        groups.setdefault(record['evidence_id'], []).append(record)
    for group in groups.values():
        group.sort(key=order)
    result = []
    for index in range(max(map(len, groups.values()), default=0)):
        for evidence_id in sorted(groups):
            group = groups[evidence_id]
            if index >= len(group):
                continue
            record = group[index]
            item = {key: record[key] for key in ('id', 'evidence_id', 'kind', 'source_locator', 'observed_at_utc', 'observed_at_raw') if key in record}
            value = record.get('normalized_value', record.get('raw_value', ''))
            item['normalized_value'] = value[:2400]
            if 'raw_value' in record and record['raw_value'] != value:
                item['raw_value'] = record['raw_value'][:2400]
            if len(value) > 2400:
                item['text_truncated'] = True
            size = len(json.dumps(item, separators=(',', ':'), ensure_ascii=False))
            if size <= budget:
                result.append(item)
                budget -= size
    return result
