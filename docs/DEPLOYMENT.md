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

The CI `container` job builds and starts Compose, checks routing/export/cancellation, recreates the container with the same volume, and checks saved-ride persistence. Its remote result still needs verification. Docker is unavailable in the local development environment. Local Waitress restart persistence has passed. Browser/mobile interaction QA remains incomplete because native Arc interaction repeatedly lost page content. See the roadmap for the remaining release work.
