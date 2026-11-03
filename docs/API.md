# Backend API

The browser and native iPhone client share this API. Use the asynchronous job endpoints for interactive clients. A configured shared beta password protects every endpoint except health. See [startup](STARTUP.md) for authentication setup.

- `GET /api/health`: readiness after startup.
- `GET /api/info?region_id=...`: selected dataset, terrain metadata, cached catalog. Omit ID for the default region.
- `POST /api/route-jobs`: `{mode, region_id, lat, lon, miles, traffic, stops, hills, strict, avoid_major, tolerance, max_ascent}`; returns 202 and a job ID. Miles 5–75; traffic/stops 0–1; hills `neutral`, `avoid`, `seek`; tolerance 3–30%; `max_ascent` null or 0–30000 feet.
- `GET /api/route-jobs/{id}`: queued/running/complete/failed/cancelled; completed jobs include a result ID and cache-hit flag.
- `DELETE /api/route-jobs/{id}`: cooperative cancellation. Active jobs do not survive a server restart.
- `GET /api/results/{id}`: stored route result. `/?ride={id}&route=0` opens it in the UI.
- `POST /api/routes`: compatible synchronous endpoint with the same preferences; uses the bounded worker pool.
- `GET /api/gpx/{result_id}/{route_index}`: download GPX. Results survive restarts with persistent storage, up to 30 days and the newest 500 searches. They are unlisted, not account-private; anyone with the link and any configured shared beta credentials can view them. There is no public listing endpoint.
- `POST /api/regions/load`: `{lat, lon, miles, label}`; returns 202 and a job ID. Imports can be disabled for hosting; cached region selection remains available.
- `GET /api/regions/jobs/{id}`: import progress. Import jobs do not survive a restart.

Coordinates use `[latitude, longitude]`, not GeoJSON ordering. All provider fetches are server-side. A failed download does not change the active graph. Terrain cache persists on disk; it is not the OSM basemap tile cache.

For real roads set `mode` to `osm` (the normal default); `synthetic` is an explicitly invented fixture. Use `region_id` from the catalog, not a display label. `tolerance` is a percentage number, e.g. `10`, not `0.1`. `strict` and `avoid_major` are booleans.

Route coordinates are `[latitude, longitude]`. Navigation cues contain `distance_m`, `coordinate_index` and `instruction`. Elevation arrays pair distance in miles with height in metres; raw elevation heights may be null when unavailable. Inspect `ios/Sources/PedalCore/Models.swift` and its contract tests before changing response formats.
