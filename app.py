#!/usr/bin/env python3
"""Local-only HTTP app. Python 3.9+, no third-party Python dependencies."""
import argparse
from collections import OrderedDict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import uuid
from urllib.parse import urlsplit
from planner import graph, routing, export
from planner.regions import Regions

ROOT = Path(__file__).resolve().parent


def create_server(port=8000, data=None, demo_only=False):
    fixture = graph.demo()
    path = Path(data) if data else ROOT/'data/providence.osm.json.gz'
    regions = Regions(ROOT/'data',path,enabled=not demo_only)
    cache, lock = OrderedDict(), threading.Lock()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kw): super().__init__(*args,directory=str(ROOT/'web'),**kw)
        def send_json(self,value,status=200):
            body = json.dumps(value,allow_nan=False).encode()
            self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/info':
                selected = regions.active or fixture
                return self.send_json({'osm_available': regions.active is not None, 'default_mode': 'osm' if regions.active else 'synthetic', 'source': selected.metadata, 'nodes': len(selected.nodes), 'tile_url': os.environ.get('TILE_URL','https://tile.openstreetmap.org/{z}/{x}/{y}.png'), **regions.info()})
            if path.startswith('/api/regions/jobs/'):
                result = regions.job(path.rsplit('/',1)[-1])
                return self.send_json(result or {'error':'Unknown import job'},200 if result else 404)
            if path.startswith('/api/gpx/'):
                try:
                    _,_,_,rid,index = path.split('/')
                    with lock: result = cache.get(rid)
                    if result is None: raise ValueError()
                    index = int(index)
                    if index < 0: raise ValueError()
                    route = result['routes'][index]
                    body = export.gpx(route,result['source'])
                except (ValueError,IndexError): return self.send_json({'error':'Route expired or not found. Generate it again.'},404)
                self.send_response(200); self.send_header('Content-Type','application/gpx+xml'); self.send_header('Content-Disposition',f'attachment; filename="pedal-loop-{result["source"]["source"]}-{index+1}.gpx"'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
            if path.startswith('/api/'): return self.send_json({'error':'Not found'},404)
            super().do_GET()
        def do_POST(self):
            if self.path not in {'/api/routes','/api/regions/load'}: return self.send_json({'error':'Not found'},404)
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host',''):
                return self.send_json({'error':'Only same-origin requests are supported.'},403)
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 8192: raise ValueError('Request body must be 1–8192 bytes.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload,dict): raise ValueError('Expected a JSON object.')
                prefs = routing.validate(payload)
                if self.path == '/api/regions/load':
                    return self.send_json(regions.start(payload,prefs),202)
                real = regions.active
                mode = payload.get('mode','osm' if real else 'synthetic')
                if mode not in {'osm','synthetic'}: raise ValueError('Unknown data source.')
                if mode == 'osm' and real is None: raise ValueError('No OSM snapshot loaded. Load roads for your start, or select synthetic demo.')
                selected = real if mode == 'osm' else fixture
            except (ValueError,TypeError) as e: return self.send_json({'error':str(e)},400)
            if not lock.acquire(blocking=False): return self.send_json({'error':'A route search is already running. Try again shortly.'},429)
            try:
                result = routing.plan(selected,prefs)
                rid = uuid.uuid4().hex
                result['id'] = rid
                cache[rid] = result
                while len(cache)>20: cache.popitem(last=False)
            except ValueError as e: return self.send_json({'error':str(e)},422)
            finally: lock.release()
            self.send_json(result)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8000)
    p.add_argument('--data',help='Path to an Overpass JSON or .json.gz snapshot')
    p.add_argument('--demo',action='store_true',help='Force invented offline fixture')
    args = p.parse_args()
    server = create_server(args.port,args.data,args.demo)
    print(f'Pedal Loop → http://127.0.0.1:{server.server_port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
