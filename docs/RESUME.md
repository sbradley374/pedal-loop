# Resume checkpoint — October 20, 2026

Resumed on October 20. Saved-ride response races are fixed and container smoke/recreation checks are added to CI. The temporary verification server on port 8001 was stopped after testing.

## Current branch

`feat/routing-speed-and-hosted-beta`. Preserve the existing intermediate `prog/speed` commits; do not reset or rewrite them. The final checkpoint adds climbing-limit search guidance, the forced-demo safeguard, and the updated benchmark result.

## Verified

- 51 Python regression tests and five frontend concurrency tests pass; JavaScript syntax and Git whitespace checks pass.
- Hosted smoke checks passed again. A saved ride and its GPX remained available after an actual Waitress process restart.
- Delayed saved-ride and dataset responses now yield to newer selections/settings/searches; obsolete errors cannot overwrite current status.
- Real Providence searches: approximately 8.9 seconds for the first 20-mile search (index construction included), 5.6 seconds for 30 miles and 7.1 seconds for 50 miles. Previous measurements were about 16/21/30 seconds.
- Real Burlington ordinary searches: approximately 0.8–1.1 seconds. Hosted HTTP smoke: 1.34 seconds for a 5-mile search and 0.11 seconds for a repeated cached request.
- Hosted HTTP checks passed for cancellation, independent region selection, stored results, and GPX export.
- A 10-mile Burlington request with a 500-foot estimated climbing ceiling now returns 10.6/9.4/10.8-mile routes with estimated ascent 479/473/484 feet. That case was rerun independently after the final refinement; its report entry records a new timestamp and cold-index timing.
- Benchmark report: `docs/benchmark-2026-10-20.json`. Ten of twelve scenarios return qualifying routes. Both strict major-road-exclusion cases report no match rather than relaxing the filter. The benchmark script intentionally exits nonzero when any scenario has no match.

## Implemented

Compressed directed routing, preference-weighted landmark A*, adaptive distance refinement, hard distance tolerance, strict major-road exclusion, climbing limits, closed-loop elevation handling, basic node-via restrictions on new imports, async search/cancel, per-request regions, SQLite result reuse/persistence, saved/shared links, coverage map, location button, production WSGI runner, Docker packaging, CI, and regional preparation/benchmark scripts.

Read `README.md`, `docs/ROADMAP.md`, and `docs/DEPLOYMENT.md` for behavior and limitations.

## Next work

1. Browser/mobile visual and interaction QA. Arc could load the app and expose its controls, but native clicks repeatedly left blank content and removed the page accessibility tree. Full interaction/visual QA remains incomplete; do not claim it passed.
2. Inspect the new `container` GitHub Actions job: it builds Compose, runs HTTP smoke checks, recreates the container, and verifies persisted ride/GPX access. Docker remains unavailable locally, and the remote job result has not yet been verified.
3. Choose/provision a staging host, persistent volume, HTTPS origin, and proxy configuration. No public site is deployed.
4. Retry a small regional import only deliberately: the Boulder/Madison batch stopped at Boulder on an Overpass 502. No new-region coverage was added. Avoid automatic retry loops.
5. Audit routes and elevation against actual rides; continue toward managed regional datasets and a shared process-worker queue before national or multi-instance claims.

## Run again

```sh
.venv/bin/python app.py
# Or production-style local serving (regional imports disabled by default):
.venv/bin/python serve.py
# Regression suites:
.venv/bin/python -m unittest discover -s tests -v
node --test tests/frontend/*.test.cjs
```

Open http://127.0.0.1:8000. Route search starts when the user clicks Find my loop. Road snapshots are unchanged; bundled snapshots still lack turn-restriction relations. Runtime databases are ignored by Git.
