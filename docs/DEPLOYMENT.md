# Deployment and operations

Current development uses a local server with an optional password-protected HTTPS tunnel. There is no permanent hosted backend. GitHub hosts source/CI, not the Python route engine. See [startup](STARTUP.md) for the supported local and phone workflow.

## Docker on localhost

With Docker installed, from the repository root:

```sh
docker compose up --build
```

Compose binds only to localhost. It is unauthenticated unless `STAGING_USER` and `STAGING_PASSWORD` are exported together before starting it. The Python tunnel instructions use Waitress directly; Compose fixes `PUBLIC_ORIGIN` to localhost, so do not expose it unchanged through that tunnel. For external hosting, configure the public origin and proxy explicitly.

A named volume retains snapshots and results across container replacement. The image seeds bundled data on first creation and does not overwrite existing volume files on updates. Use `docker compose down` to stop; adding `--volumes` deletes stored data. Only the two bundled regions are included in the build context; new local imports must be transferred explicitly.

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

Results are unlisted bearer links, not user-owned private rides. A result contains the selected start and road geometry; anyone with its random link and any configured shared beta credentials can view/download it. The UI stores up to 12 saved references in browser storage. Server results expire after 30 days and can be evicted sooner when more than 500 searches are stored. Expired records are purged on subsequent writes; take that into account for backup retention. No account system or account-level deletion UI is provided yet.

Back up the volume using a SQLite-aware backup or while the app is stopped. Do not commit databases, local terrain caches, or credentials. Search/import jobs are in memory and are lost on restart; existing completed rides survive. Do not run multiple replicas expecting jobs to be shared. Use HTTPS, restrict volume access, and define a host privacy/retention notice before inviting users.

## Before inviting riders

- Deploy a staging instance, set the public origin and proxy IP, and verify background searches, cancellation, saved links, GPX, and restart persistence through HTTPS.
- Arrange adequate map/data service capacity and attribution. Public Overpass and OSM tiles are best effort, not contracted infrastructure.
- Audit routes against local cycling knowledge in each advertised region. Bundled snapshots predate turn-restriction imports; refresh before claiming supported restrictions for them.
- Load-test expected concurrency and record latency, queue rejection rate, memory, and disk use. Set up uptime/error monitoring and backups.
- Add authentication and user-owned rides before promising private accounts. Add a shared queue and process workers before scaling replicas.

## Password gate and hosting status

Set both `STAGING_USER` and `STAGING_PASSWORD` for a private beta. The gate protects the app, API, saved links and GPX; only `GET /api/health` remains unauthenticated. Setting only one variable fails startup; removing both turns authentication off. This is a shared beta gate, not individual accounts or per-user privacy. Keep credentials out of source, logs and links.

`PUBLIC_ORIGIN` overrides `RENDER_EXTERNAL_URL` when present. Configure the exact proxy peer and HTTPS origin for the chosen host. Do not trust wildcard forwarded headers. Monitor `/api/health`, `route_job status=... elapsed_seconds=...` logs, unexpected exceptions, latency and disk/memory use. Logs do not intentionally include requested coordinates or geometry.

Paid Render hosting was deferred, and its unused proposal is in [the archive](../archive/deployment/render.yaml.example). Oracle A1 attempts failed for capacity; no compute instance was created in that workflow. Neither is an active deployment target. Recheck configuration and cost before revisiting cloud provisioning.

CI builds Docker, exercises routing/export/cancellation, recreates the container with its volume, and verifies persistence, authentication and backup. Local Waitress restart persistence has also passed. Physical ride validation and stable hosting/monitoring remain release work; see [the roadmap](ROADMAP.md).

## Load measurements and repeatable checks

The isolated local Providence burst in [the archived load report](../archive/reports/load-test-2026-10-20.json) used eight simultaneous requests and an empty result database. Six uncached searches completed in 17.5–39.7 seconds; two received the expected queue-full 429. All health probes succeeded, worst 0.482 seconds. Peak resident memory was 873,971,712 bytes (~834 MiB), measured with macOS `/usr/bin/time -l`. This is one local burst, not a production capacity guarantee or multi-region memory ceiling. Repeat on staging before choosing capacity or inviting many concurrent riders.

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

To restore, stop the app and preserve the old data directory. Build a **new** data directory from the dataset backup, place the database backup there as `routes.sqlite3`, and point `DATA_DIR` to it. Do not mix an old `-wal`/`-shm` file with a restored database. Start the app and verify a known saved ride and GPX using `python scripts/smoke_http.py --base http://127.0.0.1:8000 --verify-result FILE`, where FILE contains its result ID. Keep the old directory until the drill passes. Automated off-host backup and a hosted recovery drill remain release gates.
