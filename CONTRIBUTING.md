# Development

Start with the [startup guide](docs/STARTUP.md). Changes should preserve regional coverage warnings, explicit no-match behavior, data attribution and the distinction between approximate cues and validated navigation.

## Source layout

| Path | Role |
|---|---|
| `app.py`, `serve.py` | WSGI API/local development runner and protected Waitress runner |
| `planner/graph.py`, `compact.py`, `routing.py` | Directed road graph, compression/indexes, preference-weighted loop search |
| `planner/elevation.py`, `regions.py`, `network.py` | Terrain math/cache, regional catalog/imports, bounded HTTPS downloads |
| `planner/service.py`, `storage.py`, `staging.py` | Bounded jobs/cancellation, SQLite retention, optional password gate |
| `planner/navigation.py`, `export.py` | Approximate route cues and GPX serialization |
| `web/` | Browser planner, foreground GPS ride mode, vendored Leaflet |
| `ios/PedalLoop/` | SwiftUI/MapKit app, Core Location/audio, Keychain and local storage |
| `ios/Sources/PedalCore/` | HTTP contract, route models and deterministic GPS matcher |
| `tests/`, `ios/Tests/` | Python, browser JavaScript and Swift regressions |
| `scripts/` | Import, enrichment, benchmarks, HTTP smoke and SQLite backup tools |
| `data/` | Two bundled road/terrain regions; ignored runtime data stays local |
| `archive/` | Historical reference only |

## Regression checks

Install server dependencies as in the startup guide. Node.js 18+ is needed for browser tests; full Xcode is needed for Swift/iOS checks.

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check web/app.js
node --check web/ride-tracker.js
node --check web/ride-mode.js
node --test tests/frontend/*.test.cjs
.venv/bin/python -m compileall -q app.py serve.py planner scripts
git diff --check
```

Native checks:

```sh
swift test --package-path ios
xcodebuild -project ios/PedalLoop.xcodeproj -scheme PedalLoop \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/pedal-loop-ios-build CODE_SIGNING_ALLOWED=NO build
```

The `Tests` GitHub workflow runs Python 3.9/3.12, browser tests, Docker routing smoke, authentication, backups and result persistence after container recreation. The `iOS beta` workflow runs Swift tests and an unsigned simulator build when native sources/workflow change. Neither substitutes for [physical-device acceptance](docs/IOS.md#physical-device-acceptance-checks).

## Integration and data checks

Against a running server (export the shared credentials first if protected):

```sh
.venv/bin/python scripts/smoke_http.py --base http://127.0.0.1:8000
```

Optional slower real-data checks:

```sh
.venv/bin/python scripts/verify_snapshot.py
.venv/bin/python scripts/benchmark.py --output benchmark-results/latest.json
```

Benchmarks may exit nonzero when a restrictive scenario has no qualifying route; read each result before treating that as a regression. Do not delete a live database for a cold-cache benchmark. `load_test.py` is a deliberate concurrency test, not a startup step. `backup_results.py` uses SQLite's online backup API; see the [recovery procedure](docs/DEPLOYMENT.md#backup-and-recovery-drill).

The Xcode project is checked in. If its structure changes, regenerate with `xcodegen generate --spec ios/project.yml` and commit the generated project alongside the specification. Keep personal signing in ignored `ios/Signing.local.xcconfig`. Do not commit `.env.local-beta`, databases, terrain caches, downloaded regional files, build products, credentials or personal Xcode state.
