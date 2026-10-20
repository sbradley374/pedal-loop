import random
import unittest
from planner.graph import Graph, Edge, distance, from_osm
from planner.routing import shortest_path, validate, edge_cost, plan
from planner.compact import get_compact


class CompactTests(unittest.TestCase):
    def network(self):
        g=Graph()
        # Shape-heavy grid with one-way sections and parallel alternatives.
        for y in range(4):
            for x in range(4):g.nodes[y*4+x]=(41+y*.008,-71+x*.008)
        next_id=16
        for y in range(4):
            for x in range(4):
                u=y*4+x
                for v in ([u+1] if x<3 else [])+([u+4] if y<3 else []):
                    chain=[u]
                    for fraction in (.25,.5,.75):
                        g.nodes[next_id]=tuple(a+(b-a)*fraction for a,b in zip(g.nodes[u],g.nodes[v]))
                        chain.append(next_id);next_id+=1
                    chain.append(v)
                    for a,b in zip(chain,chain[1:]):
                        length=distance(g.nodes[a],g.nodes[b])
                        g.add(Edge(a,b,length,u*100+v,'residential','asphalt'))
                        if (u+v)%5:g.add(Edge(b,a,length,u*100+v,'residential','asphalt'))
        return g

    def test_compressed_matches_reference_for_interior_endpoints(self):
        g=self.network();randomizer=random.Random(7);prefs=validate({})
        self.assertLess(len(get_compact(g).adj),len(g.nodes)//2)
        for _ in range(35):
            start,goal=randomizer.sample(list(g.nodes),2)
            used={edge.key for edge in g.adj[start]}
            fast=shortest_path(g,start,goal,prefs,used)
            raw=shortest_path(g,start,goal,prefs,used,compact=False)
            self.assertEqual(fast is None,raw is None)
            if fast:
                self.assertEqual(fast[0].u,start);self.assertEqual(fast[-1].v,goal)
                self.assertAlmostEqual(sum(edge_cost(g,e,prefs,used) for e in fast),sum(edge_cost(g,e,prefs,used) for e in raw),places=6)
                self.assertTrue(all(a.v==b.u for a,b in zip(fast,fast[1:])))

    def test_isolated_directed_ring(self):
        g=Graph();g.nodes={1:(0,0),2:(0,.001),3:(.001,.001),4:(.001,0)}
        for u,v in ((1,2),(2,3),(3,4),(4,1)):g.add(Edge(u,v,distance(g.nodes[u],g.nodes[v]),1))
        for start in g.nodes:
            for goal in g.nodes:
                if start==goal:continue
                fast=shortest_path(g,start,goal,validate({}))
                raw=shortest_path(g,start,goal,validate({}),compact=False)
                self.assertEqual(fast,raw)

    def test_major_road_exclusion(self):
        g=self.network()
        u=0;v=15
        g.add(Edge(u,v,distance(g.nodes[u],g.nodes[v]),999,'primary','asphalt'))
        route=shortest_path(g,u,v,validate({'avoid_major':True}))
        self.assertTrue(route)
        self.assertTrue(all(e.road!='primary' for e in route))

    def test_cancellation(self):
        with self.assertRaisesRegex(ValueError,'cancelled'):
            plan(self.network(),validate({'lat':41,'lon':-71,'miles':5}),cancelled=lambda:True)

    def test_filtered_anchor_component_excludes_one_way_traps(self):
        g=Graph();g.nodes={1:(0,0),2:(0,.001),3:(.001,.001),4:(.002,.001)}
        for u,v,road in [(1,2,'residential'),(2,1,'residential'),(2,3,'residential'),
                         (3,4,'primary'),(4,3,'primary')]:
            g.add(Edge(u,v,distance(g.nodes[u],g.nodes[v]),u*10+v,road,'asphalt'))
        self.assertEqual(g.round_trip_nodes(1,avoid_major=True),{1,2})
        with self.assertRaisesRegex(ValueError,'connected roads'):
            plan(g,validate({'lat':0,'lon':0,'miles':10,'avoid_major':True}))


class RestrictionTests(unittest.TestCase):
    def graph(self,restriction='no_right_turn',**tags):
        nodes=[{'type':'node','id':i,'lat':lat,'lon':lon} for i,lat,lon in [(1,0,0),(2,0,.001),(3,0,.002),(4,.001,.001)]]
        ways=[{'type':'way','id':way,'nodes':ends,'tags':{'highway':'residential','surface':'asphalt','oneway':'yes'}} for way,ends in [(10,[1,2]),(20,[2,3]),(30,[2,4]),(40,[4,3])]]
        relation={'type':'relation','id':100,'tags':{'type':'restriction','restriction':restriction,**tags},'members':[{'type':'way','role':'from','ref':10},{'type':'node','role':'via','ref':2},{'type':'way','role':'to','ref':20}]}
        return from_osm({'elements':nodes+ways+[relation],'pedal_loop':{'restrictions_requested':True}})

    def test_no_turn_and_only_turn(self):
        for compact in (True,False):
            g=self.graph()
            route=shortest_path(g,1,3,validate({}),compact=compact)
            self.assertEqual([e.way for e in route],[10,30,40])
            g=self.graph('only_straight_on')
            self.assertEqual([e.way for e in shortest_path(g,1,3,validate({}),compact=compact)],[10,20])
            self.assertIsNone(shortest_path(g,1,4,validate({}),compact=compact))

    def test_restriction_across_anchor_and_loop_closure(self):
        g=self.graph()
        self.assertEqual([e.way for e in shortest_path(g,2,3,validate({}),incoming=10)],[30,40])
        self.assertIsNone(shortest_path(g,1,2,validate({}),final_way=20))

    def test_bicycle_exception_and_conditional_disclosure(self):
        g=self.graph(**{'except':'bicycle'})
        self.assertEqual([e.way for e in shortest_path(g,1,3,validate({}))],[10,20])
        g=self.graph(**{'restriction:conditional':'no_right_turn @ (Mo-Fr)'})
        self.assertEqual(g.metadata['turn_restrictions']['unsupported'],1)
