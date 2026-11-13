# GPS map workspace plan

Status: initial map workspace implemented after the latest “start working” (13 November 2026). The sections below retain the broader design proposal.

Delivered: authorized `/locations` projection from matching validated GPS rows; revision-checked pages; a lazy-loaded MapLibre workspace; bundled Natural Earth country boundaries; clusters, device/date filters, source citations, playback and optional paths. Paths split at source/run/device changes, equal/negative timestamps, gaps over one hour and date-line crossings. The client loads at most 20,000 records, identifies partial views, and disables paths when incomplete.

Approximate places use exact normalized matches against bundled countries and 243 major populated places. City points are representative centers; country mentions use areas. They identify places mentioned in text, with no person/device-position claim or invented accuracy. Unmatched names remain unmapped; an ambiguous alias can produce multiple source-linked place candidates.

Offline PMTiles packages open from a local file for the current session. Common water/land/building/road/boundary vector layers and supported raster formats render locally; package styles, glyphs and label layers are not imported. Archive attribution is displayed as safe text. Following the request to replace the blank overview with streets, the default basemap is now online OpenStreetMap. The selector also offers online Esri World Imagery satellite tiles and an Offline map. Offline mode removes online layers, uses local data only, and is remembered in this browser. Map networking is independent of the Local models only setting; choosing online maps does not change model providers or upload source files. A selected reported GPS point offers Google Street View in a new tab; approximate place centers do not offer that action. Only the coordinates are included in the external link, and no referring case URL is sent. Panoramas depend on provider coverage and their imagery dates may differ from evidence times. No tiles are prefetched or exported for offline use.

Still planned: persistent map installation in Settings, richer local labels/styles, indexed spatial/time queries and server-side geographic filtering. Current pagination bounds responses but recomputes the validated projection; it is not an indexed large-case spatial engine.

## Existing data and missing work

The GPS parser already accepts `timestamp,device_id,latitude,longitude` CSV rows. Processing preserves source-located observations for each device/latitude/longitude field and projects `gps.location` events with raw timestamps, normalized UTC when available, and links to the original evidence/observations.

The application has no dedicated geographic map. Event coordinates currently appear in a human-readable summary, while the underlying coordinate fields are separate observations. Build a typed geographic projection from matching source rows; do not extract map coordinates by parsing the event summary. The current input does not supply GPS accuracy, speed, heading, altitude or an explicit coordinate datum, so these cannot be presented as source measurements.

## User experience

Add **Locations** to the case navigation as a real workspace. Display a large map, a compact device/date filter bar, and a time scrubber. Keep point information in a panel that opens on selection; avoid a permanent column of instructions or action buttons.

First delivery:

- Zoom/pan, fit-to-data, markers and clustered points for dense records. Selecting a cluster expands it; selecting a point opens its time, source-reported device, coordinates and original-row action.
- Separate colors/labels per device and source. Do not merge device records from different files solely because their labels match.
- A linked records table: select a row to locate the point, or a point to select the row. It remains usable without WebGL or basemap availability.
- Device, evidence-source and date/time filters shared by map, table and timeline. Show filtered scope consistently and keep unknown-time points separate.
- An optional path connecting chronological observations for one source/device, with start/end markers and gaps shown explicitly. It represents connections between recorded positions, not a measured road route or continuous travel history.
- Playback moves through recorded points and times. Do not invent intermediate positions across missing intervals.
- Open the exact source row through the existing verified-original workflow. Returning to the map preserves viewport, filters and selection.

Keep the toolbar small: filters, fit view, playback and one overflow menu. Export and advanced layers belong in that menu. The selected-point panel uses the planned Results / Original / Info pattern and hides internal IDs under Technical.

## Map engine and offline basemap

Recommended candidate: [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/examples/create-and-style-clusters/), which supports GeoJSON point clustering and interactive layers. Load it only when the geographic workspace opens.

For EVORA's offline workflow, use an installed regional [PMTiles basemap](https://docs.protomaps.com/pmtiles/maplibre) served from loopback. [PMTiles supports local HTTP serving with range requests](https://docs.protomaps.com/pmtiles/). Bundle or install the matching styles, fonts/glyphs, sprites and attribution locally as well. Verify range responses, cache handling, archive bounds/zoom levels, and map rendering without any external requests. A map library alone does not provide offline map data.

Install regional map packages deliberately through Settings, recording their coverage, size, version and attribution. Avoid bundling an unnecessarily large world dataset. Outside an installed region, keep evidence points and the coordinate table usable and explain the missing basemap briefly.

Online tiles are an optional configured mode; show that the basemap requires external requests. No automatic remote geocoding of evidence points. OpenStreetMap's public standard tile service does not permit offline prefetching; use appropriately supplied regional archives or a provider that permits the intended use. See the [official tile policy](https://operations.osmfoundation.org/policies/tiles/).

## Backend projection and correctness

Propose a case-authorized endpoint such as `GET /api/v1/cases/{caseId}/locations`, returning typed geographic points or GeoJSON, with device/source/time/bounding-box filters. Each point carries original evidence, processing-run and observation references, source row, reported device label, validated coordinates, raw time, normalized UTC where known, and quality flags.

Pair latitude/longitude/device observations by the same evidence ID, processing-run ID and physical CSV row. Reject incomplete, conflicting or mixed-run tuples. Confirm the input coordinate reference system before claiming WGS84 plotting; preserve originals when conversion is needed. GeoJSON coordinates use longitude, latitude order. Valid zero coordinates must not be discarded simply because they are zero.

Keep the map's data scope explicit: current completed GPS processing is available without running case analysis. A later snapshot/report view must use pinned historical outputs consistently. Reprocessing must not move old report points silently to newer outputs.

Validate geographic/time bounds on the server. Sort with a stable timestamp/source ordering; separate equal-time conflicts, missing UTC/timezone information, and gaps. Split paths at large gaps and handle the antimeridian correctly. Treat device labels and positions as source reports, without assigning a person or vehicle identity automatically.

Use indexed spatial/time queries and bounded responses for large cases. Return total/returned counts and completeness. Never present a page of points as the complete track. Keep an overview display simplified for performance while exact original points remain available on selection/zoom/export. Downsampling must preserve path breaks and not change calculations.

Retain case access controls for all point queries and derived artifacts. Clear geographic state/caches on logout or case changes. GPS source records must not be embedded in public basemap archives or written into public diagnostic logs.

## Approximate locations supported by evidence

The user also requests approximate location when evidence supports it. Include this in the Locations design, with a clear distinction between reported GPS positions and inferred/coarse areas.

- Supported inputs may include source-provided coarse coordinates, image location metadata, an address/landmark tied to an event in a document/message, or suitable cell-site/IP location metadata. Additional extractors/reference datasets are future work; the existing GPS CSV parser does not provide all these capabilities.
- Show a short label such as `Approximate area: Bengaluru`, the supporting source/passage or metadata field, and its relevant time. Keep reported coordinates, extracted place names and derived geographic interpretations separate.
- A place mentioned in text does not automatically locate its author, device or every event in the file. Record which claim/event the passage actually supports. Registration-region codes and language alone must not establish a vehicle's current location.
- Match display precision to the supporting evidence: area boundary/shading for a city or district; a representative marker explicitly labeled as such when a boundary is unavailable. Do not present a place centroid as a measured GPS point or an exact building address.
- Show a numeric uncertainty radius only when supplied by the source or justified by a documented method. Coordinate decimal precision, model scores and repeated mentions do not establish physical accuracy. Use `Accuracy unknown` where appropriate.
- Treat IP/cell-site mappings as coarse, source-dependent candidates. Retain reference-dataset version/date and account for VPNs, carrier gateways, network routing and historical mapping differences. Do not infer an exact device/person position from an IP lookup.
- Link every approximate feature to its evidence and method. Allow review, correction and rejection while preserving the original extraction. Conflicting areas remain visible as alternatives; do not average them into an invented position.
- Keep unsupported location unknown. Local geocoding resolves a supported place reference to map geometry; it does not independently prove the underlying location claim. Follow the same explicit online/offline boundary as basemap requests.

## Later analytical features

- Observed stop/stationary intervals, with configurable distance/time thresholds and visible gaps/uncertainty.
- Segment distance and derived speed, with explicit derivation and adequate timestamps; no source-accuracy radius when the input lacks accuracy.
- Compare device tracks and candidate proximity within selected time/distance windows. Present this as an investigative comparison.
- Geofence entry/exit and dwell candidates, with source-linked supporting points and uncertainty around sampling gaps.
- Heatmaps labeled as recorded sample density, with awareness of differing device sampling rates.
- Export selected source-linked records/GeoJSON and an attributed map image for a report. GPX/KML ingestion/export needs separate format work.
- Correlate other evidence only where reliable geographic/time references exist. Relative video offsets require an explicit capture-time alignment before comparison with GPS UTC.

## Delivery order and acceptance

1. Typed source-row geographic projection and linked records table.
2. Real map, point inspection, filters and installed offline basemap.
3. Recorded-position paths and timeline playback.
4. Stops, comparison, geofences and exports after validating basic map behavior.

Validate with real processed GPS fixtures, multiple devices/sources, multi-page data, coordinate-order mistakes, valid zeros, date-line crossings, timezone changes, undated rows, duplicate/conflicting points, track gaps and unavailable map packages. Test permissions/session teardown, offline networking, keyboard/table fallback, mobile selection panels, and large-case rendering. The first map delivery is not complete with a decorative image, external-map link, or placeholder coordinates.
