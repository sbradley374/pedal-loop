# Implementation decisions and source notes

Reviewed October 20, 2026. These are engineering notes, not a substitute for reviewing provider terms before deployment.

## Libraries and route data

- **OSMnx:** the current stable documentation reviewed identifies 2.1.1. It retrieves networks, preserves directed one-way topology, supports custom OSM filters/tags, persists GraphML, and offers routing/elevation helpers on NetworkX/GeoPandas. A strong next step for larger geographic processing. [Getting started](https://osmnx.readthedocs.io/en/stable/getting-started.html), [API reference](https://osmnx.readthedocs.io/en/stable/user-reference.html).
- **Chosen MVP:** a small Python standard-library graph implementation with A* and explicit Overpass ingestion. This keeps the delivered project runnable without a geospatial installation and exposes algorithm/policy choices for portfolio review. OSM ways are split at every source node, so exported geometry follows road shape. A metre-grid nearest-node index reduces repeated graph scans.
- **Leaflet 1.9.4:** selected as the stable, straightforward raster-map/vector-overlay option. Assets are vendored locally; the upstream license is retained in `web/vendor/Leaflet-LICENSE`. [Official download and releases](https://leafletjs.com/download.html).
- **Elevation:** no synthetic heights are assigned to real roads. OSM node `ele` tags are parsed when numeric; they are too sparse to support a useful real profile here. Future work should sample a properly licensed DEM at source shape nodes, validate voids and units, then smooth noisy gains.

## Service and licensing choices

- **OSM data is ODbL**, separate from application code. Attribution and relevant share-alike requirements apply when redistributing OSM or a derived database. The deliverable includes the downloaded source snapshot and provenance, and the UI/GPX link to attribution. [OSM copyright](https://www.openstreetmap.org/copyright).
- **Overpass is a shared service.** Public instance capacity is limited, requests can queue or fail, and instance policies differ. Use one cached regional extraction; do not request a new network for every route generation. This MVP has no scheduled refresh or automatic retries. The shared-instance guidance describes resource slots, timeouts and limits; repeated imports or production usage should move to an appropriate provider or your own infrastructure. [Overpass resource guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html).
- **OSM raster tiles:** use HTTPS, visible attribution, normal browser caching and valid referrer; no bulk downloads, prefetching, or offline tile bundling. Service is best effort. The tile URL is configurable. [Tile usage policy](https://operations.osmfoundation.org/policies/tiles/).
- **No public Nominatim integration:** start presets, coordinate entry and map clicks satisfy this MVP without a geocoder. The public service has an aggregate maximum of one request per second, identification/caching requirements, prohibits autocomplete, and specifically limits how generic generated search services may use it. A future address-search feature requires a deliberate provider choice and compliance with its terms. [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/).

## Priority next steps

1. Turn-restriction relation ingestion and direction-sensitive access/barrier logic; audit routes against real local cycling knowledge.
2. Elevation raster integration and credible road/traffic attributes, each with provenance and coverage.
3. Contract degree-two shape nodes while retaining geometry; benchmark candidate quality and speed against NetworkX/OSMnx baselines.
4. Adaptive anchor placement and distance refinement to reduce target error, followed by route diversity tuning.
5. A production service layer, cancellation and cached graph partitions if usage moves beyond a personal local demo.

## v0.2: terrain and regional generalization

The original elevation limitation above is now addressed with cached global Terrain Tiles, while retaining explicit source uncertainty. The [AWS registry](https://registry.opendata.aws/terrain-tiles/) describes global bare-earth terrain on a public S3 bucket; the [Terrarium specification](https://github.com/tilezen/joerd/blob/master/docs/formats.md) defines metre-valued RGB encoding. The implementation samples zoom-12 rasters bilinearly, handles neighboring tile pixels at seams, and records source metadata with snapshot-bound sidecars. Pillow is the only optional new dependency, needed for new PNG downloads.

The UI now supports explicit background regional imports, durable cached-region selection, 5–75 mile targets, and coverage warnings. Imports use a radius estimated from target distance, capped at 30 km. This begins geographical generalization; it does not claim universally reliable global routes, complete road attributes, or arbitrarily long rides. Public OSM/terrain services remain best effort.

Terrain is a proxy for road elevation: it does not encode bridge deck or tunnel geometry. Profiles and gain use spatial smoothing and a reversal threshold rather than accumulating every small change between shape nodes. The method is documented in the README, UI and sidecar metadata, and the source attribution is retained locally. Terrain source accuracy and age remain independent of the displayed raster spacing/retrieval date.

The next elevation-specific improvements should be bridge/tunnel correction, calibration against known rides or authoritative road elevations, and a user-selected ascent range rather than only hill avoidance/preference. Address search, compact graphs and turn-restriction support remain separate next steps.

## v0.3: measured speed, bounded routes, and hosted-beta foundation

The implementation now contracts directed chains without simplifying exported geometry. Shape-point endpoints are split virtually for each search. Preference-weighted landmark distances ignore turn restrictions and repeated-road penalties, so they remain lower bounds for A*. Differential tests compare compressed and uncompressed weighted paths, including internal endpoints, one-way rings and turn restrictions.

Search uses 24 initial anchor triangles and up to 16 distance-driven refinements. The requested tolerance is enforced using unrounded length. The optional ascent cap rejects unknown profiles. Primary/secondary road exclusion is an actual routing and snapping filter, not a stronger soft penalty. Traffic remains a road-class proxy; this does not estimate vehicle counts or certify quiet/safe roads.

A pure-distance landmark experiment increased runtime on the Providence benchmark and was replaced by preference-weighted indexes. See `docs/benchmark-2026-10-20.json` for the final recorded matrix. Timings depend on hardware, graph/index warmth, and other load.

New imports request restrictions; supported node-via restrictions are enforced across path segments and loop closure. Unsupported restrictions are counted and disclosed. Existing source snapshots and their original provenance remain unchanged. Ground elevation on bridges/tunnels is disclosed rather than replaced with fabricated heights. Closed profiles now smooth periodically and use valley-based gain counting.

The UI uses asynchronous search jobs. A bounded in-process thread pool supports cancellation and avoids blocking HTTP requests, while SQLite retains results. This is a single-process beta architecture: it does not promise parallel CPU speed, durable jobs, or multi-instance coordination. The next infrastructure step is a shared queue and dedicated process workers, not more web threads.

Hosted serving follows the [Waitress usage guide](https://docs.pylonsproject.org/projects/waitress/en/stable/usage.html) and [proxy configuration guidance](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html). Browser tiles remain subject to the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/); no offline tile bulk downloading is added.
