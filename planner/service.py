"""Bounded background searches and durable, unlisted route results."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from . import graph, routing
from .regions import Regions

CACHE_VERSION = 4  # Bump when routing, filtering, or elevation math changes.


class Busy(ValueError):
    pass


class ResultStore:
    def __init__(self, path, max_results=500, days=30):
        self.path = str(path)
        self.max_results = max_results
        self.seconds = days * 86400
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS results (id TEXT PRIMARY KEY, cache_key TEXT, created REAL, body TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS results_cache ON results(cache_key)')
            db.commit()

    def get(self, value, by_key=False):
        field = 'cache_key' if by_key else 'id'
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute(f'SELECT body FROM results WHERE {field}=? AND created>? ORDER BY created DESC LIMIT 1',
                             (value, time.time()-self.seconds)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key, result):
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.execute('INSERT INTO results VALUES (?,?,?,?)',
                       (result['id'], key, time.time(), json.dumps(result, allow_nan=False)))
            db.execute('DELETE FROM results WHERE created<?', (time.time()-self.seconds,))
            db.execute('DELETE FROM results WHERE id IN (SELECT id FROM results ORDER BY created DESC LIMIT -1 OFFSET ?)',
                       (self.max_results,))
            db.commit()


class PlannerService:
    def __init__(self, data_dir, initial=None, demo=False, imports=True, workers=2, store_path=None):
        self.regions = Regions(data_dir, initial, enabled=not demo)
        self.imports_enabled = imports and not demo
        self.fixture = graph.demo()
        self.store = ResultStore(store_path or Path(data_dir)/'routes.sqlite3')
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='route')
        self.slots = threading.BoundedSemaphore(workers+4)
        self.lock = threading.Lock()
        self.jobs = OrderedDict()
        self.demo = demo

    def info(self, region_id=None):
        if self.demo and region_id is not None:
            raise ValueError('Region selection is disabled in forced synthetic mode.')
        selected = None if self.demo else self.regions.get(region_id)
        catalog = self.regions.info()
        if self.demo: catalog['regions'] = []
        catalog['active_region'] = region_id or self.regions.active_id
        catalog['region_import_enabled'] = self.imports_enabled
        return {'osm_available': selected is not None, 'default_mode': 'osm' if selected else 'synthetic',
                'source': (selected or self.fixture).metadata, 'nodes': len((selected or self.fixture).nodes),
                'result_retention_days': 30, **catalog}

    def validate_request(self, payload):
        prefs = routing.validate(payload)
        mode = payload.get('mode', 'synthetic' if self.demo else 'osm')
        if not isinstance(mode, str) or mode not in {'osm', 'synthetic'}:
            raise ValueError('Unknown data source.')
        rid = payload.get('region_id')
        if rid is not None and (not isinstance(rid, str) or rid not in self.regions.catalog):
            raise ValueError('Unknown cached region.')
        if mode == 'osm' and (self.demo or (rid is None and self.regions.active_id is None)):
            raise ValueError('No OSM snapshot loaded. Load roads for your start, or select synthetic demo.')
        return prefs

    def calculate(self, payload, cancelled=lambda: False):
        prefs = self.validate_request(payload)
        mode = payload.get('mode', 'synthetic' if self.demo else 'osm')
        selected = self.regions.get(payload.get('region_id')) if mode == 'osm' else self.fixture
        if cancelled(): raise ValueError('Route search cancelled.')
        identity = {'version': CACHE_VERSION, 'source': selected.metadata, 'preferences': prefs}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        cached = self.store.get(key, by_key=True)
        if cached:
            cached['cached'] = True
            return cached
        result = routing.plan(selected, prefs, cancelled=cancelled)
        if cancelled(): raise ValueError('Route search cancelled.')
        result.update(id=uuid.uuid4().hex, cached=False, region_id=payload.get('region_id') or self.regions.active_id)
        self.store.put(key, result)
        return result

    def synchronous(self, payload):
        if not self.slots.acquire(blocking=False):
            raise Busy('Search queue is full. Try again shortly.')
        try:
            return self.pool.submit(self.calculate, payload).result()
        finally:
            self.slots.release()

    def submit(self, payload):
        self.validate_request(payload)
        if not self.slots.acquire(blocking=False):
            raise Busy('Search queue is full. Try again shortly.')
        job_id = uuid.uuid4().hex
        event = threading.Event()
        with self.lock:
            self.jobs[job_id] = {'id': job_id, 'status': 'queued', '_cancel': event}
            for old_id in list(self.jobs):
                if len(self.jobs) <= 100: break
                if self.jobs[old_id]['status'] in {'complete', 'failed', 'cancelled'}:
                    del self.jobs[old_id]

        def work():
            started = time.monotonic()
            try:
                with self.lock: self.jobs[job_id]['status'] = 'running'
                result = self.calculate(payload, event.is_set)
                with self.lock:
                    self.jobs[job_id].update(status='cancelled' if event.is_set() else 'complete',
                                            result_id=result['id'], cached=result.get('cached',False))
            except Exception as exc:
                if not isinstance(exc, ValueError):
                    logging.getLogger(__name__).exception('Unexpected route search failure')
                with self.lock:
                    self.jobs[job_id].update(status='cancelled' if event.is_set() else 'failed',
                                            error=str(exc) if isinstance(exc, ValueError) else 'Search failed. Please try again.')
            finally:
                with self.lock:
                    outcome = self.jobs[job_id]['status']
                logging.getLogger(__name__).info('route_job status=%s elapsed_seconds=%.3f', outcome, time.monotonic()-started)
                self.slots.release()
        self.pool.submit(work)
        return self.job(job_id)

    def job(self, job_id, cancel=False):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job: return None
            if cancel and job['status'] in {'queued', 'running'}:
                job['_cancel'].set()
            return {k:v for k,v in job.items() if not k.startswith('_')}

    def close(self):
        with self.lock:
            for job in self.jobs.values(): job['_cancel'].set()
        self.pool.shutdown(wait=True)
