import { useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { FileSource, PMTiles, Protocol } from 'pmtiles';
import type { FeatureCollection, Geometry, Position } from 'geojson';
import type { components } from '../api/schema';
import { useApiClient } from '../api/ApiProvider';
import type { SourceFocus } from './mediaLocators';

type Location = components['schemas']['LocationRecord'];
type Basemap = 'offline' | 'streets' | 'satellite';
const mapPreferenceKey = 'evora-map-view';
function preferredBasemap(): Basemap {
  try { const value = localStorage.getItem(mapPreferenceKey); if (value === 'offline' || value === 'satellite') return value; } catch { /* Use the street map when storage is unavailable. */ }
  return 'streets';
}
export const satelliteSource: maplibregl.RasterSourceSpecification = {
  type: 'raster',
  tiles: ['https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
  tileSize: 256, maxzoom: 19,
  attribution: 'Imagery © <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri, Vantor, Earthstar Geographics, and the GIS User Community</a>',
};
export function streetViewUrl(row: Location): string | undefined {
  if (row.basis !== 'gps' || row.geometry.type !== 'Point') return;
  const [longitude, latitude] = row.geometry.coordinates;
  if (typeof latitude !== 'number' || typeof longitude !== 'number' || !Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return;
  const url = new URL('https://www.google.com/maps/@');
  url.search = new URLSearchParams({ api: '1', map_action: 'pano', viewpoint: `${latitude},${longitude}` }).toString();
  return url.href;
}
export function locationTracks(points: Location[]): FeatureCollection {
  const groups = new Map<string, Location[]>();
  for (const point of points) if (point.basis === 'gps' && point.observed_at_utc && point.geometry.type === 'Point') {
    const key = `${point.evidence_id}:${point.processing_run_id}:${point.device}`;
    groups.set(key, [...(groups.get(key) ?? []), point]);
  }
  const features: FeatureCollection['features'] = [];
  for (const rows of groups.values()) {
    rows.sort((a, b) => Date.parse(a.observed_at_utc!) - Date.parse(b.observed_at_utc!) || a.id.localeCompare(b.id));
    let segment: Position[] = [], previous: Location | undefined;
    const flush = () => { if (segment.length > 1) features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: segment } }); segment = []; };
    for (const row of rows) {
      const coords = row.geometry.coordinates as Position;
      const gap = previous ? Date.parse(row.observed_at_utc!) - Date.parse(previous.observed_at_utc!) : 0;
      if (previous && (gap <= 0 || gap > 3600000 || Math.abs(Number(coords[0]) - Number(previous.geometry.coordinates[0])) > 180)) flush();
      segment.push(coords); previous = row;
    }
    flush();
  }
  return { type: 'FeatureCollection', features };
}
function dataFor(rows: Location[]): FeatureCollection {
  return { type: 'FeatureCollection', features: rows.map(row => ({ type: 'Feature', properties: { record_id: row.id, basis: row.basis, label: row.label }, geometry: row.geometry as Geometry })) };
}
function boundsFor(rows: Location[]) {
  const bounds = new maplibregl.LngLatBounds();
  const visit = (value: unknown) => { if (!Array.isArray(value)) return; if (typeof value[0] === 'number' && typeof value[1] === 'number') bounds.extend([value[0], value[1]]); else value.forEach(visit); };
  rows.forEach(row => visit(row.geometry.coordinates)); return bounds;
}
const worldStyle: maplibregl.StyleSpecification = { version: 8, sources: { countries: { type: 'geojson', data: '/maps/countries.geojson' } }, layers: [
  { id: 'sea', type: 'background', paint: { 'background-color': '#e7eff4' } },
  { id: 'land', type: 'fill', source: 'countries', paint: { 'fill-color': '#faf9ee', 'fill-outline-color': '#bfcac9' } },
] };

export function LocationsWorkspace({ caseId, inspectEvidence }: { caseId: string; inspectEvidence: (id: string, focus?: SourceFocus) => void }) {
  const client = useApiClient();
  const [records, setRecords] = useState<Location[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState(''), [total, setTotal] = useState(0), [revision, setRevision] = useState(0);
  const [device, setDevice] = useState(''), [from, setFrom] = useState(''), [through, setThrough] = useState(''), [areas, setAreas] = useState(true), [tracks, setTracks] = useState(false);
  const [selectedId, setSelectedId] = useState(''), [playing, setPlaying] = useState(false), [cursor, setCursor] = useState(0), [page, setPage] = useState(0);
  const [basemap, setBasemap] = useState<Basemap>(preferredBasemap), [ready, setReady] = useState(false);
  const [mapLoading, setMapLoading] = useState(true);
  const localMapLabel = useRef('Offline · world overview');
  const [mapError, setMapError] = useState(''), [mapLabel, setMapLabel] = useState('Offline · world overview');
  const container = useRef<HTMLDivElement>(null), map = useRef<maplibregl.Map | null>(null), mapReady = useRef(false), mapFit = useRef(false), protocol = useRef<Protocol | undefined>(undefined);
  const fileInput = useRef<HTMLInputElement>(null), recordRef = useRef<Location[]>([]), currentData = useRef<{ points: FeatureCollection; lines: FeatureCollection }>({ points: dataFor([]), lines: locationTracks([]) });
  useEffect(() => {
    const request = new AbortController(); const session = client.getSessionVersion(); setLoading(true); setError(''); setRecords([]); setSelectedId(''); setPlaying(false); mapFit.current = false;
    const unsubscribe = client.subscribeSession(() => { request.abort(); setRecords([]); resetOnlineMap(); });
    void (async () => {
      const rows: Location[] = []; const ids = new Set<string>(); let count: number | undefined, snapshot: string | undefined;
      do {
        const result = await client.request('get', '/api/v1/cases/{caseId}/locations', { path: { caseId }, query: { limit: 1000, offset: rows.length }, signal: request.signal });
        if ((snapshot !== undefined && snapshot !== result.revision) || result.case_id !== caseId || !Array.isArray(result.items) || result.offset !== rows.length || result.limit !== 1000 || !Number.isSafeInteger(result.total) || result.total < 0 || result.items.length !== Math.min(1000, result.total - rows.length) || (count !== undefined && count !== result.total)) throw Error();
        snapshot = result.revision; count = result.total;
        for (const row of result.items) { if (ids.has(row.id) || !['gps', 'place_mention'].includes(row.basis) || !['Point', 'Polygon', 'MultiPolygon'].includes(row.geometry.type)) throw Error(); ids.add(row.id); rows.push(row); }
      } while (rows.length < count && rows.length < 20000);
      if (!request.signal.aborted && session === client.getSessionVersion()) { setRecords(rows); setTotal(count ?? 0); }
    })().catch(() => { if (!request.signal.aborted) setError('Could not load location records.'); }).finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => { request.abort(); unsubscribe(); };
  }, [client, caseId, revision]);
  const filtered = useMemo(() => records.filter(row => (areas || row.basis === 'gps') && (!device || `${row.evidence_id}:${row.device}` === device) && (!from || !!row.observed_at_utc && row.observed_at_utc >= `${from}T00:00:00`) && (!through || !!row.observed_at_utc && row.observed_at_utc <= `${through}T23:59:59.999Z`)), [records, device, from, through, areas]);
  recordRef.current = filtered;
  const dated = useMemo(() => filtered.filter(row => row.basis === 'gps' && row.observed_at_utc).sort((a, b) => Date.parse(a.observed_at_utc!) - Date.parse(b.observed_at_utc!)), [filtered]);
  const selected = filtered.find(row => row.id === selectedId);
  const selectedStreetView = selected ? streetViewUrl(selected) : undefined;
  const devices = [...new Map(records.filter(row => row.device).map(row => [`${row.evidence_id}:${row.device}`, row.label])).entries()];
  currentData.current = { points: dataFor(filtered), lines: tracks && total === records.length ? locationTracks(filtered) : locationTracks([]) };
  const fit = () => { if (mapReady.current && filtered.length) { const bounds = boundsFor(filtered); if (!bounds.isEmpty()) map.current?.fitBounds(bounds, { padding: 50, maxZoom: 14, duration: 0 }); } };
  useEffect(() => {
    if (!container.current) return;
    maplibregl.setWorkerUrl('/assets/maplibre-gl-worker.mjs');
    let instance: maplibregl.Map;
    try { instance = new maplibregl.Map({ container: container.current, style: worldStyle, center: [15, 20], zoom: 1.5, attributionControl: false, fadeDuration: 0 }); }
    catch { setMapError('Map unavailable. Location records remain accessible below.'); return; }
    map.current = instance;
    instance.on('error', () => { setMapError('Some map layers could not load. Location records remain available.'); setMapLoading(false); });
    instance.on('dataloading', () => setMapLoading(true));
    instance.on('idle', () => setMapLoading(false));
    const localProtocol = protocol.current = new Protocol();
    maplibregl.addProtocol('pmtiles', localProtocol.tile);
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    instance.addControl(new maplibregl.AttributionControl({ customAttribution: 'Natural Earth · public domain' }), 'bottom-right');
    instance.on('load', () => {
      instance.addSource('evidence', { type: 'geojson', data: { ...currentData.current.points, features: currentData.current.points.features.filter(feature => feature.geometry.type === 'Point') }, cluster: true, clusterRadius: 40, clusterMaxZoom: 16 });
      instance.addSource('areas', { type: 'geojson', data: { ...currentData.current.points, features: currentData.current.points.features.filter(feature => feature.geometry.type !== 'Point') } });
      instance.addSource('tracks', { type: 'geojson', data: currentData.current.lines });
      instance.addLayer({ id: 'approximate-areas', type: 'fill', source: 'areas', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': '#d69729', 'fill-opacity': .2, 'fill-outline-color': '#ae6d0d' } });
      instance.addLayer({ id: 'recorded-paths', type: 'line', source: 'tracks', paint: { 'line-color': '#227c74', 'line-width': 2, 'line-dasharray': [3, 2] } });
      instance.addLayer({ id: 'location-points', type: 'circle', source: 'evidence', filter: ['all', ['==', ['geometry-type'], 'Point'], ['!', ['has', 'point_count']]], paint: { 'circle-radius': 7, 'circle-color': ['case', ['==', ['get', 'basis'], 'gps'], '#228b80', '#d69729'], 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' } });
      mapReady.current = true; setReady(true); instance.resize();
      changeBasemap(basemap);
      const rows = recordRef.current; if (rows.length) { const bounds = boundsFor(rows); if (!bounds.isEmpty()) instance.fitBounds(bounds, { padding: 50, maxZoom: 14, duration: 0 }); mapFit.current = true; }
    });
    instance.on('click', event => { const feature = instance.queryRenderedFeatures(event.point, { layers: ['location-points', 'approximate-areas'].filter(id => !!instance.getLayer(id)) })[0]; if (feature?.properties?.record_id) { setSelectedId(String(feature.properties.record_id)); setPlaying(false); } });
    instance.on('mouseenter', 'location-points', () => { instance.getCanvas().style.cursor = 'pointer'; });
    instance.on('mouseleave', 'location-points', () => { instance.getCanvas().style.cursor = ''; });
    const clusters = new Map<string, maplibregl.Marker>();
    instance.on('render', () => {
      if (!mapReady.current || !instance.isSourceLoaded('evidence')) return;
      const visible = new Set<string>();
      for (const feature of instance.querySourceFeatures('evidence')) {
        if (!feature.properties?.cluster || feature.geometry.type !== 'Point') continue;
        const id = String(feature.properties.cluster_id); if (visible.has(id)) continue; visible.add(id);
        if (!clusters.has(id)) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'map-cluster'; button.textContent = String(feature.properties.point_count); button.setAttribute('aria-label', `${feature.properties.point_count} location records. Zoom in`);
          button.addEventListener('click', () => { void (instance.getSource('evidence') as maplibregl.GeoJSONSource).getClusterExpansionZoom(Number(id)).then(zoom => { if (map.current === instance) instance.easeTo({ center: feature.geometry.type === 'Point' ? feature.geometry.coordinates as [number, number] : [0, 0], zoom, duration: 0 }); }); });
          clusters.set(id, new maplibregl.Marker({ element: button }).setLngLat(feature.geometry.coordinates as [number, number]).addTo(instance));
        }
      }
      for (const [id, marker] of clusters) if (!visible.has(id)) { marker.remove(); clusters.delete(id); }
    });
    const observer = new ResizeObserver(() => instance.resize()); observer.observe(container.current);
    return () => { observer.disconnect(); clusters.forEach(marker => marker.remove()); mapReady.current = false; instance.remove(); map.current = null; maplibregl.removeProtocol('pmtiles'); };
  }, []);
  useEffect(() => {
    setPage(0); setPlaying(false); setCursor(0);
    if (!mapReady.current) return;
    (map.current?.getSource('evidence') as maplibregl.GeoJSONSource)?.setData({ ...currentData.current.points, features: currentData.current.points.features.filter(feature => feature.geometry.type === 'Point') });
    (map.current?.getSource('areas') as maplibregl.GeoJSONSource)?.setData({ ...currentData.current.points, features: currentData.current.points.features.filter(feature => feature.geometry.type !== 'Point') });
    (map.current?.getSource('tracks') as maplibregl.GeoJSONSource)?.setData(currentData.current.lines);
    if (!mapFit.current && filtered.length) { fit(); mapFit.current = true; }
  }, [filtered, tracks]);
  useEffect(() => { if (!selected || !mapReady.current) return; const bounds = boundsFor([selected]); if (!bounds.isEmpty()) map.current?.fitBounds(bounds, { maxZoom: selected.basis === 'gps' ? 14 : 7, padding: 90, duration: 0 }); }, [selected]);
  useEffect(() => { if (!playing || !dated.length) return; const timer = setInterval(() => setCursor(value => { const next = value + 1; if (next >= dated.length) { setPlaying(false); return value; } setSelectedId(dated[next]!.id); return next; }), 900); return () => clearInterval(timer); }, [playing, dated]);
  function changeBasemap(next: Basemap) {
    const instance = map.current; if (!instance || !mapReady.current || !client.hasToken()) return;
    try {
      resetOnlineMap();
      for (const layer of instance.getStyle().layers ?? []) if ('source' in layer && layer.source === 'regional') instance.setLayoutProperty(layer.id, 'visibility', next === 'offline' ? 'visible' : 'none');
      if (next !== 'offline') {
        const id = next === 'satellite' ? 'online-satellite' : 'online-streets';
        instance.addSource(id, next === 'satellite' ? satelliteSource : { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, maxzoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' });
        instance.addLayer({ id, type: 'raster', source: id, paint: { 'raster-fade-duration': 0 } }, 'approximate-areas');
      }
      setBasemap(next); setMapError('');
      try { localStorage.setItem(mapPreferenceKey, next); } catch { /* Map choices still work without storage. */ }
      setMapLabel(next === 'satellite' ? 'Online · Satellite · Esri' : next === 'streets' ? 'Online · OpenStreetMap' : localMapLabel.current);
    } catch { setMapError('Could not change the basemap. Try Offline.'); }
  }
  function resetOnlineMap() {
    const instance = map.current;
    if (!instance || !mapReady.current) return;
    for (const id of ['online-streets', 'online-satellite']) {
      if (instance.getLayer(id)) instance.removeLayer(id);
      if (instance.getSource(id)) instance.removeSource(id);
    }
  }
  async function openMap(file: File) {
    if (!map.current || !mapReady.current || !protocol.current) return;
    try {
      const archive = new PMTiles(new FileSource(file)); protocol.current.add(archive);
      const header = await archive.getHeader(), metadata = await archive.getMetadata(); const instance = map.current; if (!instance) return;
      const layers = ((metadata as { vector_layers?: { id: string }[] }).vector_layers as { id: string }[] | undefined) ?? [];
      if (header.tileType === 1 && !layers.some(layer => /^(water|landuse|buildings?|landcover|roads|transportation|boundaries|boundary|waterway)$/.test(layer.id))) throw Error('Unsupported layers');
      if (![1, 2, 3, 4].includes(header.tileType)) throw Error('Unsupported tile format');
      const attribution = document.createElement('span');
      attribution.textContent = typeof (metadata as { attribution?: string }).attribution === 'string' ? (metadata as { attribution: string }).attribution.replace(/<[^>]*>/g, '') : '';
      if (instance.getSource('regional')) { instance.getStyle().layers?.filter(layer => 'source' in layer && layer.source === 'regional').forEach(layer => instance.removeLayer(layer.id)); instance.removeSource('regional'); }
      const source = `pmtiles://${archive.source.getKey()}`;
      if (header.tileType !== 1) { instance.addSource('regional', { type: 'raster', tiles: [`${source}/{z}/{x}/{y}`], minzoom: header.minZoom, maxzoom: header.maxZoom, tileSize: 256, attribution: attribution.innerHTML }); instance.addLayer({ id: 'regional-raster', type: 'raster', source: 'regional' }, 'approximate-areas'); }
      else {
        instance.addSource('regional', { type: 'vector', tiles: [`${source}/{z}/{x}/{y}`], minzoom: header.minZoom, maxzoom: header.maxZoom, attribution: attribution.innerHTML });
        for (const layer of layers) {
          if (/^(water|landuse|buildings?|landcover)$/.test(layer.id)) instance.addLayer({ id: `regional-${layer.id}`, type: 'fill', source: 'regional', 'source-layer': layer.id, paint: { 'fill-color': layer.id === 'water' ? '#dceaf0' : /building/.test(layer.id) ? '#c7ceca' : '#e7eddb' } }, 'approximate-areas');
          if (/^(roads|transportation|boundaries|boundary|waterway)$/.test(layer.id)) instance.addLayer({ id: `regional-${layer.id}`, type: 'line', source: 'regional', 'source-layer': layer.id, paint: { 'line-color': layer.id === 'waterway' ? '#97bccc' : '#a9b4ad', 'line-width': 1.5 } }, 'approximate-areas');
        }
      }
      resetOnlineMap(); setBasemap('offline'); localMapLabel.current = `Local map · ${file.name}`;
      try { localStorage.setItem(mapPreferenceKey, 'offline'); } catch { /* The archive remains available for this session. */ }
      setMapLabel(localMapLabel.current); setMapError('');
      instance.fitBounds([[header.minLon, header.minLat], [header.maxLon, header.maxLat]], { padding: 30, duration: 0 });
    } catch { setMapError('Could not open this map package. The world overview is still available.'); }
  }
  return <section className="locations-workspace" aria-label="Locations" aria-busy={loading}>
    <header className="workspace-section-heading"><h2>Locations</h2><div className="location-actions">
      <label className="basemap-picker"><span className="sr-only">Basemap</span><select aria-label="Basemap" value={basemap} disabled={!ready} title="Street and satellite views use online tiles" onChange={event => changeBasemap(event.target.value as Basemap)}>
        <option value="streets">Street map</option><option value="satellite">Satellite</option><option value="offline">Offline map</option>
      </select></label>
      <button type="button" className="quiet-button" onClick={fit} disabled={!filtered.length}>Fit view</button>
      <details className="action-menu"><summary aria-label="Map actions" title="Map actions">⋯</summary><div className="action-popover"><button type="button" onClick={() => fileInput.current?.click()}>Open offline map</button><button type="button" onClick={() => setRevision(value => value + 1)}>Refresh locations</button></div></details>
      <input ref={fileInput} type="file" accept=".pmtiles" hidden aria-label="Offline map package" onChange={event => { const file = event.target.files?.[0]; if (file) void openMap(file); }} />
    </div></header>
    <div className="location-filters"><label>Device<select value={device} onChange={event => setDevice(event.target.value)}><option value="">All sources/devices</option>{devices.map(([id, label], index) => <option key={id} value={id}>{label} · source {index + 1}</option>)}</select></label><label>From (UTC)<input type="date" value={from} onChange={event => setFrom(event.target.value)} /></label><label>Through (UTC)<input type="date" value={through} min={from} onChange={event => setThrough(event.target.value)} /></label><label className="inline-check"><input type="checkbox" checked={areas} onChange={event => setAreas(event.target.checked)} /> Approximate areas</label><label className="inline-check"><input type="checkbox" checked={tracks} onChange={event => setTracks(event.target.checked)} disabled={records.length !== total} /> Recorded paths</label></div>
    {loading && <p role="status">Loading locations…</p>}{error && <p role="alert">{error}</p>}{mapError && <p role="alert">{mapError}</p>}{records.length < total && <p role="status">Showing {records.length} of {total} records. Paths are disabled for this partial view.</p>}
    <div className="map-layout"><div className="map-stage" aria-busy={mapLoading}><div ref={container} className="location-map" aria-label="Evidence location map" />{mapLoading && <span className="sr-only" role="status">Loading map…</span>}<div className="map-caption"><span>{mapLabel}</span><span><i className="gps-dot" /> Reported GPS <i className="approx-dot" /> Approximate / mentioned</span></div></div>
      {selected && <aside className="location-inspector panel"><div className="section-heading"><h3>{selected.label}</h3><button type="button" className="icon-button" aria-label="Close location" onClick={() => setSelectedId('')}>×</button></div><span className="kind-badge">{selected.basis === 'gps' ? 'Reported GPS · accuracy unknown' : 'Approximate area · place mentioned'}</span><p>{selected.observed_at_utc ? new Date(selected.observed_at_utc).toLocaleString('en-GB', { timeZone: 'UTC' }) + ' UTC' : 'Time unknown'}</p>{selected.geometry.type === 'Point' && <p>{Number(selected.geometry.coordinates[1]).toFixed(5)}, {Number(selected.geometry.coordinates[0]).toFixed(5)}{selected.basis !== 'gps' ? ' · representative center' : ''}</p>}{selected.basis !== 'gps' && <p className="scope-note">The source mentions this place. This does not establish a device or person's position.</p>}
        <div className="location-source-actions"><button type="button" className="button-primary" onClick={() => inspectEvidence(selected.evidence_id, { observation_id: selected.observation_id, processing_run_id: selected.processing_run_id, source_locator: selected.source_locator })}>Open source</button>
          {selectedStreetView && (basemap !== 'offline' ? <a className="location-street-view" href={selectedStreetView} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" title="Opens Google Street View for these coordinates. Coverage and imagery dates vary.">Street View ↗</a> : <button type="button" disabled title="Choose Street map or Satellite to use online Street View">Street View ↗</button>)}
        </div>
      </aside>}
    </div>
    {dated.length > 0 && <div className="location-playback"><button type="button" onClick={() => { if (cursor >= dated.length - 1) setCursor(0); setPlaying(value => !value); }}>{playing ? 'Pause' : 'Play'}</button><label className="sr-only" htmlFor="location-time">Recorded position</label><input id="location-time" type="range" min="0" max={dated.length - 1} value={Math.min(cursor, dated.length - 1)} onChange={event => { const index = Number(event.target.value); setCursor(index); setPlaying(false); setSelectedId(dated[index]!.id); }} /><output>{new Date(dated[Math.min(cursor, dated.length - 1)]!.observed_at_utc!).toISOString().replace('T', ' ').slice(0, 19)} UTC</output></div>}
    {!loading && !filtered.length && <p className="empty-state">No supported locations in this selection.</p>}
    <div className="location-records-scroll"><table className="location-records"><caption className="sr-only">Location records</caption><thead><tr><th>Location / device</th><th>Basis</th><th>Time (UTC)</th></tr></thead><tbody>{filtered.slice(page * 50, (page + 1) * 50).map(row => <tr key={row.id} className={row.id === selectedId ? 'selected-row' : ''}><td><button type="button" className="text-action" aria-pressed={row.id === selectedId} onClick={() => { setSelectedId(row.id); setPlaying(false); }}>{row.label}</button></td><td>{row.basis === 'gps' ? 'Reported GPS' : 'Place mentioned · approximate'}</td><td>{row.observed_at_utc?.replace('T', ' ').replace(/Z$/, '') || 'Unknown'}</td></tr>)}</tbody></table></div>
    <div className="location-pagination"><span>{filtered.length} records</span>{filtered.length > 50 && <><button type="button" disabled={page === 0} onClick={() => setPage(value => value - 1)}>Previous</button><button type="button" disabled={(page + 1) * 50 >= filtered.length} onClick={() => setPage(value => value + 1)}>Next</button></>}</div>
  </section>;
}
