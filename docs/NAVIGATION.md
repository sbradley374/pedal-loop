# Live ride navigation

## Foreground beta, October 27, 2026

Generate a real-road route, select an alternative, and choose **Start live ride**. The browser requests location permission only when you start. Synthetic demo routes cannot start a ride.

The dashboard shows current speed in mph (device speed when available, otherwise an estimate from accepted GPS movement), approximate GPS mileage, remaining route mileage, active elapsed time, and distance to the next mapped cue. A blue marker follows your position; following can be disabled to inspect the map. Pause/resume and End ride release the location watcher. Changing route/settings ends the current session. Clicking the map during a ride does not move the route's start.

Tracking starts within 60 m of the planned start. It rejects fixes over 40 m reported uncertainty, fixes older than 15 seconds, and implausible position jumps. Small movement is filtered to reduce stationary GPS jitter. Progress matching uses a limited forward window so the loop's endpoint or a later crossing is not mistaken for immediate completion. Off-route or ambiguous positions suppress remaining distance and cues. Rejoining far ahead is not supported: stop safely and check the map; there is no automatic rerouting.

GPS positions remain in memory in this browser; no ride-position upload or permanent ride recording was added. Reloading or ending loses the live session. Normal basemap requests still tell the tile provider which area is being viewed. Mileage is an estimate and excludes gaps after pausing, losing GPS, or suspending the app.

Keep the page visible. Hiding the app or locking the screen pauses tracking, and resuming requires tapping Resume. A screen wake lock is requested when supported, but the OS can release it. Browser GPS requires a secure context and location permission. See [Geolocation watchPosition](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/watchPosition) and [Screen Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API).

## Cue preview is not complete turn-by-turn navigation

Cues come from the selected directed path's road names, junctions, and heading changes; they do not reroute the loop through another provider. Each has a distance and geometry index. The routing cache version was incremented so new searches include them. Previously saved rides remain readable; they may have no cues and display an instruction to regenerate.

These cues are approximate. Roundabout exits, complicated junctions, short connecting segments, direction-specific restrictions, lane guidance, and missing map tags are not fully interpreted. Geometry can misclassify a maneuver; signs and actual road access still take precedence. There are no voice instructions, automatic rerouting, locked-screen navigation, downloaded offline basemaps, or native phone app yet. Do not advertise this beta as a complete navigation system.

## Verification

- Deterministic GPS replays cover start/finish ambiguity, ordinary progress, jitter, implausible jumps, inaccurate/stale fixes, off-route suppression, missing-mileage gaps, and a full loop.
- Controller tests cover hiding/resuming, permission denial, watcher cleanup, and ignoring callbacks after stopping.
- Backend tests cover named turns, cumulative cue distance, and avoiding false turns at ordinary shape points.
- HTTP smoke verifies cues are ordered and end at the final coordinate alongside routing, GPX, cancellation, and cache checks.
- Physical-device riding, browser layout and GPS replay against recorded real rides remain unverified. Browser control was unavailable on October 27.

## Work required for complete mobile navigation

1. Audit maneuver generation against complex junctions and roundabouts; retain the map tags needed for dependable instructions and announce cues with tested lead distances.
2. Validate map matching on real rides: parallel roads, crossings, tunnels, wrong-way travel, urban GPS noise, starts away from the loop, detours, and rejoining.
3. Build an iOS/Android app with OS-supported background location, explicit permission and battery handling, session recovery, and locked-screen behavior. A browser screen wake lock is not a replacement.
4. Add spoken/haptic cues, off-route recovery that preserves ride preferences, and arrival handling after those behaviors are validated.
5. License/provision offline basemaps and keep the selected route/cues available through loss of connectivity. Define tracking retention and optional ride-history controls before storing location histories.
6. Test on physical iPhone and Android devices, including denied permissions, calls, screen locking, app termination, battery restrictions, and long rides.

Public deployment still requires Render installation/connection, approval of a concrete hosting quote, and HTTPS staging verification. The prepared Render deployment configuration remains available; no resources were provisioned in this session.
