import gzip
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from planner.elevation import Terrain, attach, decode_rgb, fingerprint, pixel_coordinates, profile_metrics, sidecar
from planner.graph import from_osm
from planner.regions import Regions, requested_radius
from planner.routing import validate, plan
from test_planner import osm


class ElevationTests(unittest.TestCase):
    def test_encoding_and_projection(self):
        self.assertEqual(decode_rgb((128,0,0)),0)
        self.assertEqual(decode_rgb((127,255,128)),-.5)
        self.assertEqual(pixel_coordinates(0,0,0),(127.5,127.5))
        with self.assertRaises(ValueError):pixel_coordinates(90,0)
    def test_bilinear_interpolation_across_tile_boundary(self):
        terrain=Terrain.__new__(Terrain);terrain.zoom=2
        class Image:
            def __init__(self,x,y):self.x=x;self.y=y
            def getpixel(self,point):
                value=(self.x*256+point[0])*.5+(self.y*256+point[1])*.25+32768
                return int(value//256),int(value%256),int(value%1*256)
        terrain.tile=lambda x,y:Image(x,y)
        with patch('planner.elevation.pixel_coordinates',return_value=(255.5,100.25)):
            self.assertAlmostEqual(terrain.sample(0,0),255.5*.5+100.25*.25)
    def test_climb_profile_and_noise_rejection(self):
        flat=profile_metrics([[i*30,100+(.4 if i%2 else 0)] for i in range(40)])
        self.assertEqual(flat['ascent_ft'],0)
        climb=profile_metrics([[0,0],[300,30],[600,0]])
        self.assertAlmostEqual(climb['ascent_ft'],98,delta=12)
        self.assertAlmostEqual(climb['descent_ft'],98,delta=12)
        self.assertAlmostEqual(climb['max_grade_pct'],10,delta=.1)
        self.assertIsNone(profile_metrics([[0,0],[100,None],[200,0]]))
        self.assertEqual(climb['profile'][0][0],0)
    def test_sidecar_rejects_stale_snapshot(self):
        g=from_osm(osm({}))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'roads.json';path.write_text('first source')
            data={'snapshot_sha256':fingerprint(path),'metadata':{'provider':'test'},'nodes':{'1':10,'2':20,'3':30}}
            with gzip.open(sidecar(path),'wt') as f:json.dump(data,f)
            self.assertTrue(attach(g,path));self.assertEqual(g.elevation[2],20)
            path.write_text('changed source');g.elevation={}
            self.assertFalse(attach(g,path));self.assertEqual(g.elevation,{})
    def test_distance_range(self):
        for miles in (5,10,60,75):self.assertEqual(validate({'miles':miles})['miles'],miles)
        for miles in (4,76):
            with self.assertRaises(ValueError):validate({'miles':miles})
        self.assertEqual(requested_radius(5),6000)
        self.assertEqual(requested_radius(75),30000)


class RegionTests(unittest.TestCase):
    def finish(self,manager,job):
        for _ in range(500):
            job=manager.job(job['id'])
            if job['status']!='running':return job
            time.sleep(.01)
        self.fail('Region job did not finish')
    def downloader(self,path,lat,lon,radius,**kwargs):
        d=osm({'surface':'asphalt'});d['pedal_loop']={'center':[lat,lon],'radius_m':radius,'region_label':kwargs.get('label','Test')}
        with gzip.open(path,'wt') as f:json.dump(d,f)
    def test_cached_switch_without_download_and_portable_id(self):
        with tempfile.TemporaryDirectory() as td:
            manager=Regions(td,downloader=self.downloader,enricher=lambda *args:None)
            job=self.finish(manager,manager.start({'label':'Test city'},validate({})))
            self.assertEqual(job['status'],'complete');self.assertIsNotNone(manager.active)
            region_id=manager.active_id
            def no_download(*args,**kwargs):raise AssertionError('Cached region must not download roads')
            restored=Regions(td,downloader=no_download,enricher=lambda *args:None)
            job=self.finish(restored,restored.start({'region_id':region_id},validate({})))
            self.assertEqual(job['status'],'complete');self.assertEqual(restored.active_id,region_id)
    def test_failed_import_preserves_previous_region(self):
        with tempfile.TemporaryDirectory() as td:
            manager=Regions(td,downloader=self.downloader,enricher=lambda *args:None)
            self.finish(manager,manager.start({},validate({})));previous=manager.active
            def fail(*args,**kwargs):raise OSError('Provider offline')
            manager.downloader=fail
            job=self.finish(manager,manager.start({},validate({'lat':44})))
            self.assertEqual(job['status'],'failed');self.assertIs(manager.active,previous)
    def test_terrain_failure_is_explicit_and_roads_remain_usable(self):
        with tempfile.TemporaryDirectory() as td:
            def no_terrain(*args,**kwargs):raise OSError('Terrain provider offline')
            manager=Regions(td,downloader=self.downloader,enricher=no_terrain)
            job=self.finish(manager,manager.start({},validate({})))
            self.assertEqual(job['status'],'complete');self.assertIn('terrain unavailable',job['warning'])
            self.assertTrue(manager.active.nodes)
    def test_unknown_region_and_disabled_downloads(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):Regions(td).start({'region_id':'bogus'},validate({}))
            with self.assertRaises(ValueError):Regions(td,enabled=False).start({},validate({}))

if __name__=='__main__':unittest.main()
