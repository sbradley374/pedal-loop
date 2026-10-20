#!/usr/bin/env python3
"""Pedal Loop WSGI application; stdlib local runner, Waitress hosted runner."""
import argparse
from collections import OrderedDict
from http import HTTPStatus
import json
import mimetypes
import os
from pathlib import Path
from socketserver import ThreadingMixIn
import tempfile
import threading
import time
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server, WSGIServer
from planner import export
from planner.service import PlannerService, Busy

ROOT = Path(__file__).resolve().parent


def create_app(data=None, demo_only=False, data_dir=None, store_path=None, imports=True, public_origin=None):
    directory = Path(data_dir or ROOT/'data')
    service = PlannerService(directory, data or directory/'providence.osm.json.gz',
                             demo=demo_only, imports=imports, store_path=store_path)
    limits, rate_lock = OrderedDict(), threading.Lock()

    def application(environ, start_response):
        method, path = environ['REQUEST_METHOD'], environ.get('PATH_INFO', '/')
        headers = [('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'strict-origin-when-cross-origin'),
                   ('Content-Security-Policy', "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")]

        def respond(value, status=200, content_type='application/json'):
            body = json.dumps(value, allow_nan=False).encode() if content_type == 'application/json' else value
            start_response(f'{status} {HTTPStatus(status).phrase}',
                           headers + [('Content-Type', content_type), ('Content-Length', str(len(body))),
                                      ('Cache-Control', 'no-store' if path.startswith('/api/') else 'no-cache')])
            return [body]

        try:
            if method in {'POST', 'DELETE'}:
                origin = environ.get('HTTP_ORIGIN')
                expected = public_origin or f"{environ.get('wsgi.url_scheme', 'http')}://{environ.get('HTTP_HOST', '')}"
                if origin and origin != expected:
                    return respond({'error': 'Only same-origin requests are supported.'}, 403)
            if method == 'POST':
                key = (environ.get('REMOTE_ADDR', ''), 'import' if path.endswith('/load') else 'route')
                now = time.monotonic()
                with rate_lock:
                    count, since = limits.get(key, (0, now))
                    if now-since > 60: count, since = 0, now
                    limits[key] = (count+1, since)
                    limits.move_to_end(key)
                    while len(limits) > 10000: limits.popitem(last=False)
                if count >= (2 if key[1] == 'import' else 20):
                    headers.append(('Retry-After', '60'))
                    return respond({'error': 'Too many requests. Try again in a minute.'}, 429)
                size = int(environ.get('CONTENT_LENGTH') or 0)
                if not 0 < size <= 8192: raise ValueError('Request body must be 1–8192 bytes.')
                payload = json.loads(environ['wsgi.input'].read(size))
                if not isinstance(payload, dict): raise ValueError('Expected a JSON object.')
                if path == '/api/regions/load':
                    if not service.imports_enabled:
                        return respond({'error': 'Regional downloads are disabled on this server.'}, 400)
                    return respond(service.regions.start(payload, service.validate_request({**payload, 'mode':'synthetic'}), activate=False), 202)
                if path in {'/api/routes', '/api/route-jobs'}:
                    service.validate_request(payload)
                    if path == '/api/route-jobs': return respond(service.submit(payload), 202)
                    try: return respond(service.synchronous(payload))
                    except Busy: raise
                    except ValueError as exc: return respond({'error': str(exc)}, 422)
            if path.startswith('/api/route-jobs/') and method in {'GET', 'DELETE'}:
                result = service.job(path.rsplit('/',1)[-1], cancel=method == 'DELETE')
                return respond(result or {'error':'Unknown search job.'}, 200 if result else 404)
            if method == 'GET':
                if path == '/api/health': return respond({'status': 'ok'})
                if path == '/api/info':
                    rid = parse_qs(environ.get('QUERY_STRING','')).get('region_id',[None])[0]
                    return respond({**service.info(rid), 'tile_url': os.environ.get('TILE_URL','https://tile.openstreetmap.org/{z}/{x}/{y}.png')})
                if path.startswith('/api/regions/jobs/'):
                    result = service.regions.job(path.rsplit('/',1)[-1])
                    return respond(result or {'error':'Unknown import job'}, 200 if result else 404)
                if path.startswith('/api/results/'):
                    result = service.store.get(path.rsplit('/',1)[-1])
                    return respond(result or {'error':'Route expired or not found.'}, 200 if result else 404)
                if path.startswith('/api/gpx/'):
                    try:
                        _, _, _, rid, index = path.split('/')
                        result = service.store.get(rid)
                        index = int(index)
                        if result is None or index < 0: raise ValueError()
                        route = result['routes'][index]
                    except (ValueError, IndexError):
                        return respond({'error':'Route expired or not found. Generate it again.'},404)
                    headers.append(('Content-Disposition',f'attachment; filename="pedal-loop-{result["source"]["source"]}-{index+1}.gpx"'))
                    return respond(export.gpx(route,result['source']), content_type='application/gpx+xml')
                if not path.startswith('/api/'):
                    target = (ROOT/'web'/('index.html' if path == '/' else path.lstrip('/'))).resolve()
                    if ROOT/'web' in target.parents and target.is_file():
                        return respond(target.read_bytes(), content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            return respond({'error':'Not found'},404)
        except Busy as exc:
            headers.append(('Retry-After','5'))
            return respond({'error':str(exc)},429)
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            return respond({'error':str(exc)},400)
        except Exception:
            import logging
            logging.exception('Request failed')
            return respond({'error':'The server could not complete this request.'},500)

    application.service = service
    return application


def create_server(port=8000, data=None, demo_only=False):
    temporary = tempfile.TemporaryDirectory() if demo_only else None
    application = create_app(data, demo_only, store_path=Path(temporary.name)/'routes.sqlite3' if temporary else None)

    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = True
        def server_close(self):
            super().server_close()
            application.service.close()
            if temporary: temporary.cleanup()

    return make_server('127.0.0.1', port, application, server_class=Server)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data')
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    server = create_server(args.port, args.data, args.demo)
    print(f'Pedal Loop → http://127.0.0.1:{server.server_port}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
