# Hosted beta deployment

The repository contains a single-instance Python web app. GitHub hosts source code; it does not run the route engine. Nothing has been deployed publicly by these changes.

## Start locally with the hosted server

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-hosted.txt
.venv/bin/python serve.py
```

Open http://127.0.0.1:8000. The Waitress runner disables public regional downloads by default. Cached regions still work. The original `python app.py` remains the local development runner with imports enabled.

Alternatively, with Docker installed:

```sh
docker compose up --build
```

The Compose file binds only to localhost. A named volume retains snapshots and result storage across container replacement; the image seeds it on first creation. Later image updates do not overwrite an existing volume. Import new snapshots into that volume explicitly. Do not delete the volume unless you intend to discard stored rides/data.

## Hosting settings

Use a persistent container/VM host, one app instance, and a managed HTTPS proxy. An initial 4 GB RAM allocation is a conservative starting point, not a load-tested capacity guarantee; measure actual peak memory under concurrent searches and dense regional loads. This Python graph is not suitable for a small edge-function memory limit.

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` (`0.0.0.0` in Docker) | Listener; restrict external access to the HTTPS proxy |
| `PORT` | `8000` | Listener port |
| `DATA_DIR` | project `data/` | Writable persistent volume with road/terrain manifests and `routes.sqlite3` |
| `ROAD_DATA` | `DATA_DIR/providence.osm.json.gz` | Default road snapshot |
| `PUBLIC_ORIGIN` | request origin | Set to exact public origin, e.g. `https://rides.example.com`, without a trailing slash |
| `ALLOW_IMPORTS` | `0` | Keep disabled for visitors; preload regions using the CLI |
| `TRUSTED_PROXY` | unset | Actual reverse-proxy peer IP if using forwarded client IP/protocol; wildcards rejected |
| `TILE_URL` | OSM standard tiles | Substitute a suitable map provider and update its attribution in `web/app.js`/footer |

Waitress serves the app with eight HTTP threads, a body-size limit, and channel timeouts. Searches use a separate pool of two threads with four queue slots. The GIL limits CPU parallelism. Application submission limits are 20 route submissions/minute/client IP and two imports/minute/IP; queue overflow returns 429. Configure the trusted proxy correctly or all clients behind it share a rate limit. Also configure edge limits appropriate to your audience.

Health check: `GET /api/health`. A healthy response means the process started; it is not a live test of Overpass, terrain providers, or every regional route.

## Persistent results and privacy

Results are unlisted bearer links, not authenticated private rides. A result contains the selected start and road geometry; anyone with its random link can view/download it. The UI stores up to 12 saved references in browser storage. Server results expire after 30 days and can be evicted sooner when more than 500 searches are stored. Expired records are purged on subsequent writes; take that into account for backup retention. No account system or account-level deletion UI is provided yet.

Back up the volume using a SQLite-aware backup or while the app is stopped. Do not commit databases, local terrain caches, or credentials. Search/import jobs are in memory and are lost on restart; existing completed rides survive. Do not run multiple replicas expecting jobs to be shared. Use HTTPS, restrict volume access, and define a host privacy/retention notice before inviting users.

## Before inviting riders

- Deploy a staging instance, set the public origin and proxy IP, and verify background searches, cancellation, saved links, GPX, and restart persistence through HTTPS.
- Arrange adequate map/data service capacity and attribution. Public Overpass and OSM tiles are best effort, not contracted infrastructure.
- Audit routes against local cycling knowledge in each advertised region. Bundled snapshots predate turn-restriction imports; refresh before claiming supported restrictions for them.
- Load-test expected concurrency and record latency, queue rejection rate, memory, and disk use. Set up uptime/error monitoring and backups.
- Add authentication and user-owned rides before promising private accounts. Add a shared queue and process workers before scaling replicas.

The CI `container` job builds and starts Compose, checks routing/export/cancellation, recreates the container with the same volume, and checks saved-ride persistence. The Docker build, routing checks, and persistence after container recreation passed in [GitHub Actions run 39495796695](https://github.com/sbradley374/pedal-loop/actions/runs/39495796695). Docker is unavailable in the local development environment. Local Waitress restart persistence has passed. Safari desktop generation, alternative selection, saving/copying/export and visual layout passed, as did a 390-pixel form preview. Remaining browser/mobile flows are listed in `QA-2026-10-20.md`. Arc automation blanks even script-free JSON; Safari later worked but lost its window connection during the mobile pass. See the roadmap for the remaining release work.

## Private Render staging proposal

`render.yaml` proposes one Docker web service in Virginia, 2 CPUs / 4 GB RAM, and a 2 GB persistent disk mounted at `/app/storage`. This is a paid-resource proposal, not an existing deployment. Review the current quoted compute/disk cost before provisioning. Install/connect the Render plugin to make the account available. Use this feature branch when creating the Blueprint; automatic deploys are disabled initially.

The configuration follows Render's [Blueprint reference](https://render.com/docs/blueprint-spec) and [persistent disk guidance](https://render.com/docs/disks). The service starts by seeding missing bundled datasets onto the persistent disk; existing files and ride databases are never replaced. The local Compose configuration exercises the same separate storage directory. New region snapshots prepared only on a developer machine are not automatically on the hosted disk.

The Blueprint generates `STAGING_PASSWORD` and sets `STAGING_USER=beta`. The shared HTTPS password gate protects the app, APIs, saved links, and GPX. Only `GET /api/health` remains unauthenticated for uptime checks. This is a private beta gate, not individual user accounts or per-user ride privacy. Keep both environment variables set; do not publish credentials in Git, logs, links, or chat. Removing both turns the gate off. `PUBLIC_ORIGIN` overrides the Render-provided `RENDER_EXTERNAL_URL` when a custom domain is used.

Keep imports disabled. Confirm the actual proxy configuration before allowing multiple testers: without a trusted proxy, the 20-submissions/minute limit can be shared by all visitors. Do not trust arbitrary forwarded headers or use a wildcard. Configure the host's uptime alert for `/api/health`, and review `route_job status=... elapsed_seconds=...` logs plus unexpected-search exception logs. These logs do not intentionally include requested coordinates or route geometry. Host alerts and off-site backup scheduling still require account access.

## Load measurements and repeatable checks

The isolated local Providence burst in `docs/load-test-2026-10-20.json` used eight simultaneous requests and an empty result database. Six uncached searches completed in 17.5–39.7 seconds; two received the expected queue-full 429. All health probes succeeded, worst 0.482 seconds. Peak resident memory was 873,971,712 bytes (~834 MiB), measured with macOS `/usr/bin/time -l`. This is one local burst, not a production capacity guarantee or multi-region memory ceiling. Repeat on staging before choosing capacity or inviting many concurrent riders.

```sh
python scripts/load_test.py --base http://127.0.0.1:8000 --requests 8 --output benchmark-results/load.json
python scripts/smoke_http.py --base http://127.0.0.1:8000
```

For the password-protected site, supply `STAGING_USER` and `STAGING_PASSWORD` through your shell's secure environment. Both scripts use them without writing them to reports. Use a fresh result database for cold-cache comparisons; do not delete a live database to run a benchmark. The load script sends at most 12 submissions, reports queue rejections separately, and attempts to cancel searches that exceed its deadline.

## Backup and recovery drill

```sh
python scripts/backup_results.py --source /app/storage/routes.sqlite3 --output /app/storage/backups/routes-YYYY-MM-DD.sqlite3
```

The script uses SQLite's online backup API, checks integrity, writes with owner-only permissions, and refuses to overwrite a backup. A live-WAL restore regression test verifies saved rides remain readable. Back up road snapshots, elevation sidecars, and region manifests separately; disable imports while copying those files. Copy backups to private off-host storage and apply a retention policy consistent with ride expiration. A backup kept only on the same disk does not protect against disk loss.

To restore, stop the app and preserve the old data directory. Build a **new** data directory from the dataset backup, place the database backup there as `routes.sqlite3`, and point `DATA_DIR` to it. Do not mix an old `-wal`/`-shm` file with a restored database. Start the app and verify a known saved ride and GPX using `smoke_http.py --verify-result FILE`, where FILE contains its result ID. Keep the old directory until the drill passes. Automated off-host backup and a hosted recovery drill remain release gates.
