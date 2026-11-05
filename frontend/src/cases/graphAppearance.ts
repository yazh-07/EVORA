const styles = {
  person: { color: '#f59e0b', path: 'M8 8a4 4 0 1 0 8 0 4 4 0 1 0-8 0M5 21v-3a7 7 0 0 1 14 0v3' },
  vehicle: { color: '#06b6d4', path: 'm5 7 2-4h10l2 4 2 3v8H3v-8l2-3Zm0 0h14M3 12h18M6 15h2m8 0h2M6 18v3m12-3v3' },
  device: { color: '#3b82f6', path: 'M3 3h18v13H3zM8 21h8m-4-5v5' },
  ip: { color: '#6366f1', path: 'M2 12h20M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 0c-6 5-6 15 0 20 6-5 6-15 0-20' },
  location: { color: '#10b981', path: 'M12 22S4 14 4 9a8 8 0 1 1 16 0c0 5-8 13-8 13Zm-3-13a3 3 0 1 0 6 0 3 3 0 1 0-6 0' },
  account: { color: '#8b5cf6', path: 'M2 5h20v14H2zM2 10h20M6 15h4' },
  camera: { color: '#f43f5e', path: 'M2 5h14v14H2zM16 10l6-4v12l-6-4' },
  document: { color: '#94a3b8', path: 'M5 2h10l4 4v16H5zM14 2v5h5M8 11h8m-8 4h8m-8 4h5' },
};
export const forensicTypes = Object.keys(styles) as (keyof typeof styles)[];
export const isRawLogEvent = (kind: string, entityType?: string) =>
  kind === 'event' || entityType === 'event' || kind.includes('activity') || kind === 'gps.location';
export function graphAppearance(kind: string, entityType?: string) {
  const type = (entityType || kind).toLowerCase();
  const key = type === 'video' || type === 'image' ? 'camera' : type === 'face' ? 'person' : type === 'plate' ? 'vehicle' : type;
  return styles[key as keyof typeof styles] ?? { color: '#94a3b8', path: 'M5 5h14v14H5zM9 9h6v6H9z' };
}
