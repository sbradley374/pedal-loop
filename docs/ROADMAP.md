# Roadmap

The [README](../README.md) describes implemented features. This page tracks remaining work; it is not a promise that hosting alone makes navigation complete.

## 1. Validate the existing iPhone beta

The app builds and has launched on a physical iPhone. Complete the [device acceptance checklist](IOS.md#physical-device-acceptance-checks): full loop, crossings, wrong turns, weak GPS, permission changes, screen lock, calls/audio interruptions, battery use, termination/recovery and disconnected-server behavior. Audit routes against local cycling knowledge. Finish browser ride-dashboard/mobile QA separately.

## 2. Improve navigation and recovery

- Audit mapped maneuvers, roundabout exits, short connectors and complex junctions. Calibrate spoken cue lead distances with actual rides.
- Test matching on parallel roads, urban noise, crossings and wrong-way travel. The current bounded matcher cannot reliably rejoin far ahead after a detour.
- Add deliberate **Rejoin route** and **Route home** actions before automatic rerouting. A new backend recovery API should connect an accurate current fix to reachable forward points or the original start, respecting roads/restrictions/preferences and clearly showing no-route failures.
- After deliberate recovery is validated, add sustained off-route detection, cooldowns, cancellable requests and stale-result rejection. Replace remaining geometry/cues atomically, with defined poor-GPS and disconnected-server behavior. Sending live fixes for recovery changes the current local-only tracking privacy model.

## 3. Make a stable regional beta

Choose hosting only after reviewing current costs and measured resource needs. Add stable HTTPS, health/error monitoring, scheduled off-host backups and a restore drill. Keep imports controlled; review map-provider capacity and attribution. Refresh bundled snapshots to include supported restriction relations, audit representative rides, and calibrate terrain-based climbing estimates.

There are no individual accounts, user-owned routes or account deletion workflow. Add them before promising private accounts. A shared password is only a small-group gate.

## 4. Expand coverage and offline capability

A globally viewable map does not supply a global routing graph. Build a managed OSM extract/update pipeline and regional coverage/boundary strategy before wider geographic claims. Current imports are capped at 30 km; jobs are in memory and threads do not provide CPU scaling. Multi-instance hosting needs shared durable jobs, process workers and coordinated storage.

Downloaded native routes already retain geometry/cues. Offline basemaps require a provider/licensing choice, region downloads, storage limits and expiry management. Offline route generation/rerouting is a separate routing-engine/data project. GPX alone does not contain map tiles or an offline routing graph.

Android, editable waypoints/avoid areas and TestFlight/App Store distribution remain future work. Native place search is implemented with MapKit; browser address search is not implemented.
