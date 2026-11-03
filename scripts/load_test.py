#!/usr/bin/env python3
"""Bounded HTTP burst against an explicitly selected development/staging server."""
import argparse
import base64
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--requests', type=int, default=8, choices=range(1, 13))
    parser.add_argument('--region-id')
    parser.add_argument('--lat', type=float, default=41.8268)
    parser.add_argument('--lon', type=float, default=-71.4025)
    parser.add_argument('--miles', type=float, default=20)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base = args.base.rstrip('/')

    def request(path, payload=None, method=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(base+path, data=data, method=method,
                                     headers={'Content-Type':'application/json', 'Origin':base})
        if os.environ.get('STAGING_USER') and os.environ.get('STAGING_PASSWORD'):
            credentials=f"{os.environ['STAGING_USER']}:{os.environ['STAGING_PASSWORD']}"
            req.add_header('Authorization','Basic '+base64.b64encode(credentials.encode()).decode())
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    code, health = request('/api/health')
    if code != 200 or health.get('status') != 'ok':
        raise RuntimeError('Server is not healthy before the test')
    stop = threading.Event()
    probes = []
    def monitor():
        while not stop.is_set():
            start = time.monotonic()
            try:
                code, _ = request('/api/health')
                probes.append({'seconds':round(time.monotonic()-start,3), 'status':code})
            except Exception as exc:
                probes.append({'seconds':round(time.monotonic()-start,3), 'error':str(exc)})
            stop.wait(.25)

    barrier = threading.Barrier(args.requests)
    def search(index):
        payload = {'mode':'osm', 'lat':args.lat, 'lon':args.lon,
                   'miles':args.miles+index*.1, 'traffic':.8, 'tolerance':10}
        if args.region_id: payload['region_id'] = args.region_id
        barrier.wait()
        start = time.monotonic()
        job_id = None
        try:
            code, job = request('/api/route-jobs', payload)
            if code != 202:
                return {'request':index,'status':'rejected' if code==429 else 'error',
                        'http_status':code,'error':job.get('error'),'seconds':round(time.monotonic()-start,3)}
            job_id = job['id']
            while job['status'] in {'queued','running'}:
                if time.monotonic()-start > 180:
                    raise TimeoutError('Search exceeded 180 seconds')
                time.sleep(.25)
                code, job = request('/api/route-jobs/'+job_id)
                if code != 200: raise RuntimeError(f'Job poll returned {code}')
            return {'request':index,'status':job['status'],'cached':job.get('cached',False),
                    'error':job.get('error'),'seconds':round(time.monotonic()-start,3)}
        except Exception as exc:
            if job_id:
                try: request('/api/route-jobs/'+job_id, method='DELETE')
                except Exception: pass
            return {'request':index,'status':'error','error':str(exc),'seconds':round(time.monotonic()-start,3)}

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        with ThreadPoolExecutor(max_workers=args.requests) as pool:
            rows = list(pool.map(search, range(args.requests)))
    finally:
        stop.set(); thread.join(timeout=31)
    report = {'created_at':datetime.now(timezone.utc).isoformat(),
              'base':base,'requests':args.requests,'region_id':args.region_id,
              'cases':rows,'health_probes':probes,
              'note':'One bounded burst, not a production capacity guarantee. Cached results are marked; use a fresh result database for cold-cache measurements.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    counts = {status:sum(row['status']==status for row in rows) for status in sorted({r['status'] for r in rows})}
    print(json.dumps({'outcomes':counts,'max_health_seconds':max(p['seconds'] for p in probes),'report':str(args.output)}))
    return int(any(r['status'] not in {'complete','rejected'} for r in rows) or
               any(p.get('status') != 200 for p in probes) or not counts.get('complete'))


if __name__ == '__main__':
    raise SystemExit(main())
