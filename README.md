# Pedal Loop

A regional cycling-loop planner with a Python route engine, a browser interface, and a native iPhone beta. It generates loops on OpenStreetMap roads, estimates climbing from terrain data, and exports GPX tracks.

**Current status:** local development and phone testing work. The iPhone app has launched on a physical device; a full outdoor ride and background navigation still need validation. There is no permanent hosted backend. Automatic rerouting and downloaded offline maps are not implemented.

## Start here

From a fresh checkout, Python 3.9+ is enough for the bundled Providence and Burlington datasets:

```sh
python3 app.py
```

Open **http://127.0.0.1:8000**. Choose Burlington and a 5-mile target for a small first search, then click **Find my loop**. Stop with Ctrl-C. If port 8000 is occupied, use `python3 app.py --port 8001`.

For dependency installation, a password-protected HTTPS link, iPhone connection, and troubleshooting, follow the **[startup guide](docs/STARTUP.md)**. Local browser use does not require Xcode, Docker, or a hosting account.

## What works today

| Capability | Current behavior |
|---|---|
| Loop generation | 5–75 mile targets, up to three alternatives, hard distance tolerance, traffic/stop proxies, hill preferences, pavement/major-road filters, optional estimated climbing ceiling |
| Road coverage | Providence and Burlington are bundled; additional regional imports are available locally, capped at 30 km radius. A map or place-search result does not imply routing coverage. |
| Maps and elevation | Browser uses Leaflet/OSM tiles; iPhone uses Apple Maps and place search. Both show routes and terrain-based climbing profiles. Basemaps need their own internet connection. |
| Save and export | Server stores results and GPX links. Browser saves result references; iPhone stores route geometry/cues locally and exports GPX. |
| Browser ride mode | Foreground GPS, speed/mileage/progress, approximate mapped cues, pause/resume, weak-GPS/off-route warnings. Hiding the page pauses tracking. |
| Native iPhone ride mode | GPS dashboard, spoken cues, simulation, pause/resume, local summaries and paused session recovery. Background location/audio is implemented but not validated on a complete physical ride. |
| Offline use | Downloaded iPhone routes retain geometry and cues. There is no offline basemap download, offline route generation, or automatic rerouting. |

Routes and instructions are approximate. Traffic is inferred from road classes, and terrain heights can differ from road decks and tunnels. Bundled snapshots lack turn-restriction relations; new imports support only basic node-via restrictions. Distance targets and restrictive filters can legitimately return no match. See [routing assumptions](docs/ROUTING.md) and [navigation limitations](docs/NAVIGATION.md).

## Project guide

| Guide | Purpose |
|---|---|
| [Startup](docs/STARTUP.md) | Browser, protected local server, temporary HTTPS link, troubleshooting |
| [iPhone](docs/IOS.md) | Xcode/signing, installation, device test checklist, local storage |
| [Navigation](docs/NAVIGATION.md) | GPS matching, cue behavior, browser/native differences |
| [Routing and terrain](docs/ROUTING.md) | Search assumptions, elevation method, regional imports |
| [API](docs/API.md) | HTTP endpoints and response conventions |
| [Deployment](docs/DEPLOYMENT.md) | Docker, configuration, persistence, backups and hosting requirements |
| [Development](CONTRIBUTING.md) | Source layout and regression checks |
| [Roadmap](docs/ROADMAP.md) | Remaining work in priority order |
| [Resume checkpoint](docs/RESUME.md) | Current handoff and validation status |
| [Archive](archive/README.md) | Historical reports, GPX examples, screenshots and deferred Render proposal |

The active code lives in `planner/`, `web/`, and `ios/`. Import, backup and verification scripts remain in `scripts/`; they are supported tools, not abandoned prototypes. The synthetic `--demo` mode is retained for development/tests and is explicitly labeled as invented data.

## Data and privacy

Searches send the selected start/preferences to the configured backend, which stores route results in SQLite for up to 30 days and at most 500 searches. Links are unlisted, with shared-password protection when configured; there are no individual accounts or per-user access controls. Live GPS tracking is not uploaded. Native recovery and saved routes remain on the phone. See [storage and retention](docs/DEPLOYMENT.md#persistent-results-and-privacy).

OSM data is **© OpenStreetMap contributors**, [ODbL](https://www.openstreetmap.org/copyright); provenance is in [data/README.md](data/README.md). Terrain uses Mapzen/AWS Terrain Tiles with [source attribution](data/TERRAIN-ATTRIBUTION.md). Application code is [MIT licensed](LICENSE); the vendored [Leaflet license](web/vendor/Leaflet-LICENSE) is retained. Map/provider requests disclose the viewed/downloaded area and IP to the relevant service. There is no offline tile downloader or prefetching. Review provider terms before scaling usage or changing providers.
