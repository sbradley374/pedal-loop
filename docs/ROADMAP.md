# Development status and next milestones

## Implemented in v0.3

- Compressed directed road search with original geometry/edge costs and reusable preference-weighted landmark indexes.
- Adaptive target-distance refinement, hard distance tolerance, major-road exclusion, estimated ascent limits.
- Node-via turn restrictions from new imports; explicit disclosure of unsupported or missing restrictions.
- Closed-loop elevation smoothing and start-independent gain counting; bridge/tunnel exposure reporting.
- Independent region selection per request, bounded region/index caches, bounded async search workers, cancellation.
- SQLite results, repeat-search reuse, GPX links that survive restarts, browser saved rides and link copying.
- Geolocation button, coverage boundary, route comparison metrics, no automatic search on page load.
- Production WSGI runner, container configuration, health endpoint, rate limits, automated tests and offline benchmark matrix.

- Foreground live-ride beta with GPS metrics, bounded route matching, and approximate mapped cues; see `NAVIGATION.md`. Native background navigation remains separate work.

## Release gates not yet satisfied

- No hosted URL or hosting account has been provisioned. Docker build/run and container-recreation checks passed in GitHub Actions run 39495796695. Local Waitress restart persistence passed.
- Safari desktop generation, alternative selection, save/copy/export and visual layout passed; the 390-pixel form preview passed. Mobile results and remaining flows still need verification (see QA report).
- No national data preload or nationwide route validation has been completed. Providence/Burlington are bundled. A deliberate Boulder retry succeeded locally with roads/terrain and four passing benchmark scenarios; the 9 km snapshot is not bundled in Git. Madison remains unimported. Local-rider review is still required.
- No traffic-volume feed, live closures, full access-rule interpreter, via-way/conditional/same-way turn restrictions, or bridge-deck elevation correction.
- No elevation calibration against surveyed roads or recorded rides. Climbing remains a terrain estimate.
- Local bounded concurrency test completed: six uncached searches took 17.5–39.7 seconds, two excess requests rejected, health checks responsive, peak RSS ~834 MiB. Hosted load, alerts, off-site backups and recovery drills remain open.

## Next recommended milestones

1. Deploy a private staging instance and run browser/mobile, persistence, and load checks.
2. Prepare and audit a small set of contrasting regions. `data/coverage-plan.json` proposes additional US regions; it is a plan, not an availability list. Use `python scripts/prepare_regions.py --only boulder madison` to inspect the plan and add `--download` to import sequentially. Failed provider requests stop the batch without automatic retry.
3. Add recorded-ride comparison fixtures for distance/climb and local rider review of selected routes. Expand the benchmark suite as actual datasets become available.
4. Replace the shared public download dependency with a managed OSM extract/update pipeline and a preprocessed routing engine or partitioned graph service. Add overlapping regional coverage and boundary stitching. National coverage requires this operational work, not just more presets.
5. Add an address-search provider, editable waypoints/avoid areas, user accounts, private route collections, and a privacy/deletion flow.
6. Add an installable mobile experience. Treat offline navigation and turn-by-turn instructions as separate projects requiring validated instructions, rerouting, and offline map licensing.

The current architecture deliberately supports a small single-instance beta. Search workers are threads, completed results are durable, active jobs are not durable, and region imports remain capped at 30 km. A shared durable queue, process workers, and storage coordination are prerequisites for multi-instance scaling.
