import math
import unittest
import xml.etree.ElementTree as ET
from planner.graph import Graph, Edge, demo, from_osm, eligible, distance, PAVED
from planner.routing import validate, shortest_path, plan, edge_cost, summarize
from planner.export import gpx


def osm(way_tags, node_tags=None):
    nodes = [{'type':'node','id':i,'lat':41.8,'lon':-71.4+i*.001,'tags':(node_tags or {}).get(i,{})} for i in (1,2,3)]
    return {'elements': nodes+[{'type':'way','id':9,'nodes':[1,2,3],'tags':{'highway':'residential',**way_tags}}]}


class RoadImportTests(unittest.TestCase):
    def test_surface_and_access(self):
        for tags in ({'surface':'gravel'},{'access':'private'},{'bicycle':'no'},{'bicycle':'dismount'},{'access:conditional':'no @ (winter)'},{'smoothness':'bad'}):
            self.assertFalse(eligible({'highway':'residential',**tags}))
        self.assertTrue(eligible({'highway':'residential','surface':'asphalt'}))
        self.assertTrue(eligible({'highway':'residential'}))
        self.assertFalse(eligible({'highway':'motorway','bicycle':'yes'}))
        self.assertFalse(eligible({'highway':'footway'}))
    def test_oneway_and_bicycle_exception(self):
        p=validate({})
        g=from_osm(osm({'oneway':'yes'}))
        self.assertEqual(len(shortest_path(g,1,3,p)),2)
        self.assertIsNone(shortest_path(g,3,1,p))
        g=from_osm(osm({'oneway':'yes','oneway:bicycle':'no'}))
        self.assertEqual(len(shortest_path(g,3,1,p)),2)
        g=from_osm(osm({'oneway':'-1'}))
        self.assertIsNone(shortest_path(g,1,3,p))
        self.assertEqual(len(shortest_path(g,3,1,p)),2)
    def test_roundabout_and_barrier(self):
        g=from_osm(osm({'junction':'roundabout'}))
        self.assertIsNone(shortest_path(g,3,1,validate({})))
        g=from_osm(osm({}, {2:{'barrier':'gate'}}))
        self.assertEqual(len(g.nodes),0)
    def test_strict_surface(self):
        g=from_osm(osm({}))
        self.assertIsNone(shortest_path(g,1,3,validate({'strict':True})))
        with self.assertRaises(ValueError): g.nearest((41.8,-71.4),True)
    def test_parallel_edges_preserved(self):
        data=osm({'surface':'asphalt'})
        data['elements'].append({'type':'way','id':10,'nodes':[1,2,3],'tags':{'highway':'secondary','surface':'asphalt'}})
        g=from_osm(data)
        route=shortest_path(g,1,3,validate({'traffic':1}))
        self.assertTrue(all(e.way==9 for e in route))


class RoutingTests(unittest.TestCase):
    def test_preferences_change_path(self):
        g=Graph();g.nodes={1:(0,0),2:(0,.001),3:(.001,.001),4:(0,.002)}
        for u,v,length,road in [(1,2,115,'primary'),(2,4,115,'primary'),(1,3,160,'residential'),(3,4,160,'residential')]:
            g.add(Edge(u,v,length,u*10+v,road,'asphalt'))
        self.assertEqual([e.v for e in shortest_path(g,1,4,validate({'traffic':0,'stops':0}))],[2,4])
        self.assertEqual([e.v for e in shortest_path(g,1,4,validate({'traffic':1,'stops':0}))],[3,4])
        g.stops.add(2)
        self.assertEqual([e.v for e in shortest_path(g,1,4,validate({'traffic':0,'stops':1}))],[3,4])
    def test_hills_and_reuse_have_cost(self):
        g=Graph();g.nodes={1:(0,0),2:(0,.001)};g.elevation={1:0,2:10}
        e=Edge(1,2,100,1,surface='asphalt')
        neutral=edge_cost(g,e,validate({}))
        self.assertGreater(edge_cost(g,e,validate({'hills':'avoid'})),neutral)
        self.assertGreater(edge_cost(g,e,validate({}),{e.key}),neutral)
    def test_loops_closed_distinct_and_in_range(self):
        g=demo()
        for miles in (5,20,30,50,75):
            result=plan(g,validate({'miles':miles}))
            self.assertGreaterEqual(len(result['routes']),2)
            signatures=[]
            for r in result['routes']:
                self.assertEqual(r['coordinates'][0],r['coordinates'][-1])
                self.assertLessEqual(r['distance_error_pct'],30)
                self.assertLessEqual(r['repeated_pct'],20)
                self.assertAlmostEqual(sum(distance(a,b) for a,b in zip(r['coordinates'],r['coordinates'][1:]))/1609.344,r['distance_miles'],delta=.06)
                signatures.append(tuple(r['coordinates']))
            self.assertEqual(len(set(signatures)),len(signatures))
    def test_disconnected_network_and_distant_start(self):
        g=Graph();g.nodes={1:(0,0),2:(0,.001),3:(1,1)};g.add(Edge(1,2,100,1))
        self.assertIsNone(shortest_path(g,1,3,validate({})))
        with self.assertRaises(ValueError): plan(demo(),validate({'lat':0,'lon':0}))
    def test_strict_demo_routes_have_no_unknown_pavement(self):
        for r in plan(demo(),validate({'strict':True}))['routes']:
            self.assertEqual(r['unknown_surface_pct'],0)
    def test_invalid_input(self):
        for p in ({'miles':-1},{'lat':float('nan')},{'lon':float('inf')},{'traffic':2},{'hills':'magic'},{'strict':'false'},{'miles':None}):
            with self.assertRaises(ValueError):validate(p)


class ExportTests(unittest.TestCase):
    def test_valid_gpx_closed_and_escaped(self):
        result=plan(demo(),validate({}))
        r=result['routes'][0];r['name']='Brown & <friends>'
        root=ET.fromstring(gpx(r,result['source']))
        ns={'g':'http://www.topografix.com/GPX/1/1'}
        self.assertEqual(root.attrib['version'],'1.1')
        self.assertIn('DO NOT RIDE',root.find('g:trk/g:name',ns).text)
        self.assertIn('Brown & <friends>',root.find('g:trk/g:name',ns).text)
        pts=root.findall('.//g:trkpt',ns)
        self.assertEqual(len(pts),len(r['coordinates']))
        self.assertEqual(pts[0].attrib,pts[-1].attrib)
        self.assertEqual(len(root.findall('.//g:ele',ns)),len(pts))
    def test_missing_elevation_not_fabricated(self):
        g=from_osm(osm({'surface':'asphalt'}));p=validate({})
        edges=shortest_path(g,1,3,p)+shortest_path(g,3,1,p)
        r=summarize(g,edges,1000,p);r['name']='Test'
        self.assertIsNone(r['ascent_ft'])
        self.assertNotIn(b'<ele>',gpx(r,g.metadata))

if __name__=='__main__':unittest.main()
