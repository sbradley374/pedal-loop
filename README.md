# Pedal Loop · roads + terrain

A local road-cycling loop planner with real OpenStreetMap roads, terrain elevation, GPX exports, and cached regional imports. Brown University is the default start; targets now span **5–75 miles**.

## Run

The bundled Providence and Burlington road/elevation snapshots need only Python 3.9+:

```sh
python3 app.py
```

Open **http://127.0.0.1:8000**. To enable downloads of terrain for new regions, use the included dependency file (Pillow decodes terrain PNGs):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

On Windows activate with `.venv\Scripts\activate`. The app binds only to your computer. Use `--port 8001` if necessary; stop with Ctrl+C. `python3 app.py --demo` forces the clearly labeled invented fixture, disables regional downloads, and does not use internet tiles.

## Plan a ride anywhere the data supports

1. Choose a preset, enter latitude/longitude, or click the map. Providence, Boston, Burlington and London are convenient starting presets; **a preset does not mean its roads have already been downloaded**.
2. Set the desired distance (5–75 miles), traffic/stop preferences, and hill preference.
3. For a new place, click **Load roads + terrain here**. Progress appears under the button. The regional radius is estimated from the chosen distance, capped at 30 km for this local prototype. The download may take several minutes or fail if the public provider is busy.
4. Click **Find my loop**. Choose an alternative, compare climbing estimates, inspect the profile, and download GPX. Move over the profile for distance/elevation readings.
5. Use **Cached road regions** to switch locations without repeating downloads. The start moves to the cached region's center; choose the distance you want and generate again.

The existing region remains available until a new one is successfully built. If terrain fails, the road region still loads with an explicit warning and unknown elevation. If roads fail, the prior region remains active. There is no silent substitution of synthetic routes.

**Coverage matters:** a long ride or start near the boundary may have few alternatives or no good match. The UI reports that limitation. Loading around the selected start and distance can improve coverage, but the 30 km import cap is deliberate; 75 miles is an allowed target, not a guarantee that every region supports it. Poles and dateline-crossing regions are not validated. Latitude is limited to ±85°.

## Elevation: what the numbers mean

The app samples **Mapzen Terrain Tiles from AWS Open Data**, using cached zoom-12 Terrarium tiles. The Providence grid spacing is approximately **28.5 m**; spacing varies with latitude, and underlying source resolution and accuracy vary independently.

- Each road node gets a bilinearly interpolated **terrain-height estimate**. Tile-boundary interpolation uses adjacent tiles, rather than clamping pixels at seams.
- Climbing/descent totals use a profile resampled every 30 m, a three-sample (~90 m) moving mean, and a 3 m reversal threshold to suppress raster noise. Smoothed profiles require complete route elevation coverage; missing samples are not filled across gaps.
- Approximate steepest grade is measured over 150 m, not adjacent OSM shape points. It is not an instantaneous maximum grade or a surveyed road measurement.
- **Prefer flatter roads** increases the cost of steeper segments. **Prefer hills** biases toward sloped segments. These are heuristic preferences, not guarantees of a climb budget or the lowest/highest possible total ascent.
- GPX contains the available raw terrain samples at source road points; another app's climb calculation may differ because it smooths differently. The UI uses the smoothed profile and gain method described above.
- Source, retrieval timestamp, grid spacing and method are stored with the elevation sidecar. A SHA-256 fingerprint binds each sidecar to its exact road snapshot, so refreshing roads cannot silently attach stale samples.

**Bridges, tunnels, cliffs and causeways can differ sharply from the underlying ground.** These effects and source errors can create false hills or grades. Terrain interpolation is useful for planning, not equivalent to surveyed road elevation. GPX includes terrain-source attribution. No real-route elevation is invented when unavailable.

The initial default 29.8-mile Brown candidate estimated ~1,024 ft of climbing with this method. Treat this as a reproducible model output, not a calibrated measurement.

## Road/routing assumptions

- OSM ways retain their shape points and directed one-way topology, including mapped `oneway:bicycle` overrides. Known unsuitable surfaces, some barriers, access restrictions, and conditional-access ways are conservatively excluded.
- Traffic is a **road-class proxy**, not measured traffic. Stop/signal tags are incomplete, and a mapped junction does not necessarily require stopping.
- Unknown pavement is allowed by default and disclosed as a percentage. Strict pavement mode allows only explicitly tagged paved surfaces and may disconnect the network.
- **Turn-restriction relations are not implemented.** Complex access rules, temporary closures, direction-sensitive restrictions and all barrier cases are not fully handled. Check current signs, access, surface and conditions. This is not a safety guarantee or turn-by-turn navigation engine.
- The start snaps to an eligible road within 1.5 km. Connecting travel from your requested point is not included, and the snapped distance is displayed.
- A* uses positive costs for distance, traffic proxies, stops/junctions, surface uncertainty, and known grades. A bounded search over 24 anchor triangles penalizes repeated segments, then ranks distance error and ride cost. Up to three alternatives are retained, with at most 20% repeated length, at most 30% target error, and less than 75% overlap of the shorter route between alternatives. This is a heuristic, not a globally optimal loop solver.
- Providence searches typically take ~20–40 seconds on the development laptop. Smaller regions can be much faster. There is one route computation and one import job at a time; imports run in the background. Large dense regions use substantial memory.

## CLI imports

Use the same region-and-terrain pipeline as the UI:

```sh
python scripts/prepare_region.py --lat 44.4759 --lon -73.2121 --miles 10 --label "Burlington, Vermont"
```

Restart the app to discover a region prepared by a separate CLI process. In-app imports require no restart. On startup the default active region is Providence; other regions remain in the cache selector.

For explicit road-only imports, the original importer remains available:

```sh
python scripts/fetch_osm.py --lat 42.355 --lon -71.0656 --radius 15000 --output data/boston.osm.json.gz
python scripts/enrich_elevation.py --data data/boston.osm.json.gz
python app.py --data data/boston.osm.json.gz
```

The fetch script reuses existing files unless `--refresh` is supplied. It does not automatically retry. If a Python certificate bundle is missing on macOS, install your Python distribution's certificates or use its configured system CA bundle; never disable certificate verification. The new shared downloader uses `/etc/ssl/cert.pem` if Python has no loaded CA certificates.

## Source layout and API

```text
app.py                       Local HTTP API, static UI, result cache
planner/graph.py             Directed OSM graph, filters, nearest-node index
planner/routing.py           Validation, weighted A*, loop search, metrics
planner/elevation.py         Tile cache, interpolation, sidecars, climb/profile math
planner/regions.py           Region catalog, imports, job status, atomic switching
planner/network.py           Identified HTTPS downloads and byte limits
planner/export.py            GPX 1.1 track serialization and source attribution
web/                        Responsive interface and local Leaflet assets
scripts/                    Data import, terrain enrichment, real-data checks
tests/                      Offline algorithm, data, job, export and HTTP tests
data/                       Road snapshots, elevation sidecars, region manifests
```

- `GET /api/info`: active dataset, terrain metadata, cached region catalog.
- `POST /api/routes`: `{mode, lat, lon, miles, traffic, stops, hills, strict}`. Miles 5–75; traffic/stops 0–1; hills `neutral`, `avoid`, `seek`.
- `GET /api/gpx/{result_id}/{route_index}`: download one result. Last 20 searches retained in memory; links expire on restart.
- `POST /api/regions/load`: `{lat, lon, miles, label}` for a new region, or `{region_id}` to switch a cached region. Returns 202 and a job ID.
- `GET /api/regions/jobs/{id}`: `running`, `complete`, or `failed`, plus progress and warnings.

Coordinates use `[latitude, longitude]`, not GeoJSON ordering. All provider fetches are server-side. A failed download does not change the active graph. Terrain cache persists on disk; it is not the OSM basemap tile cache.

## Test

```sh
python -m unittest discover -s tests -v
node --check web/app.js  # optional, if Node is installed
python scripts/verify_snapshot.py  # optional slower real-data checks
```

Tests cover routing and preference costs, directed/access/surface filtering, loop closure and distance accounting, GPX validity, missing elevations, terrain interpolation across tile seams, noisy climb suppression, stale-sidecar rejection, distance bounds, cached region switching, failed-import recovery, and HTTP behavior. The original real-data smoke script checks Providence at 20/30/50 miles; new manual integration checks also exercise Burlington at 5/10 miles and contrasting hill preferences.

## Data, terms and privacy

OSM road data: **© OpenStreetMap contributors**, [ODbL](https://www.openstreetmap.org/copyright). See `data/README.md` for source provenance. Preserve attribution and applicable share-alike obligations when redistributing road data or derived databases. Application code is MIT licensed; Leaflet has its own retained license.

Terrain: **Mapzen and source contributors**, [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) and [source-specific attribution/terms](https://github.com/tilezen/joerd/blob/master/docs/attribution.md). A local copy of attribution is in `data/TERRAIN-ATTRIBUTION.md`. Raw terrain files and derived elevations retain their source terms. Terrain Tiles was accessed on October 20, 2026. Data can be old despite a recent retrieval date.

Road/elevation calculations stay local. Explicit downloads transmit the selected region to Overpass and terrain-tile requests to AWS. Interactive OSM basemap requests disclose viewport/IP to the tile provider. Basemap tiles use normal browser caching and visible attribution, with no offline tile downloader or prefetch. `TILE_URL` changes the basemap provider; update required attribution for any replacement. Read the [tile policy](https://operations.osmfoundation.org/policies/tiles/) before scaling usage. No public Nominatim address lookup is integrated.

New-region data services are best effort. Downloads are cached and bounded; no background refresh or automatic retries. This is still a local prototype, not a public service. Production work should add provider contracts/quotas, cancellation, turn restrictions, compact graphs, and stronger route audits.
