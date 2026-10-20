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
