#!/usr/bin/env python3
"""Plan regional coverage or explicitly import selected regions sequentially."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner.regions import Regions, requested_radius
from planner.routing import validate


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,default=root/'data/coverage-plan.json')
    parser.add_argument('--data-dir',type=Path,default=root/'data')
    parser.add_argument('--only',nargs='+',required=True,help='Explicit region IDs; no nationwide bulk download.')
    parser.add_argument('--download',action='store_true',help='Actually request roads and terrain. Otherwise print plan only.')
    args=parser.parse_args()
    catalog={r['id']:r for r in json.loads(args.catalog.read_text())['regions']}
    unknown=set(args.only)-catalog.keys()
    if unknown:parser.error(f'Unknown region IDs: {sorted(unknown)}')
    manager=Regions(args.data_dir) if args.download else None
    failed=False
    for name in dict.fromkeys(args.only):
        region=catalog[name];prefs=validate(region)
        print(f"{region['label']}: {requested_radius(prefs['miles'])/1000:g} km radius",flush=True)
        if not manager:continue
        job=manager.start(region,prefs);last=None
        while job['status']=='running':
            if job['message']!=last:print(job['message'],flush=True);last=job['message']
            time.sleep(1);job=manager.job(job['id'])
        print(job['message'],flush=True)
        if job['status']=='failed':
            failed=True
            break  # No automatic retries or continuing to hammer a busy provider.
    return int(failed)


if __name__=='__main__':sys.exit(main())
