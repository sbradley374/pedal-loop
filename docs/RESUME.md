# Resume checkpoint — October 27, 2026

Resumed on October 20. Private-staging preparation now includes a Render Blueprint, shared-password gate, empty-volume seeding, online SQLite backups, and bounded load testing. Safari desktop interaction QA succeeded; see `docs/QA-2026-10-20.md`. The temporary verification server on port 8001 was stopped after testing.

## October 27 update

Added foreground live-ride beta: GPS speed/mileage/progress, approximate road/junction cues, pause/resume, off-route and weak-GPS warnings, local-only GPS session, wake-lock request, and loop-crossing protection. See `docs/NAVIGATION.md` for limitations and the path to complete native navigation. Routing cache version is now 4; older saved rides remain readable but may lack cues.

Render is now connected through the plugin. The new ride dashboard has not been visually or physically tested.

### Render deployment continuation

### Local hosting after Oracle capacity failure

The user opted against paid Render hosting. Oracle signup succeeded in home region Ashburn; the user created `pedal-loop-vcn`, but A1 instance creation failed with out-of-capacity errors in all three availability domains. No Oracle compute instance was successfully created in this workflow.

The user requested local hosting and a temporary HTTPS link. Installed `cloudflared` through Homebrew. Password-protected Waitress is running on `127.0.0.1:8000`, with imports disabled and the exact loopback proxy trusted. Credentials are in the Git-ignored, owner-readable `.env.local-beta`; never commit or display them in logs. Local HTTP smoke checks passed for route search, alternatives, cancellation, saved-result retrieval, and GPX.

The user explicitly approved Cloudflare proxying the password-protected app and saved rides. The temporary tunnel is running at https://mega-molecular-pre-organisms.trycloudflare.com . HTTPS smoke checks passed for routing, three alternatives, result retrieval, cancellation, and GPX; unauthenticated app requests return 401. Verification used `SSL_CERT_FILE=/etc/ssl/cert.pem` because the local Python installation lacks a configured CA bundle. The Mac must remain awake and connected, and the server/tunnel processes must remain running. Restarting the quick tunnel produces a new URL. To restart locally, export the variables in `.env.local-beta` and run `.venv/bin/python serve.py`; run `cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate` in a second terminal. Stop each with Ctrl-C in its terminal. Current agent-managed process sessions: server 19668, tunnel 70789.

### Earlier Render investigation

- Verified October 27 pricing: `2c-4g` (2 CPUs / 4 GB) is $85/month; the proposed 2 GB persistent disk is $0.50/month ($0.25/GB/month). Hosting baseline is **$85.50/month**, excluding workspace fees, usage overages, taxes, and off-host backups. Source: https://render.com/pricing?trk=public_profile__reactions-text . The workspace billing plan has not been inspected.
- Remote branch `feat/routing-speed-and-hosted-beta` matches local commit `171720b7a983141614e2f1deaa000b4e3b27e3ea`; working tree was clean before this checkpoint update.
- Plugin lists “My Workspace,” ID `tea-dbgbm22vcj2c73bo0040`, but no workspace is selected. User confirmation of workspace is pending; no workspace resources were inspected or created in this continuation.
- Plugin web-service creation lacks persistent-disk configuration. Continue with the existing Blueprint through Dashboard (or authenticated API), preserving the disk and generated staging password. Do not create a diskless substitute.
- Safari successfully opened the Blueprint setup link but redirected to Render sign-in. Dashboard login is needed. Link: https://dashboard.render.com/blueprint/new?repo=https://github.com/sbradley374/pedal-loop . Select the feature branch explicitly during setup. Render CLI is not installed; platform Blueprint validation remains pending.
- No paid resources were created and no deployment was started. After workspace confirmation and Dashboard login, inspect existing resources and workspace billing, review the final quote, apply the Blueprint, then verify HTTPS/auth, routing, GPX, restart persistence, proxy behavior, alerts, and off-host backups.

## Current branch

`feat/routing-speed-and-hosted-beta`. Preserve the existing intermediate `prog/speed` commits; do not reset or rewrite them. The final checkpoint adds climbing-limit search guidance, the forced-demo safeguard, and the updated benchmark result.

## Verified

- 59 Python regression tests and 19 frontend tests pass; JavaScript syntax and Git whitespace checks pass.
- Eight simultaneous uncached Providence requests: six completed in 17.5–39.7 seconds, two queue-full 429s; worst health response 0.482 seconds, peak RSS ~834 MiB. This limits expectations for concurrent traffic. See `docs/load-test-2026-10-20.json`.
- Hosted smoke checks passed again. A saved ride and its GPX remained available after an actual Waitress process restart.
- Boulder 10-mile strict-road-filter candidates have 0% primary/secondary road exposure and meet distance tolerance. These are software invariants, not local-rider or surveyed-elevation validation.
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

1. Finish the remaining Safari/mobile checks in `docs/QA-2026-10-20.md`. Desktop generation, alternatives, save, copy link, GPX download and layout passed. A 390 × 844 responsive form looked correct, but the window/capture connection disappeared before mobile map/results checks. Arc's earlier blank-page failure also affected script-free JSON.
2. Container verification passed: GitHub Actions run 39495796695 completed successfully for Docker build, routing smoke checks, and ride/GPX persistence after container recreation. Python 3.9/3.12 jobs passed too. Docker remains unavailable locally.
3. Render plugin is connected; workspace confirmation and Dashboard login are pending. `render.yaml` proposes paid 2 CPU / 4 GB hosting with a 2 GB persistent disk and generated staging password, verified at $85.50/month baseline above. No paid resources were created and no site is deployed. Next: inspect workspace billing/resources, provision staging, verify HTTPS/proxy/auth, and configure alerts/off-host backups. See deployment guide.
4. Boulder retry succeeded: local 9 km road/terrain snapshot `data/region-545e35694e9da76e.osm.json.gz`, region ID `bf8d7a379fd363ea`. Four route cases passed (5 miles, 10 miles, traffic disabled, strict major exclusion), with three alternatives each in 1.3–1.8 seconds. See `docs/benchmark-boulder-2026-10-20.json`. The snapshot remains Git-ignored and is not bundled for fresh clones; restart the local app to discover it. Madison remains unimported. Avoid automatic retry loops.
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
