export type SourceFocus = { source_locator: string; observation_id?: string; processing_run_id?: string };
export type MediaLocator = { box?: { x: number; y: number; width: number; height: number }; frame?: number; seconds?: number };

/** Phase 1 boxes use original-image pixels; offsets are elapsed seconds, never capture times. */
export function parseMediaLocator(source: string): MediaLocator {
  const result: MediaLocator = {};
  const segment = source.match(/^media:start_ms=(\d+);end_ms=(\d+)$/);
  if (segment && Number.isSafeInteger(Number(segment[1]))) result.seconds = Number(segment[1]) / 1000;
  const number = '(\\d+(?:\\.\\d+)?)';
  const box = source.match(new RegExp(`(?:^|[;\\s])box=${number},${number},${number},${number}(?=;|\\s|$)`));
  if (box) {
    const [x, y, width, height] = box.slice(1).map(Number) as [number, number, number, number];
    if ([x, y, width, height].every(Number.isFinite) && width > 0 && height > 0) result.box = { x, y, width, height };
  }
  const frame = source.match(/(?:^|[;\s])frame=(\d+)(?=;|\s|$)/);
  if (frame && Number.isSafeInteger(Number(frame[1]))) result.frame = Number(frame[1]);
  const time = source.match(new RegExp(`(?:^|[;\\s])time_offset=${number}s?(?=;|\\s|$)`));
  if (time && Number.isFinite(Number(time[1]))) result.seconds = Number(time[1]);
  return result;
}
export function detectionStyle(value: string) {
  if (/person:face|\bface\b/i.test(value)) return { label: 'Face region · identity unknown', color: '#f59e0b' };
  if (/person:fullbody|^person$/i.test(value)) return { label: 'Person detection · identity unknown', color: '#f59e0b' };
  if (/person:upperbody/i.test(value)) return { label: 'Upper-body detection · identity unknown', color: '#f59e0b' };
  if (/license_plate|\bplate\b/i.test(value)) return { label: 'Possible plate · unverified', color: '#06b6d4' };
  if (/\b(vehicle|car)\b/i.test(value)) return { label: 'Vehicle detection', color: '#06b6d4' };
  return { label: 'Object', color: '#8b5cf6' };
}
export function detectionVisible(locator: MediaLocator, seconds: number, isVideo: boolean, fps?: number) {
  if (!locator.box) return false;
  if (!isVideo) return true;
  // Sampled detections are shown only near their sampled time, never carried into another second.
  const at = locator.seconds ?? (fps && locator.frame !== undefined ? locator.frame / fps : undefined);
  return at !== undefined && Math.abs(seconds - at) <= (fps ? .5 / fps + .001 : .08);
}
