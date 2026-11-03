# Resume checkpoint — November 2, 2026

## Current state

The regional Python planner, browser interface and native iPhone beta are implemented. The working branch is `feat/routing-speed-and-hosted-beta`; native implementation was committed/pushed as `648b13c`. Read the [README](../README.md) for functionality and [startup guide](STARTUP.md) to run again. The repository cleanup centralizes setup/status and archives old research, reports, exports, screenshots and the unused Render proposal.

There is no permanent hosted backend. Development uses local Waitress and an optional temporary Cloudflare HTTPS tunnel. Use the URL printed by the current tunnel process; old URLs and process IDs are intentionally not recorded here. Paid Render was deferred. Oracle provisioning failed for A1 capacity in all three availability domains; no compute instance was created in that workflow.

## Local state to preserve

- `.env.local-beta`: ignored local server configuration and beta credentials. Never print or commit it. Fresh checkouts use `.env.example` and the startup guide's one-time generation step.
- `ios/Signing.local.xcconfig`: ignored Personal Team choice, optionally included by the checked-in project. Do not commit personal signing state.
- `data/routes.sqlite3`, terrain cache and additional regional downloads: ignored runtime data. Providence/Burlington are bundled; a local Boulder import is not included in clones.
- Existing server/tunnel processes can be reused; cleanup does not require stopping them or deleting runtime data.

## Validation and limitations

At native checkpoint `648b13c`, 59 Python, 19 frontend and 16 Swift tests passed locally. GitHub Python 3.9/3.12, container/persistence/authentication and native simulator checks passed. The earlier Python 3.9 environment failure was fixed by pinning Ubuntu 24.04; it was not an app-test failure.

The user confirmed launch on a physical iPhone 16 Pro. Full-loop outdoor riding, background GPS/audio, battery and recovery acceptance remain pending. Simulator builds and deterministic GPS tests do not establish reliable real-ride navigation. Automatic rerouting, downloaded basemaps and offline route generation are unimplemented. Historical benchmarks/browser QA are indexed in [the archive](../archive/README.md).

## Cleanup verification

The cleanup reran all 59 Python, 19 frontend and 16 Swift tests successfully. An isolated copy containing only repository files passed browser startup, generated private configuration (including overwrite protection), password-gate checks, bundled-region routing/GPX/cancellation/cache checks, empty-volume seeding and saved-result retrieval after a Waitress restart. Local Markdown links resolve. No application source or native project files changed. Docker packaging now excludes personal/native build state and packages only the two documented regions.

## Next work

Start with the [physical-device checklist](IOS.md#physical-device-acceptance-checks), then follow [the roadmap](ROADMAP.md). Hosting and navigation recovery are deferred decisions, not currently running deployments or implemented features. Use [CONTRIBUTING](../CONTRIBUTING.md) for repeatable checks and [deployment operations](DEPLOYMENT.md) for data retention/backups.
