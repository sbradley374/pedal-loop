"""Deterministic multi-anchor loop search over directed, weighted road segments."""
import heapq
import math
import time
from .compact import get_compact
from .graph import PAVED, TRAFFIC, distance, offset
from .elevation import profile_metrics

MILE = 1609.344


def edge_cost(graph, e, prefs, used=frozenset()):
    if prefs['strict'] and e.surface not in PAVED: return math.inf
    if prefs.get('avoid_major') and e.road in {'primary', 'primary_link', 'secondary', 'secondary_link'}: return math.inf
    weight = 1 + prefs['traffic'] * 3 * TRAFFIC.get(e.road, .5)
    if not e.surface: weight += .35
    if e.surface == 'paving_stones': weight += .4
    if e.u in graph.elevation and e.v in graph.elevation:
        grade = abs(graph.elevation[e.v] - graph.elevation[e.u]) / max(e.length, 1)
        if prefs['hills'] == 'avoid': weight += min(3, 30 * grade)
        if prefs['hills'] == 'seek': weight += max(0, .5 - 15 * grade)
    stop = (150 if e.v in graph.stops else 30 if graph.is_junction(e.v) else 0) * prefs['stops']
    return e.length * (weight + (8 if e.key in used else 0)) + stop


def shortest_path(graph, start, goal, prefs, used=frozenset(), costs=None,
                  incoming=None, final_way=None, cancelled=lambda: False, compact=True):
    if start == goal: return []
    index = get_compact(graph) if compact else None
    outgoing = index.for_search(start, goal) if compact else None
    prepared = index.prepare(graph,prefs,edge_cost) if compact else None
    lower_bound = index.lower_bound(goal,prepared,graph,prefs,edge_cost) if compact else lambda node: 0
    heuristic_cache = {}
    def heuristic(node):
        if node not in heuristic_cache:
            heuristic_cache[node] = max(distance(graph.nodes[node],graph.nodes[goal]),lower_bound(node))
        return heuristic_cache[node]
    arc_costs = costs if costs is not None else {}
    initial = (start, incoming if start in graph.restriction_nodes else None)
    queue = [(distance(graph.nodes[start], graph.nodes[goal]), 0, 0, initial)]
    best, previous, serial = {initial: 0}, {}, 0
    iterations = 0
    while queue:
        iterations += 1
        if iterations % 128 == 1 and cancelled(): raise ValueError('Route search cancelled.')
        _, cost, _, state = heapq.heappop(queue)
        node, from_way = state
        if cost != best[state]: continue
        if node == goal and (final_way is None or graph.turn_allowed(node, from_way, final_way)):
            result = []
            while state != initial:
                state, edges = previous[state]
                result.append(edges)
            return [edge for edges in reversed(result) for edge in edges]
        arcs = outgoing(node) if compact else graph.adj[node]
        for arc in arcs:
            edges = arc.edges if compact else (arc,)
            if not graph.turn_allowed(node, from_way, edges[0].way): continue
            if arc not in arc_costs:
                lengths = {}
                for edge in edges: lengths[edge.key] = lengths.get(edge.key, 0) + edge.length
                base = prepared[0].get(arc) if compact else None
                if base is None: base = sum(edge_cost(graph, edge, prefs) for edge in edges)
                arc_costs[arc] = (base, lengths, lengths.keys())
            base, lengths, keys = arc_costs[arc]
            weight = base + 8 * sum(lengths[k] for k in keys & used)
            end = edges[-1].v
            next_state = (end, edges[-1].way if end in graph.restriction_nodes else None)
            new = cost + weight
            if new < best.get(next_state, math.inf):
                best[next_state] = new
                previous[next_state] = (state, edges)
                serial += 1
                heapq.heappush(queue, (new + heuristic(end), new, serial, next_state))
    return None


def validate(payload):
    def number(name, default, low, high):
        if isinstance(payload.get(name, default), bool): raise ValueError(f'{name} must be a number.')
        try: value = float(payload.get(name, default))
        except (ValueError, TypeError): raise ValueError(f'{name} must be a number.')
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{name} must be between {low} and {high}.')
        return value
    strict = payload.get('strict', False)
    if not isinstance(strict, bool): raise ValueError('strict must be true or false.')
    hills = payload.get('hills', 'neutral')
    if not isinstance(hills, str) or hills not in {'avoid', 'neutral', 'seek'}: raise ValueError('Unknown hill preference.')
    avoid_major = payload.get('avoid_major', False)
    if not isinstance(avoid_major, bool): raise ValueError('avoid_major must be true or false.')
    max_ascent = None if payload.get('max_ascent') is None else number('max_ascent', None, 0, 30000)
    return {'max_ascent': max_ascent, 'avoid_major': avoid_major, 'tolerance': number('tolerance', 10, 3, 30), 'lat': number('lat', 41.8268, -85, 85), 'lon': number('lon', -71.4025, -180, 180), 'miles': number('miles', 30, 5, 75), 'traffic': number('traffic', .8, 0, 1), 'stops': number('stops', .6, 0, 1), 'hills': hills, 'strict': strict}


def summarize(graph, edges, target, prefs):
    length = sum(e.length for e in edges)
    unique = {e.key: e.length for e in edges}
    repeat = 1-sum(unique.values())/length
    unknown = sum(e.length for e in edges if not e.surface)/length
    traffic = sum(e.length*TRAFFIC.get(e.road, .5) for e in edges)/length
    ids = [edges[0].u]+[e.v for e in edges]
    covered, cumulative = 0, 0
    profile = [[0, graph.elevation.get(ids[0])]]
    for e in edges:
        if e.u in graph.elevation and e.v in graph.elevation:
            covered += e.length
        cumulative += e.length
        profile.append([cumulative, graph.elevation.get(e.v)])
    metrics = profile_metrics(profile, closed=ids[0] == ids[-1])
    raw_elevation = [[round(d/MILE,4),y] for d,y in profile] if covered else []
    error = abs(length-target)/target
    score = 6*error + 3*repeat + sum(edge_cost(graph,e,prefs) for e in edges)/length
    return {'distance_miles': round(length/MILE, 1), 'distance_error_pct': round(error*100), 'repeated_pct': round(repeat*100,1), 'unknown_surface_pct': round(unknown*100,1), 'traffic_proxy': round(traffic*100), 'major_road_pct': round(sum(e.length for e in edges if e.road in {'primary','primary_link','secondary','secondary_link'})/length*100,1), 'structure_pct': round(sum(e.length for e in edges if e.structure)/length*100,1), 'junctions': len({n for n in ids if graph.is_junction(n)}), 'mapped_stops': len(set(ids)&graph.stops), 'ascent_ft': metrics['ascent_ft'] if metrics else None, 'descent_ft': metrics['descent_ft'] if metrics else None, 'max_grade_pct': metrics['max_grade_pct'] if metrics else None, 'elevation_profile': metrics['profile'] if metrics else [], 'elevation_coverage_pct': round(covered/length*100), 'elevation': raw_elevation, 'coordinates': [graph.nodes[n] for n in ids], '_keys': unique, '_score': score}


def plan(graph, prefs, cancelled=lambda: False):
    started = time.monotonic()
    start, snap = graph.nearest((prefs['lat'], prefs['lon']), prefs['strict'], prefs.get('avoid_major',False))
    if snap > 1500:
        raise ValueError('Start is more than 1.5 km from a matching road. Choose a point inside the loaded region or import a closer OSM snapshot.')
    target = prefs['miles']*MILE
    tolerance = prefs.get('tolerance', 10)/100
    snap_index = None
    if prefs['strict'] or prefs.get('avoid_major'):
        connected = graph.round_trip_nodes(start,prefs['strict'],prefs.get('avoid_major',False))
        lengths = {e.key:e.length for n in connected for e in graph.adj[n]
                   if e.v in connected and graph.edge_allowed(e,prefs['strict'],prefs.get('avoid_major',False))}
        if sum(lengths.values()) < target*(1-tolerance)*.8:
            raise ValueError(f'Your road filters leave only {sum(lengths.values())/MILE:.1f} miles of connected roads at this start, too little for this loop without excessive repetition. Move the start, shorten the ride, or relax the road filters.')
        snap_index = graph.snap_index(prefs['strict'],prefs.get('avoid_major',False),connected)
    candidates, seen, costs = [], set(), {}
    searched = set()
    best_error = math.inf

    def candidate(bearing, scale):
        nonlocal best_error
        if cancelled(): raise ValueError('Route search cancelled.')
        radius = target/3 * scale
        anchors = [start]
        for angle in (bearing, bearing+60):
            theta = math.radians(angle)
            point = offset(graph.nodes[start], radius*math.cos(theta), radius*math.sin(theta))
            node, error = graph.nearest(point, prefs['strict'], prefs.get('avoid_major',False), index=snap_index)
            if error > radius*.45: return None
            anchors.append(node)
        identity = tuple(anchors)
        if len(set(anchors)) != 3 or identity in searched: return None
        searched.add(identity)
        anchors.append(start)
        route, used = [], set()
        for leg, (u,v) in enumerate(zip(anchors, anchors[1:])):
            path = shortest_path(graph,u,v,prefs,used,costs,
                                 incoming=route[-1].way if route else None,
                                 final_way=route[0].way if leg == 2 else None,
                                 cancelled=cancelled)
            if not path: return None
            route.extend(path); used.update(e.key for e in path)
        length = sum(e.length for e in route)
        key = frozenset(used)
        unique = {e.key:e.length for e in route}
        repeated = 1-sum(unique.values())/length
        error = abs(length-target)/target
        if repeated <= .20:
            best_error = min(best_error, error)
            if error <= tolerance and key not in seen:
                seen.add(key)
                result = summarize(graph,route,target,prefs)
                limit = prefs.get('max_ascent')
                if limit is None or (result['ascent_ft'] is not None and result['ascent_ft'] <= limit):
                    candidates.append(result)
        return length

    # Sample every direction, then refine the radius using measured road distance.
    # Refinement is bounded; tight tolerances never silently fall back to 30%.
    for bearing in range(0,360,45):
        observations = []
        for scale in (.65,.85,1.05):
            length = candidate(bearing,scale)
            if length: observations.append((abs(length-target),scale,length))
        for _ in range(2):
            if not observations: break
            _,scale,length = min(observations)
            if abs(length-target)/target <= min(.025,tolerance): break
            corrected = max(.2,min(1.4,scale*target/length))
            measured = candidate(bearing,corrected)
            if measured is None: break
            observations.append((abs(measured-target),corrected,measured))
    candidates.sort(key=lambda r:r['_score'])
    selected = []
    for candidate_route in candidates:
        keys = candidate_route['_keys']
        if any(sum(v for k,v in keys.items() if k in r['_keys']) / min(sum(keys.values()),sum(r['_keys'].values())) > .75 for r in selected): continue
        selected.append(candidate_route)
        if len(selected) == 3: break
    if not selected:
        nearest = f' Closest eligible candidate was {best_error*100:.1f}% from the target.' if math.isfinite(best_error) else ''
        climb_note = ' The climbing limit requires complete elevation coverage and may exclude candidates.' if prefs.get('max_ascent') is not None else ''
        raise ValueError(f'No suitable loop within ±{tolerance*100:g}% of your distance.{nearest}{climb_note} Try a wider tolerance, another start, or less restrictive road filters.')
    for i,r in enumerate(selected):
        r.pop('_keys'); r.pop('_score')
        r['name'] = ['Best match', 'Alternative 02', 'Alternative 03'][i]
    warnings = []
    center, region_radius = graph.metadata.get('center'), graph.metadata.get('radius_m')
    if center and region_radius and distance(center,graph.nodes[start])+target*.4 > region_radius:
        warnings.append('This distance/start may reach the edge of the loaded region. Candidate choice is limited; load a larger region or shorten the ride.')
    if any(not r['elevation_profile'] for r in selected):
        warnings.append('Incomplete terrain coverage: climbing is unavailable and hill preferences may be unreliable.')
    if any(r['structure_pct'] for r in selected):
        warnings.append('Routes include bridges or tunnels. Ground elevation may differ from riding elevation on these sections.')
    restrictions = graph.metadata.get('turn_restrictions', {})
    if graph.metadata.get('source') == 'osm' and not restrictions.get('included_in_extract'):
        warnings.append('This road snapshot predates turn-restriction imports. Refresh the region to include supported turn restrictions.')
    if restrictions.get('unsupported'):
        warnings.append('Some complex or conditional turn restrictions are not modeled. Check signs and access.')
    return {'routes': selected, 'snapped_start': graph.nodes[start], 'snap_distance_m': round(snap), 'requested_start': [prefs['lat'],prefs['lon']], 'source': graph.metadata, 'preferences': prefs, 'warnings':warnings,
            'search': {'seconds': round(time.monotonic()-started,3), 'candidates_tried':len(searched),
                       'road_nodes':len(graph.nodes), 'search_nodes':len(get_compact(graph).adj)}}
