# Startup guide

Run commands from the repository root. The browser/server works with Python 3.9+; iPhone builds also need a Mac with Xcode and iOS platform support. A fresh checkout includes Providence and Burlington roads and elevation. Other local datasets, credentials, saved results and signing choices are intentionally not in Git.

## 1. Try the browser locally

```sh
python3 app.py
```

Open http://127.0.0.1:8000. Choose **Burlington** in Cached road regions, set **5 miles**, and click **Find my loop**. Select an alternative, inspect the map/profile, and download GPX. The first Providence search can take longer while its larger index is built.

This development runner binds to localhost and enables regional imports. It does not apply the shared-password gate. Use the protected Waitress setup below for a tunnel. Basemap tiles require internet even when bundled route calculations work offline. `python3 app.py --demo` is an optional synthetic fixture with internet tiles/imports disabled, not a real-road ride.

## 2. Install the server dependencies

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-hosted.txt
```

This installs Waitress and Pillow (needed for new terrain downloads). On Windows, use `.venv\Scripts\python.exe`; the shell commands below target macOS/Linux. No hosting subscription is required for local serving.

## 3. Create private local configuration once

If `.env.local-beta` already exists, keep it and skip this step. Otherwise copy the safe template and generate a password locally without printing it:

```sh
python3 - <<'PY'
from pathlib import Path
import os
import secrets

template = Path('.env.example').read_text()
contents = template.replace('STAGING_PASSWORD=', 'STAGING_PASSWORD=' + secrets.token_urlsafe(32), 1)
fd = os.open('.env.local-beta', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    output.write(contents)
print('Created .env.local-beta; read the credentials locally when connecting your phone.')
PY
```

The command refuses to overwrite an existing file. `.env.local-beta` is ignored by Git. The template's empty password is intentional: a username without a password makes the protected runner fail rather than serve an unprotected beta. Do not use `.env.example` directly as live configuration.

## 4. Run the protected server

Stop any development runner on port 8000 first, or reuse an already running protected server. In terminal A:

```sh
set -a
source .env.local-beta
set +a
.venv/bin/python serve.py
```

Open http://127.0.0.1:8000 and sign in with the local credentials. This runner disables regional imports by default. With both authentication variables absent, `serve.py` is unauthenticated; keep both set for shared access.

In another terminal, verify the gate before opening a tunnel:

```sh
curl --silent --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:8000/
curl --fail http://127.0.0.1:8000/api/health
```

The first command must return **401**; health should return `{"status": "ok"}` without credentials. If the first returns 200, do not expose that process: use the protected runner and correct environment.

## 5. Connect your phone over temporary HTTPS

With `cloudflared` installed (`brew install cloudflared` on a Homebrew-equipped Mac), run in terminal B:

```sh
cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate --edge-ip-version 4
```

Copy the **current HTTPS URL printed by cloudflared**. In the native app's **Server** tab, enter that URL and the local username/password, then **Connect and save**. For installation/signing, follow [the iPhone guide](IOS.md). The phone can also open the URL in Safari to use the browser interface.

Both server and tunnel must keep running, and the Mac must remain awake and online for new searches. The phone needs internet to reach the tunnel and fetch map tiles. Restarting the tunnel may change the URL; update the phone's Server setting. A temporary tunnel is development access, not permanent hosting. Cloudflare proxies requests and responses, including planned route locations.

Stop each process with Ctrl-C in its terminal when finished. Saved server results remain in `data/routes.sqlite3`; stop the tunnel to remove shared access. No cloud VM or paid hosting is provisioned by these commands.

## Troubleshooting

| Symptom | Action |
|---|---|
| Port already in use | Reuse the existing server or stop it in its terminal. For browser-only development, use `python3 app.py --port 8001`. If changing the Waitress port, update the tunnel target too. |
| Phone cannot connect / tunnel not found | Check both processes, restart the tunnel after sleep/network changes, and save its new HTTPS URL. `localhost` on the phone means the phone itself, not your Mac. |
| Unauthorized | Check the credentials in `.env.local-beta` against the phone's Server tab; never put the password in the URL. |
| Map visible but no route at a place | Maps and route coverage are separate. Select a bundled region or explicitly import roads/terrain using the [regional import guide](ROUTING.md#import-regional-data), then restart if imported via CLI. |
| Regional downloads disabled | Expected for `serve.py`. Import locally with the CLI; do not enable public imports just to fix the phone. |
| No qualifying loop | Move the start inside coverage, shorten the target, or reconsider restrictive filters/tolerance. The planner does not silently relax constraints. |
| Certificate verification fails during imports | Fix the Python installation's CA bundle; on macOS a configured system bundle may be available at `/etc/ssl/cert.pem`. Do not disable TLS verification. |
| Saved browser link expired | Server retention is bounded; regenerate or use a GPX/downloaded iPhone route retained locally. |

For Docker, persistent hosting and backups, see [deployment](DEPLOYMENT.md). For automated checks, see [development](../CONTRIBUTING.md).
