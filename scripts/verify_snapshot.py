#!/usr/bin/env python3
"""Optional integration checks against the bundled real OSM snapshot."""
import sys
from pathlib import Path
import time
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner.graph import load, distance
from planner.routing import plan, validate
from planner.export import gpx

g=load(Path(__file__).resolve().parents[1]/'data/providence.osm.json.gz')
assert g.metadata['source']=='osm'
print(f'Loaded {len(g.nodes):,} eligible road nodes',flush=True)
for miles in (20,30,50):
    started=time.monotonic();result=plan(g,validate({'miles':miles}))
    assert result['routes']
    for r in result['routes']:
        assert r['coordinates'][0]==r['coordinates'][-1]
        assert r['distance_error_pct']<=30
        assert r['repeated_pct']<=20
        measured=sum(distance(a,b) for a,b in zip(r['coordinates'],r['coordinates'][1:]))/1609.344
        assert abs(measured-r['distance_miles'])<.06
        ET.fromstring(gpx(r,result['source']))
    print(f'{miles} mi target: {[r["distance_miles"] for r in result["routes"]]} in {time.monotonic()-started:.1f}s',flush=True)
