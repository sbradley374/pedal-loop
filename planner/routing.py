"""Deterministic multi-anchor loop search over directed, weighted road segments."""
import heapq
import math
from .graph import PAVED, TRAFFIC, distance, offset
from .elevation import profile_metrics

MILE = 1609.344


def edge_cost(graph, e, prefs, used=frozenset()):
    if prefs['strict'] and e.surface not in PAVED: return math.inf
    weight = 1 + prefs['traffic'] * 3 * TRAFFIC.get(e.road, .5)
    if not e.surface: weight += .35
    if e.surface == 'paving_stones': weight += .4
    if e.u in graph.elevation and e.v in graph.elevation:
        grade = abs(graph.elevation[e.v] - graph.elevation[e.u]) / max(e.length, 1)
        if prefs['hills'] == 'avoid': weight += min(3, 30 * grade)
        if prefs['hills'] == 'seek': weight += max(0, .5 - 15 * grade)
    stop = (150 if e.v in graph.stops else 30 if graph.is_junction(e.v) else 0) * prefs['stops']
    return e.length * (weight + (8 if e.key in used else 0)) + stop


def shortest_path(graph, start, goal, prefs, used=frozenset(), costs=None):
    if start == goal: return []
    queue = [(distance(graph.nodes[start], graph.nodes[goal]), 0, start)]
    best, previous = {start: 0}, {}
    while queue:
        _, cost, node = heapq.heappop(queue)
        if cost != best[node]: continue
        if node == goal:
            result = []
            while node != start:
                e = previous[node]; result.append(e); node = e.u
            return result[::-1]
        for e in graph.adj[node]:
            if costs is None:
                weight = edge_cost(graph,e,prefs,used)
            else:
                key = id(e)
                if key not in costs: costs[key] = edge_cost(graph,e,prefs)
                weight = costs[key] + (8*e.length if e.key in used else 0)
            new = cost + weight
            if new < best.get(e.v, math.inf):
                best[e.v] = new; previous[e.v] = e
                heapq.heappush(queue, (new + distance(graph.nodes[e.v], graph.nodes[goal]), new, e.v))
    return None


def validate(payload):
    def number(name, default, low, high):
        try: value = float(payload.get(name, default))
        except (ValueError, TypeError): raise ValueError(f'{name} must be a number.')
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{name} must be between {low} and {high}.')
        return value
    strict = payload.get('strict', False)
    if not isinstance(strict, bool): raise ValueError('strict must be true or false.')
    hills = payload.get('hills', 'neutral')
    if hills not in {'avoid', 'neutral', 'seek'}: raise ValueError('Unknown hill preference.')
    return {'lat': number('lat', 41.8268, -85, 85), 'lon': number('lon', -71.4025, -180, 180), 'miles': number('miles', 30, 5, 75), 'traffic': number('traffic', .8, 0, 1), 'stops': number('stops', .6, 0, 1), 'hills': hills, 'strict': strict}


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
    metrics = profile_metrics(profile)
    raw_elevation = [[round(d/MILE,4),y] for d,y in profile] if covered else []
    error = abs(length-target)/target
    score = 6*error + 3*repeat + sum(edge_cost(graph,e,prefs) for e in edges)/length
    return {'distance_miles': round(length/MILE, 1), 'distance_error_pct': round(error*100), 'repeated_pct': round(repeat*100,1), 'unknown_surface_pct': round(unknown*100,1), 'traffic_proxy': round(traffic*100), 'junctions': len({n for n in ids if graph.is_junction(n)}), 'mapped_stops': len(set(ids)&graph.stops), 'ascent_ft': metrics['ascent_ft'] if metrics else None, 'descent_ft': metrics['descent_ft'] if metrics else None, 'max_grade_pct': metrics['max_grade_pct'] if metrics else None, 'elevation_profile': metrics['profile'] if metrics else [], 'elevation_coverage_pct': round(covered/length*100), 'elevation': raw_elevation, 'coordinates': [graph.nodes[n] for n in ids], '_keys': unique, '_score': score}


def plan(graph, prefs):
    start, snap = graph.nearest((prefs['lat'], prefs['lon']), prefs['strict'])
    if snap > 1500:
        raise ValueError('Start is more than 1.5 km from a matching road. Choose a point inside the loaded region or import a closer OSM snapshot.')
    target = prefs['miles']*MILE
    candidates, seen, costs = [], set(), {}
    # Equilateral-ish anchor triangles. Penalties discourage returning on the same road.
    for scale in (.72, .91, 1.1):
        radius = target/3 * scale
        for bearing in range(0, 360, 45):
            anchors = [start]
            for angle in (bearing, bearing+60):
                theta = math.radians(angle)
                point = offset(graph.nodes[start], radius*math.cos(theta), radius*math.sin(theta))
                node, error = graph.nearest(point, prefs['strict'])
                if error > radius*.45: break
                anchors.append(node)
            if len(anchors) != 3 or len(set(anchors)) != 3: continue
            anchors.append(start)
            route, used = [], set()
            for u,v in zip(anchors, anchors[1:]):
                path = shortest_path(graph,u,v,prefs,used,costs)
                if not path: break
                route.extend(path); used.update(e.key for e in path)
            else:
                key = frozenset(used)
                if key in seen: continue
                seen.add(key)
                result = summarize(graph,route,target,prefs)
                exact_length = sum(e.length for e in route)
                exact_repeated = 1-sum(result['_keys'].values())/exact_length
                if exact_repeated <= .20 and abs(exact_length-target)/target <= .30:
                    candidates.append(result)
    candidates.sort(key=lambda r: r['_score'])
    selected = []
    for candidate in candidates:
        keys = candidate['_keys']
        if any(sum(v for k,v in keys.items() if k in r['_keys']) / min(sum(keys.values()),sum(r['_keys'].values())) > .75 for r in selected): continue
        selected.append(candidate)
        if len(selected) == 3: break
    if not selected:
        raise ValueError('No suitable loop found with these settings. Try another start, a different distance, or allow untagged pavement. No fallback route was invented.')
    for i,r in enumerate(selected):
        r.pop('_keys'); r.pop('_score')
        r['name'] = ['Best match', 'Alternative 02', 'Alternative 03'][i]
    warnings = []
    center, region_radius = graph.metadata.get('center'), graph.metadata.get('radius_m')
    if center and region_radius and distance(center,graph.nodes[start])+target*.4 > region_radius:
        warnings.append('This distance/start may reach the edge of the loaded region. Candidate choice is limited; load a larger region or shorten the ride.')
    if prefs['hills'] != 'neutral' and any(not r['elevation_profile'] for r in selected):
        warnings.append('Incomplete terrain coverage: hill preferences cannot reliably rank all candidates.')
    return {'routes': selected, 'snapped_start': graph.nodes[start], 'snap_distance_m': round(snap), 'requested_start': [prefs['lat'],prefs['lon']], 'source': graph.metadata, 'preferences': prefs, 'warnings':warnings}
