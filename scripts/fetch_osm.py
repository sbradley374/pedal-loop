#!/usr/bin/env python3
"""Explicit cached OSM import, including supported turn-restriction relations."""
import argparse
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner.regions import download, ENDPOINT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lat',type=float,default=41.8268)
    parser.add_argument('--lon',type=float,default=-71.4025)
    parser.add_argument('--radius',type=int,default=20000)
    parser.add_argument('--endpoint',default=ENDPOINT)
    parser.add_argument('--output',type=Path,default=Path('data/providence.osm.json.gz'))
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args();path=args.output
    if path.exists() and not args.refresh:
        print(f'Using cached {path}; pass --refresh to replace.');return
    path.parent.mkdir(parents=True,exist_ok=True)
    # Build beside the destination; a failed refresh cannot remove the old snapshot.
    with tempfile.TemporaryDirectory(dir=path.parent) as temporary:
        candidate=Path(temporary)/'roads.osm.json.gz'
        download(candidate,args.lat,args.lon,args.radius,endpoint=args.endpoint,progress=lambda text:print(text,flush=True))
        candidate.replace(path)
    print(f'Saved {path}. Refresh terrain with scripts/enrich_elevation.py; old sidecars are rejected by fingerprint.')


if __name__=='__main__':main()
