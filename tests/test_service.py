from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from app import create_app
from planner.graph import from_osm, demo
from planner.routing import plan, validate
from planner.service import ResultStore, PlannerService, Busy
from test_planner import osm


class StoreTests(unittest.TestCase):
    def test_persistence_retention_and_capacity(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'rides.sqlite3'
            store=ResultStore(path,max_results=2)
            store.put('same',{'id':'a','routes':[]})
            self.assertEqual(ResultStore(path).get('same',by_key=True)['id'],'a')
            store.put('b',{'id':'b'});store.put('c',{'id':'c'})
            self.assertIsNone(store.get('a'))
            with closing(sqlite3.connect(path)) as db:
                db.execute('UPDATE results SET created=0 WHERE id=?',('b',));db.commit()
            self.assertIsNone(store.get('b'))
            self.assertIsNotNone(store.get('c'))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.service=PlannerService(self.temp.name,demo=True,workers=1)
    def tearDown(self):
        self.service.close();self.temp.cleanup()
    def finish(self,job):
        deadline=time.monotonic()+10
        while job['status'] in {'queued','running'}:
            if time.monotonic()>deadline:self.fail('Job did not finish')
            time.sleep(.01);job=self.service.job(job['id'])
        return job
    def test_cached_result_skips_planning_and_survives_new_store(self):
        result=self.service.synchronous({'miles':10})
        with patch('planner.service.routing.plan',side_effect=AssertionError('Cache missed')):
            repeated=self.service.synchronous({'miles':10})
        self.assertEqual(result['id'],repeated['id']);self.assertTrue(repeated['cached'])
        self.assertEqual(ResultStore(Path(self.temp.name)/'routes.sqlite3').get(result['id'])['id'],result['id'])
    def test_async_result_and_cache_flag(self):
        job=self.finish(self.service.submit({'miles':10}))
        self.assertEqual(job['status'],'complete')
        self.assertIsNotNone(self.service.store.get(job['result_id']))
        self.assertTrue(self.finish(self.service.submit({'miles':10}))['cached'])
    def test_cancellation_and_bounded_queue(self):
        entered=threading.Event();release=threading.Event()
        def blocked(*args,**kwargs):
            entered.set();release.wait(5)
            if kwargs.get('cancelled',lambda:False)():raise ValueError('Route search cancelled.')
            raise ValueError('Test completion')
        try:
            with patch('planner.service.routing.plan',side_effect=blocked):
                jobs=[self.service.submit({'miles':i}) for i in (5,6,7,8,9)]
                self.assertTrue(entered.wait(2))
                with self.assertRaises(Busy):self.service.submit({'miles':10})
                self.service.job(jobs[0]['id'],cancel=True)
                release.set()
                self.assertEqual(self.finish(jobs[0])['status'],'cancelled')
                for job in jobs[1:]:self.finish(job)
        finally:release.set()
    def test_two_regions_do_not_change_each_other(self):
        manager=self.service.regions
        for name,lon in [('west',-120),('east',-70)]:
            data=osm({'surface':'asphalt'});data['pedal_loop']={'center':[41.8,lon],'region_label':name,'radius_m':9000}
            file=Path(self.temp.name)/f'{name}.json';file.write_text(json.dumps(data))
            graph=from_osm(data);rid=manager.register(file,graph)
            if name=='west':west=rid
            else:east=rid
        west_graph=manager.get(west)
        east_graph=manager.get(east)
        self.assertEqual(west_graph.metadata['region_label'],'west')
        self.assertEqual(east_graph.metadata['region_label'],'east')
        self.assertIs(manager.get(west),west_graph)
        self.assertIsNone(manager.active_id)
    def test_distance_and_ascent_limits_are_hard_constraints(self):
        result=plan(demo(),validate({'miles':20,'tolerance':5}))
        self.assertTrue(all(r['distance_error_pct']<=5 for r in result['routes']))
        limited=plan(demo(),validate({'miles':5,'max_ascent':500}))
        self.assertTrue(all(r['ascent_ft'] is not None and r['ascent_ft']<=500 for r in limited['routes']))
        with self.assertRaisesRegex(ValueError,'climbing limit'):
            plan(demo(),validate({'max_ascent':0}))
    def test_input_types_are_rejected_cleanly(self):
        for payload in ({'hills':[]},{'miles':True},{'mode':[]},{'region_id':[]},{'avoid_major':'yes'},{'max_ascent':-1},{'tolerance':2}):
            with self.assertRaises(ValueError):self.service.validate_request(payload)
    def test_forced_demo_cannot_select_real_regions(self):
        self.assertEqual(self.service.info()['regions'],[])
        with self.assertRaisesRegex(ValueError,'synthetic'):
            self.service.info('some-real-region')


class WSGITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app(demo_only=True,store_path=Path(self.temp.name)/'rides.sqlite3',public_origin='https://rides.example')
    def tearDown(self):
        self.app.service.close();self.temp.cleanup()
    def request(self,path,method='GET',payload=None,origin=None):
        body=json.dumps(payload).encode() if payload is not None else b''
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':io.BytesIO(body),
             'CONTENT_LENGTH':str(len(body)),'HTTP_HOST':'localhost','REMOTE_ADDR':'127.0.0.1'}
        if origin:env['HTTP_ORIGIN']=origin
        response={}
        def start(status,headers):response.update(status=int(status.split()[0]),headers=dict(headers))
        response['body']=b''.join(self.app(env,start))
        return response
    def test_health_and_https_origin(self):
        self.assertEqual(self.request('/api/health')['status'],200)
        result=self.request('/api/route-jobs','POST',{'miles':5},origin='https://rides.example')
        self.assertEqual(result['status'],202)
        self.assertEqual(self.request('/api/route-jobs','POST',{},origin='https://other.example')['status'],403)
    def test_async_http_result_and_export(self):
        result=self.request('/api/route-jobs','POST',{'miles':5})
        job=json.loads(result['body']);deadline=time.monotonic()+10
        while job['status'] in {'queued','running'}:
            self.assertLess(time.monotonic(),deadline);time.sleep(.01)
            job=json.loads(self.request('/api/route-jobs/'+job['id'])['body'])
        self.assertEqual(job['status'],'complete')
        self.assertEqual(self.request('/api/results/'+job['result_id'])['status'],200)
        self.assertEqual(self.request('/api/gpx/'+job['result_id']+'/0')['status'],200)
        self.assertEqual(self.request('/api/route-jobs/missing','DELETE')['status'],404)
    def test_static_containment_and_headers(self):
        self.assertEqual(self.request('/../app.py')['status'],404)
        page=self.request('/')
        self.assertEqual(page['status'],200)
        self.assertIn('frame-ancestors',page['headers']['Content-Security-Policy'])
        self.assertEqual(page['headers']['X-Content-Type-Options'],'nosniff')
    def test_rate_limit(self):
        for _ in range(20):self.request('/api/routes','POST',{'miles':-1})
        self.assertEqual(self.request('/api/routes','POST',{'miles':-1})['status'],429)
