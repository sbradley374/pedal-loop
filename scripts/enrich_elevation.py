#!/usr/bin/env python3
"""Add cached global terrain elevations to an OSM snapshot."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner.graph import load
from planner.elevation import enrich

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',default='data/providence.osm.json.gz')
    p.add_argument('--cache',default='data/terrain-cache')
    a=p.parse_args();g=load(a.data)
    enrich(g,a.data,a.cache,lambda message:print(message,flush=True))
    print(f'Available elevation: {len(g.elevation):,}/{len(g.nodes):,} road nodes')
