#!/usr/bin/env python3
"""Explicit, cached OSM download. Never called automatically by the web app."""
import argparse
import gzip
import json
from pathlib import Path
import urllib.parse
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lat', type=float, default=41.8268)
    p.add_argument('--lon', type=float, default=-71.4025)
    p.add_argument('--radius', type=int, default=20000)
    p.add_argument('--endpoint', default='https://overpass-api.de/api/interpreter')
    p.add_argument('--output', default='data/providence.osm.json.gz')
    p.add_argument('--refresh', action='store_true')
    a = p.parse_args()
    path = Path(a.output)
    if path.exists() and not a.refresh:
        print(f'Using cached {path}; pass --refresh to replace.'); return
    if not (-85 <= a.lat <= 85 and -180 <= a.lon <= 180 and 1000 <= a.radius <= 30000):
        p.error('Use valid coordinates and a radius between 1,000 and 30,000 metres.')
    query = f'''[out:json][timeout:180];way(around:{a.radius},{a.lat},{a.lon})["highway"~"^(primary|secondary|tertiary|unclassified|residential|living_street|cycleway|service|path|footway)(_link)?$"];(._;>;);out body qt;'''
    request = urllib.request.Request(a.endpoint + '?' + urllib.parse.urlencode({'data': query}), headers={'User-Agent': 'PedalLoop-local-MVP/0.1', 'Accept': 'application/json'})
    print('Downloading one regional road snapshot (may take a few minutes)…', flush=True)
    with urllib.request.urlopen(request, timeout=210) as response:
        data = json.load(response)
    if data.get('remark') or not data.get('elements'):
        raise RuntimeError(f'Incomplete Overpass response: {data.get("remark", "no elements")}')
    data['pedal_loop'] = {'center': [a.lat, a.lon], 'radius_m': a.radius, 'endpoint': a.endpoint}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with gzip.open(temporary, 'wt') as f: json.dump(data, f, separators=(',', ':'))
    temporary.replace(path)
    print(f'Saved {len(data["elements"]):,} elements to {path}')

if __name__ == '__main__': main()
