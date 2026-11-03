# iPhone development beta

The native client is in `ios/PedalLoop.xcodeproj`. It requires iOS 17 or later and Xcode 16 or later. It reuses the Python route engine; it does not run Python on the phone.

## Current status

Implemented: SwiftUI planning and ride screens, Apple Maps and place search, cached-region selection, route preferences and alternatives, climbing profiles, GPX sharing, downloaded routes/cues, GPS speed/mileage/progress, spoken mapped cues, weak-GPS/off-route warnings, pause/resume, local ride summaries, and paused session recovery. A clearly labeled simulation previews a generated route without requesting GPS permission.

This is a development beta. On October 28, the unsigned iOS simulator build succeeded with Xcode 27.1, all 16 Swift core tests passed, and the Swift HTTPS client generated three Burlington alternatives with cues and local GPX. The app installed/launched on the iOS 17.5 iPhone 15 Pro simulator; a screenshot verified the initial planner, Apple basemap and tabs. On November 2, Personal Team signing and Developer Mode setup succeeded and the user confirmed the app opened on their iPhone 16 Pro. A complete outdoor ride and physical-device background behavior remain unverified. A passing core/API test does not establish reliable real-ride navigation.

Automatic rerouting, reliable road-network map matching, complex maneuver interpretation, downloaded offline basemaps, Android, and TestFlight distribution remain future work. The current bounded matcher deliberately refuses far-ahead rejoining instead of jumping between loop crossings. After a detour, return near the last matched route position. Saved routes can show their geometry and cues without the backend; basemap availability is not guaranteed offline.

## Install on your iPhone

1. Open Xcode and finish its license/component setup, including iOS platform support. In Xcode Settings → Accounts, add your Apple ID.
2. Open `ios/PedalLoop.xcodeproj`. Select the PedalLoop target → Signing & Capabilities, keep automatic signing, and choose your Personal Team. If the bundle identifier is unavailable, change it to your own unique identifier.
3. Connect and unlock your iPhone, trust this Mac, and enable Developer Mode on the phone when requested. Select your phone as the run destination and press Run. Resolve any device trust prompt in Settings → General → VPN & Device Management.
4. Open the app's **Server** tab. Enter the current HTTPS tunnel URL and the username/password from your local `.env.local-beta`. Tap **Connect and save**. Credentials are stored in the device Keychain and never bundled in source.
5. In **Plan**, choose a cached region, set a start within coverage and a distance, then **Find my loop**. Compare options, save one, and first use **Preview navigation without GPS**. End the simulation before starting a real GPS ride.
6. For a GPS ride, begin near the marked route start, tap **Start ride**, and grant precise location while using the app. Pause or End stops tracking. Confirm the device tests below before relying on screen-locked cues.

A free Personal Team supports initial testing on your own device, with periodic reprovisioning; it is not TestFlight distribution. See [Apple's account capabilities](https://developer.apple.com/help/account/basics/about-your-developer-account). App Store publication is not part of this setup.

## Keep the route server online

Use the existing running processes when available. Otherwise, from the repository root, start the backend in one terminal:

```sh
set -a
source .env.local-beta
set +a
.venv/bin/python serve.py
```

In another terminal:

```sh
cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate --edge-ip-version 4
```

Copy the HTTPS address printed by cloudflared into the phone's Server settings. A restarted tunnel gets a new address. Both processes and the Mac must remain awake and connected for new route searches. Ctrl-C stops each process. Do not put the password in URLs, scripts, Git, or screenshots. Public beta exposure requires the shared-password gate; keep regional imports disabled.

## Build and verification

From the repository root, with Xcode's command-line tools selected:

```sh
swift test --package-path ios
xcodebuild -project ios/PedalLoop.xcodeproj -scheme PedalLoop \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/pedal-loop-ios-build CODE_SIGNING_ALLOWED=NO build
```

The project is generated from `ios/project.yml`; after changing its structure, regenerate with `xcodegen generate --spec ios/project.yml`. XcodeGen is not needed to open the checked-in project. To preserve signing across regeneration, place `PEDAL_DEVELOPMENT_TEAM = YOUR_TEAM_ID` in the ignored `ios/Signing.local.xcconfig`; `Signing.xcconfig` includes it optionally. The current Mac's selected team is preserved there. Do not commit personal signing changes or `xcuserdata`.

## Next navigation milestones

1. Validate full-loop rides, screen locking, audio interruptions, GPS drift and battery use on the physical phone before expanding navigation claims.
2. Add deliberate recovery actions: **Rejoin route** and **Route home**. The backend should route from an accurate current fix to reachable forward points or the original start, honoring one-way roads and supported turn restrictions. Score rejoin points for added distance, repeated roads and the rider's road/climbing preferences. Clearly show changes and no-route failures.
3. Add automatic rerouting only after recovery is validated. Require sustained off-route evidence, use a cooldown and cancellable requests, reject stale results, and atomically replace remaining geometry/cues. Define behavior at loop crossings, on parallel roads, during poor GPS, and without server connectivity. Live fixes would be sent to the route server for recovery; disclose this change from local-only tracking.
4. Improve complex maneuvers and real-ride map matching; add offline basemap support and a stable backend so navigation recovery is not dependent on a Mac/tunnel being online.

Rerouting is not implemented in this checkpoint. It requires a new backend recovery API and native ride-state changes; simply launching another loop search from the current position would discard the intended remaining ride.

For a live contract check, export the beta credentials as above, then run:

```sh
PEDAL_SERVER_URL=https://YOUR-CURRENT-HOST.trycloudflare.com \
  swift run --package-path ios pedal-api-smoke
```

This checks the catalog, a five-mile Burlington search, result alternatives, cues, geometry, initial loop matching and local GPX generation. It requires the bundled Burlington region. The test prints no credentials. Core regression tests exercise loop crossings, a full traversal, GPS noise/staleness, pause gaps, off-route suppression, recovery, JSON compatibility and HTTPS origin validation.

The iOS GitHub Actions workflow builds for an unsigned simulator and runs the core tests on macOS. It does not install on a real device or test background behavior.

## Physical-device acceptance checks

- Planning: connect with correct/incorrect credentials, generate and cancel, switch regions/options, inspect map/profile, save/reopen after relaunch, and share a GPX to Files.
- Navigation preview: check small-screen layout, large text, cue sheet, follow/recenter, pause/resume and arrival. Simulation must remain labeled and must not save a ride summary.
- Location: deny permission, disable Precise Location, then enable it. Verify helpful states and that permission changes do not automatically resume a deliberately paused ride.
- Ride: walk a short known route first. Check start/finish coincidence, crossing paths, stationary jitter, wrong turns and GPS loss. Off-route/weak GPS must suppress misleading cue distances. Never test by interacting with the phone while cycling.
- Background: lock the phone during an active ride; verify GPS progress and audible cues continue. Test a call, music playback, Bluetooth audio, app switching and a longer session for battery use. Pause/End must stop the location indicator and restore other audio.
- Recovery: terminate/relaunch during a ride; recovery must be paused and require Resume. Check saved routes with the server disconnected. No guarantee of basemap tiles in airplane mode.
- Privacy: delete saved routes/history, verify no live GPS breadcrumb upload, and keep server credentials out of logs. No analytics SDK is included.

## Data and retention

MapKit requests go to Apple. Route searches send the chosen start and preferences to the configured backend through the tunnel provider; backend results are persisted under its existing policy. Live GPS fixes stay in memory on the phone. Local recovery stores the selected planned route, progress and mileage, not a breadcrumb trace; it is cleared on End. Up to 20 downloaded routes and 30 ride summaries are retained locally, with deletion controls and backup exclusion. Credentials use device-only Keychain storage. The privacy manifest is a development declaration and must be reviewed with the final hosting/analytics configuration before distribution.
