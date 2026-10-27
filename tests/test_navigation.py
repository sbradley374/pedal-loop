import unittest
from planner.graph import Graph,Edge
from planner.navigation import cues


class CueTests(unittest.TestCase):
    def test_named_turn_and_finish_follow_edge_order(self):
        graph=Graph();graph.nodes={1:(40,-105),2:(40.001,-105),3:(40.001,-104.999),4:(40.002,-105)}
        first=Edge(1,2,111,1,name='North Street')
        second=Edge(2,3,85,2,name='East Street')
        for e in [first,second,Edge(2,4,111,3)]:graph.add(e)
        result=cues(graph,[first,second])
        self.assertEqual(result[1]['instruction'],'Turn right onto East Street')
        self.assertEqual(result[1]['distance_m'],111)
        self.assertEqual(result[1]['coordinate_index'],1)
        self.assertEqual(result[-1]['distance_m'],196)
    def test_shape_points_on_same_road_do_not_invent_maneuvers(self):
        graph=Graph();graph.nodes={1:(40,-105),2:(40.001,-105),3:(40.001,-104.999)}
        edges=[Edge(1,2,111,1,name='Curved Road'),Edge(2,3,85,1,name='Curved Road')]
        for e in edges:graph.add(e)
        self.assertEqual(len(cues(graph,edges)),2)
