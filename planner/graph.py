"""Small directed road graph, conservative OSM eligibility, and offline fixture."""
from dataclasses import dataclass
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path

BROWN = (41.8268, -71.4025)
PAVED = {'asphalt', 'paved', 'concrete', 'concrete:lanes', 'concrete:plates', 'paving_stones'}
ROADS = {'primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'living_street', 'cycleway', 'service', 'path', 'footway', 'primary_link', 'secondary_link', 'tertiary_link'}
TRAFFIC = {'primary': 1, 'primary_link': 1, 'secondary': .75, 'secondary_link': .75, 'tertiary': .4, 'tertiary_link': .4, 'unclassified': .3, 'residential': .15, 'service': .1, 'living_street': .05, 'cycleway': 0, 'path': 0, 'footway': 0}


def distance(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def offset(center, east, north):
    return center[0] + north / 111195, center[1] + east / (111195 * math.cos(math.radians(center[0])))


@dataclass(frozen=True)
class Edge:
    u: int
    v: int
    length: float
    way: int
    road: str = 'residential'
    surface: str = ''
    name: str = 'Unnamed road'
    structure: str = ''

    @property
    def key(self):
        # Both directions count as the same segment for overlap penalties.
        return (min(self.u, self.v), max(self.u, self.v), self.way)


class Graph:
    def __init__(self):
        self.nodes = {}
        self.adj = defaultdict(list)
        self.neighbors = defaultdict(set)
        self.elevation = {}
        self.stops = set()
        self.metadata = {}
        self._spatial = {}
        self.compact = None
        self.restriction_nodes = set()
        self.forbidden_turns = defaultdict(set)
        self.only_turns = defaultdict(set)

    def add(self, edge):
        self._spatial.clear()
        self.compact = None
        self.adj[edge.u].append(edge)
        self.neighbors[edge.u].add(edge.v)
        self.neighbors[edge.v].add(edge.u)

    def nearest(self, point, strict=False, avoid_major=False):
        # Local metre grid avoids repeatedly scanning hundreds of thousands of
        # shape nodes. Final candidate comparisons still use great-circle distance.
        cache_key = (strict, avoid_major)
        if cache_key not in self._spatial:
            scale = 111195 * math.cos(math.radians(next(iter(self.nodes.values()))[0])) if self.nodes else 111195
            cells = defaultdict(list)
            candidates = []
            for n, (lat, lon) in self.nodes.items():
                if any((not strict or e.surface in PAVED) and
                       (not avoid_major or e.road not in {'primary','primary_link','secondary','secondary_link'})
                       for e in self.adj[n]):
                    cells[(math.floor(lon*scale/1000), math.floor(lat*111195/1000))].append(n)
                    candidates.append(n)
            self._spatial[cache_key] = (scale, cells, candidates)
        scale, cells, candidates = self._spatial[cache_key]
        if not candidates:
            raise ValueError('No routable roads match the road and pavement filters in this dataset.')
        x, y = point[1]*scale, point[0]*111195
        cx, cy = math.floor(x/1000), math.floor(y/1000)
        for radius in (0, 1, 2, 4, 8, 16, 32):
            nearby = [n for ix in range(cx-radius,cx+radius+1) for iy in range(cy-radius,cy+radius+1) for n in cells.get((ix,iy),())]
            if not nearby: continue
            node = min(nearby, key=lambda n: distance(point,self.nodes[n]))
            boundary = min(x-(cx-radius)*1000, (cx+radius+1)*1000-x, y-(cy-radius)*1000, (cy+radius+1)*1000-y)
            if distance(point,self.nodes[node]) < boundary*.98:
                return node, distance(point,self.nodes[node])
        node = min(candidates, key=lambda n: distance(point,self.nodes[n]))
        return node, distance(point, self.nodes[node])

    def is_junction(self, node):
        return len(self.neighbors[node]) >= 3

    def turn_allowed(self, node, incoming, outgoing):
        if incoming is None:
            return True
        key = (node, incoming)
        return (outgoing not in self.forbidden_turns.get(key, ()) and
                (key not in self.only_turns or outgoing in self.only_turns[key]))


def eligible(tags):
    if tags.get('highway') not in ROADS:
        return False
    bike = tags.get('bicycle')
    if bike in {'no', 'private', 'dismount', 'use_sidepath'}:
        return False
    if tags.get('access') in {'no', 'private', 'customers', 'destination', 'delivery'} and bike not in {'yes', 'designated', 'permissive'}:
        return False
    if tags.get('vehicle') in {'no', 'private'} and bike not in {'yes', 'designated', 'permissive'}:
        return False
    if any(k.endswith(':conditional') for k in tags):
        return False  # No time-dependent access interpreter in this MVP.
    if tags.get('highway') in {'path', 'footway'} and bike not in {'yes', 'designated'}:
        return False
    if tags.get('surface') and tags['surface'] not in PAVED:
        return False
    if tags.get('smoothness') in {'bad', 'very_bad', 'horrible', 'very_horrible', 'impassable'}:
        return False
    if tags.get('service') in {'parking_aisle', 'driveway', 'emergency_access'}:
        return False
    return True


def from_osm(data):
    g = Graph()
    blocked = set()
    for item in data['elements']:
        if item['type'] != 'node': continue
        n, tags = item['id'], item.get('tags', {})
        g.nodes[n] = (item['lat'], item['lon'])
        if tags.get('highway') in {'traffic_signals', 'stop'}: g.stops.add(n)
        if (tags.get('barrier') and tags.get('barrier') not in {'bollard', 'cycle_barrier', 'entrance'} and tags.get('bicycle') not in {'yes', 'designated'}) or tags.get('bicycle') in {'no', 'dismount'}:
            blocked.add(n)
        try:
            ele = float(tags.get('ele', ''))
            if math.isfinite(ele): g.elevation[n] = ele
        except ValueError: pass
    for item in data['elements']:
        if item['type'] != 'way': continue
        tags = item.get('tags', {})
        if not eligible(tags): continue
        direction = tags.get('oneway:bicycle', tags.get('oneway', 'yes' if tags.get('junction') == 'roundabout' else 'no'))
        for u, v in zip(item['nodes'], item['nodes'][1:]):
            if u not in g.nodes or v not in g.nodes or u in blocked or v in blocked or u == v: continue
            fields = dict(length=distance(g.nodes[u], g.nodes[v]), way=item['id'], road=tags['highway'], surface=tags.get('surface', ''), name=tags.get('name', 'Unnamed ' + tags['highway']),
                          structure='bridge' if tags.get('bridge') not in (None, 'no') else 'tunnel' if tags.get('tunnel') not in (None, 'no') else '')
            if direction != '-1': g.add(Edge(u, v, **fields))
            if direction not in {'yes', '1', 'true'}: g.add(Edge(v, u, **fields))
    g.nodes = {n: point for n, point in g.nodes.items() if n in g.neighbors}
    g.metadata = {'source': 'osm', 'label': 'OpenStreetMap road snapshot', 'timestamp': data.get('osm3s', {}).get('timestamp_osm_base', 'Unknown date'), **data.get('pedal_loop', {})}
    supported = unsupported = 0
    for item in data['elements']:
        tags = item.get('tags', {})
        if item['type'] != 'relation' or tags.get('type') != 'restriction':
            continue
        if 'bicycle' in tags.get('except', '').split(';'):
            continue
        restriction = tags.get('restriction:bicycle', tags.get('restriction', ''))
        members = item.get('members', [])
        via = [m['ref'] for m in members if m['role'] == 'via' and m['type'] == 'node']
        before = [m['ref'] for m in members if m['role'] == 'from' and m['type'] == 'way']
        after = [m['ref'] for m in members if m['role'] == 'to' and m['type'] == 'way']
        # Same-way U-turns need direction-aware state, not just way IDs.
        if (len(via) != 1 or len(before) != 1 or len(after) != 1 or
                before == after or any(':conditional' in k for k in tags) or
                not restriction.startswith(('no_', 'only_'))):
            unsupported += 1
            continue
        g.restriction_nodes.add(via[0])
        target = g.only_turns if restriction.startswith('only_') else g.forbidden_turns
        target[(via[0], before[0])].add(after[0])
        supported += 1
    g.metadata['turn_restrictions'] = {'supported': supported, 'unsupported': unsupported,
                                     'included_in_extract': bool(g.metadata.get('restrictions_requested'))}
    return g


def load(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as f: graph = from_osm(json.load(f))
    from .elevation import attach, fingerprint
    attach(graph,path)
    graph.metadata['snapshot_sha256'] = fingerprint(path)
    return graph


def demo():
    """Invented grid: exercises real routing, never represented as rideable roads."""
    g = Graph()
    side, spacing = 49, 1000
    for y in range(side):
        for x in range(side):
            n = y*side+x
            g.nodes[n] = offset(BROWN, (x-24)*spacing, (y-24)*spacing)
            g.elevation[n] = 45 + 30*math.sin(x/4) + 25*math.cos(y/5)
            if x % 5 == 0 and y % 4 == 0: g.stops.add(n)
    for y in range(side):
        for x in range(side):
            u = y*side+x
            for dx, dy in [(1, 0), (0, 1)]:
                if x+dx >= side or y+dy >= side: continue
                v = (y+dy)*side+x+dx
                road = 'tertiary' if (y if dx else x) % 6 == 0 else 'residential'
                surface = '' if (x*17+y*7+dy*3) % 23 == 0 else 'asphalt'
                kw = dict(length=distance(g.nodes[u], g.nodes[v]), way=u*2+dy, road=road, surface=surface, name='Synthetic street')
                g.add(Edge(u,v,**kw)); g.add(Edge(v,u,**kw))
    g.metadata = {'source': 'synthetic', 'label': 'Synthetic demo — not real roads', 'timestamp': None, 'center': BROWN, 'radius_m': 24000}
    return g
