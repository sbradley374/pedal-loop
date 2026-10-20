# Pedal Loop · roads + terrain · v0.3 beta

A local road-cycling loop planner with real OpenStreetMap roads, terrain elevation, GPX exports, and cached regional imports. Brown University is the default start; targets now span **5–75 miles**.

## What changed in v0.3

- Lossless directed road-chain compression and preference-weighted landmark A* reduce repeated searches over shape points. Full road geometry and distance are retained.
- Adaptive distance refinement with a hard, user-selected tolerance (default ±10%, UI choices 5/10/20/30%). No silent relaxation.
- Strict exclusion of primary/secondary roads, visible major-road percentages, and an optional estimated climbing limit. With a neutral hill preference, a climbing limit also steers the candidate search toward flatter roads.
- Supported node-via turn restrictions in new regional imports, including bicycle exceptions and restrictions across loop legs. Complex/via-way/conditional/same-way restrictions remain explicitly unsupported. Bundled snapshots predate restriction imports.
- Background route jobs, cancellation, bounded queues, reusable results, and per-request region selection.
- Persistent GPX/result links, saved rides on this browser, copyable unlisted links, location selection, and an approximate coverage circle.
- A production WSGI entrypoint, Docker packaging, CI, and regional benchmark tooling. See [deployment guidance](docs/DEPLOYMENT.md) and [development status](docs/ROADMAP.md).

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
5. Use **Cached road regions** to switch locations without repeating downloads or changing another visitor’s region. The start moves to the cached region's center; choose the distance you want and generate again. Searches start only when you click **Find my loop**, not on page load.

The existing region remains available until a new one is successfully built. Choose a distance tolerance, optionally exclude major roads or set a climbing limit, and cancel a search without waiting for it to finish. If terrain fails, the road region still loads with an explicit warning and unknown elevation. If roads fail, the prior region remains active. There is no silent substitution of synthetic routes.

**Coverage matters:** a long ride or start near the boundary may have few alternatives or no good match. The UI reports that limitation. Loading around the selected start and distance can improve coverage, but the 30 km import cap is deliberate; 75 miles is an allowed target, not a guarantee that every region supports it. Poles and dateline-crossing regions are not validated. Latitude is limited to ±85°.

## Elevation: what the numbers mean

The app samples **Mapzen Terrain Tiles from AWS Open Data**, using cached zoom-12 Terrarium tiles. The Providence grid spacing is approximately **28.5 m**; spacing varies with latitude, and underlying source resolution and accuracy vary independently.

- Each road node gets a bilinearly interpolated **terrain-height estimate**. Tile-boundary interpolation uses adjacent tiles, rather than clamping pixels at seams.
- Climbing/descent totals use a profile resampled every 30 m, a three-sample (~90 m) moving mean, and a 3 m reversal threshold to suppress raster noise. Smoothed profiles require complete route elevation coverage; missing samples are not filled across gaps.
- Closed-loop profiles smooth across the start/end seam and count climbing from the lowest smoothed point, avoiding artificial start-dependent gain/loss. A climbing limit applies to this estimate and rejects incomplete terrain coverage.
- Approximate steepest grade is measured over 150 m, not adjacent OSM shape points. It is not an instantaneous maximum grade or a surveyed road measurement.
- **Prefer flatter roads** increases the cost of steeper segments. **Prefer hills** biases toward sloped segments. These are heuristic preferences, not guarantees of a climb budget or the lowest/highest possible total ascent.
- GPX contains the available raw terrain samples at source road points; another app's climb calculation may differ because it smooths differently. The UI uses the smoothed profile and gain method described above.
- Source, retrieval timestamp, grid spacing and method are stored with the elevation sidecar. A SHA-256 fingerprint binds each sidecar to its exact road snapshot, so refreshing roads cannot silently attach stale samples.

**Bridges, tunnels, cliffs and causeways can differ sharply from the underlying ground.** These effects and source errors can create false hills or grades. Terrain interpolation is useful for planning, not equivalent to surveyed road elevation. GPX includes terrain-source attribution. No real-route elevation is invented when unavailable.

The checked-in example GPX files were generated with the prior search/profile version. New candidates and totals can differ. Treat climbing as a model output, not a calibrated measurement.

## Road/routing assumptions

- OSM ways retain their shape points and directed one-way topology, including mapped `oneway:bicycle` overrides. Known unsuitable surfaces, some barriers, access restrictions, and conditional-access ways are conservatively excluded.
- Traffic is a **road-class proxy**, not measured traffic. Stop/signal tags are incomplete, and a mapped junction does not necessarily require stopping.
- Unknown pavement is allowed by default and disclosed as a percentage. Strict pavement mode allows only explicitly tagged paved surfaces and may disconnect the network.
- **New imports include supported turn-restriction relations.** Node-via restrictions between distinct ways are modeled, including bicycle exceptions. Via-way, conditional, and same-way/U-turn restrictions are not modeled. The bundled snapshots do not contain relations and show a warning until refreshed. Complex access rules, temporary closures, direction-sensitive restrictions and all barrier cases are not fully handled. Check current signs, access, surface and conditions. This is not a safety guarantee or turn-by-turn navigation engine.
- The start snaps to an eligible road within 1.5 km. Connecting travel from your requested point is not included, and the snapped distance is displayed.
- A* uses positive costs for distance, traffic proxies, stops/junctions, surface uncertainty, and known grades. Lossless chain compression preserves original edge costs; directed, preference-weighted landmark lower bounds accelerate search. Up to 40 anchor trials (three initial scales and up to two refinements in each of eight directions) penalize repeated segments. Up to three alternatives are retained, with at most 20% repeated length, target error within the requested tolerance, and no more than 75% overlap of the shorter route between alternatives. This is a heuristic, not a globally optimal loop solver.
- Search indexes are cached per region, with two preference configurations retained. The service has two search workers and four waiting slots; excess submissions return 429. Threads keep requests responsive, but do not provide CPU scaling under Python’s GIL. One region import runs at a time. Large dense regions use substantial memory. See the checked-in benchmark report for measured times.

## CLI imports

Use the same region-and-terrain pipeline as the UI:

```sh
python scripts/prepare_region.py --lat 44.4759 --lon -73.2121 --miles 10 --label "Burlington, Vermont"
```

Restart the app to discover a region prepared by a separate CLI process. In-app imports require no restart. On startup the default region is Providence; other regions remain in the cache selector. Each request identifies its own region; switching in one browser does not switch another browser’s roads.

For explicit road-only imports, the original importer remains available:

```sh
python scripts/fetch_osm.py --lat 42.355 --lon -71.0656 --radius 15000 --output data/boston.osm.json.gz
python scripts/enrich_elevation.py --data data/boston.osm.json.gz
python app.py --data data/boston.osm.json.gz
```

The fetch script reuses existing files unless `--refresh` is supplied. It does not automatically retry. If a Python certificate bundle is missing on macOS, install your Python distribution's certificates or use its configured system CA bundle; never disable certificate verification. The new shared downloader uses `/etc/ssl/cert.pem` if Python has no loaded CA certificates.

## Source layout and API

```text
app.py                       WSGI HTTP API, local runner, static UI
serve.py                     Waitress hosted runner
planner/service.py           Bounded jobs, cancellation, SQLite result storage
planner/compact.py           Directed chain compression and landmark indexes
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

- `GET /api/health`: readiness after startup.
- `GET /api/info?region_id=...`: selected dataset, terrain metadata, cached catalog. Omit ID for the default region.
- `POST /api/route-jobs`: `{mode, region_id, lat, lon, miles, traffic, stops, hills, strict, avoid_major, tolerance, max_ascent}`; returns 202 and a job ID. Miles 5–75; traffic/stops 0–1; hills `neutral`, `avoid`, `seek`; tolerance 3–30%; `max_ascent` null or 0–30000 feet.
- `GET /api/route-jobs/{id}`: queued/running/complete/failed/cancelled; completed jobs include a result ID and cache-hit flag.
- `DELETE /api/route-jobs/{id}`: cooperative cancellation. Active jobs do not survive a server restart.
- `GET /api/results/{id}`: stored route result. `/?ride={id}&route=0` opens it in the UI.
- `POST /api/routes`: compatible synchronous endpoint with the same preferences; uses the bounded worker pool.
- `GET /api/gpx/{result_id}/{route_index}`: download GPX. Results survive restarts with persistent storage, up to 30 days and the newest 500 searches. They are unlisted, not account-private; anyone with a link can view them. There is no public listing endpoint.
- `POST /api/regions/load`: `{lat, lon, miles, label}`; returns 202 and a job ID. Imports can be disabled for hosting; cached region selection remains available.
- `GET /api/regions/jobs/{id}`: import progress. Import jobs do not survive a restart.

Coordinates use `[latitude, longitude]`, not GeoJSON ordering. All provider fetches are server-side. A failed download does not change the active graph. Terrain cache persists on disk; it is not the OSM basemap tile cache.

## Test

```sh
python -m unittest discover -s tests -v
node --check web/app.js  # optional, if Node is installed
python scripts/verify_snapshot.py  # optional slower real-data checks
python scripts/benchmark.py --output benchmark-results/latest.json
```

Tests cover routing and preference costs, directed/access/surface filtering, loop closure and distance accounting, GPX validity, missing elevations, terrain interpolation across tile seams, noisy climb suppression, stale-sidecar rejection, distance bounds, cached region switching, failed-import recovery, and HTTP behavior. The original real-data smoke script checks Providence at 20/30/50 miles; new manual integration checks also exercise Burlington at 5/10 miles and contrasting hill preferences.

## Data, terms and privacy

OSM road data: **© OpenStreetMap contributors**, [ODbL](https://www.openstreetmap.org/copyright). See `data/README.md` for source provenance. Preserve attribution and applicable share-alike obligations when redistributing road data or derived databases. Application code is MIT licensed; Leaflet has its own retained license.

Terrain: **Mapzen and source contributors**, [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) and [source-specific attribution/terms](https://github.com/tilezen/joerd/blob/master/docs/attribution.md). A local copy of attribution is in `data/TERRAIN-ATTRIBUTION.md`. Raw terrain files and derived elevations retain their source terms. Terrain Tiles was accessed on October 20, 2026. Data can be old despite a recent retrieval date.

With `app.py`, road/elevation calculations stay local. A hosted deployment runs them on its server. Results include requested/snapped starts and route geometry and are stored in SQLite even before you click Save; the browser stores saved result references. Hosted use therefore sends these locations to the host. Download GPX for long-term retention. Explicit downloads transmit the selected region to Overpass and terrain-tile requests to AWS. Interactive OSM basemap requests disclose viewport/IP to the tile provider. Basemap tiles use normal browser caching and visible attribution, with no offline tile downloader or prefetch. `TILE_URL` changes the basemap provider; update required attribution for any replacement. Read the [tile policy](https://operations.osmfoundation.org/policies/tiles/) before scaling usage. No public Nominatim address lookup is integrated.

New-region data services are best effort. Downloads are cached and bounded; no background refresh or automatic retries. This is a single-instance beta foundation, not a nationwide routing guarantee. Public deployment still needs an actual hosting account, HTTPS/domain configuration, a map-provider capacity plan, route audits, and monitoring. Multi-instance scale needs a shared durable job queue, process workers, and managed regional datasets. No public deployment is included simply by pushing this repository.
