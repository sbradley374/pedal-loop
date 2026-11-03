# Routing and terrain reference

## Plan in the browser

These controls describe the browser development runner. The hosted runner disables imports by default; use the CLI below to prepare regions for it.

1. Choose a preset, enter latitude/longitude, or click the map. Presets and **Use my location** select a matching cached region when one is available, preserving your chosen point. Providence, Boston, Burlington and London are convenient starting presets; **a preset does not mean its roads have already been downloaded**.
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

The [archived example GPX files](../archive/examples/README.md) were generated with the prior search/profile version. New candidates and totals can differ. Treat climbing as a model output, not a calibrated measurement.

## Road/routing assumptions

- OSM ways retain their shape points and directed one-way topology, including mapped `oneway:bicycle` overrides. Known unsuitable surfaces, some barriers, access restrictions, and conditional-access ways are conservatively excluded.
- Traffic is a **road-class proxy**, not measured traffic. Stop/signal tags are incomplete, and a mapped junction does not necessarily require stopping.
- Unknown pavement is allowed by default and disclosed as a percentage. Strict pavement mode allows only explicitly tagged paved surfaces and may disconnect the network.
- **New imports include supported turn-restriction relations.** Node-via restrictions between distinct ways are modeled, including bicycle exceptions. Via-way, conditional, and same-way/U-turn restrictions are not modeled. The bundled snapshots do not contain relations and show a warning until refreshed. Complex access rules, temporary closures, direction-sensitive restrictions and all barrier cases are not fully handled. Check current signs, access, surface and conditions. This is not a safety guarantee or turn-by-turn navigation engine.
- The start snaps to an eligible road within 1.5 km. Connecting travel from your requested point is not included, and the snapped distance is displayed.
- A* uses positive costs for distance, traffic proxies, stops/junctions, surface uncertainty, and known grades. Lossless chain compression preserves original edge costs; directed, preference-weighted landmark lower bounds accelerate search. Up to 40 anchor trials (three initial scales and up to two refinements in each of eight directions) penalize repeated segments. Up to three alternatives are retained, with at most 20% repeated length, target error within the requested tolerance, and no more than 75% overlap of the shorter route between alternatives. This is a heuristic, not a globally optimal loop solver.
- Search indexes are cached per region, with two preference configurations retained. The service has two search workers and four waiting slots; excess submissions return 429. Threads keep requests responsive, but do not provide CPU scaling under Python’s GIL. One region import runs at a time. Large dense regions use substantial memory. See [historical benchmark reports](../archive/README.md) for measured times.

## Import regional data

Use the same region-and-terrain pipeline as the UI:

```sh
python scripts/prepare_region.py --lat 44.4759 --lon -73.2121 --miles 10 --label "Burlington, Vermont"
```

The development machine also has a locally imported 9 km Boulder region, with four passing software benchmark scenarios in [the historical Boulder report](../archive/reports/benchmark-boulder-2026-10-20.json). It is Git-ignored and is not included in fresh clones or guaranteed in hosted deployments. To prepare it elsewhere, run `python scripts/prepare_regions.py --only boulder --download`.

Restart the app to discover a region prepared by a separate CLI process. In-app imports require no restart. On startup the default region is Providence; other regions remain in the cache selector. Each request identifies its own region; switching in one browser does not switch another browser’s roads.

For explicit road-only imports, the original importer remains available:

```sh
python scripts/fetch_osm.py --lat 42.355 --lon -71.0656 --radius 15000 --output data/boston.osm.json.gz
python scripts/enrich_elevation.py --data data/boston.osm.json.gz
python app.py --data data/boston.osm.json.gz
```

The fetch script reuses existing files unless `--refresh` is supplied. It does not automatically retry. If a Python certificate bundle is missing on macOS, install your Python distribution's certificates or use its configured system CA bundle; never disable certificate verification. The new shared downloader uses `/etc/ssl/cert.pem` if Python has no loaded CA certificates.
