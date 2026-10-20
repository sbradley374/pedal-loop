#!/usr/bin/env python3
"""Load/cache roads and terrain for any supported start, using the same jobs as the UI."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner.regions import Regions
from planner.routing import validate

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lat',type=float,required=True);p.add_argument('--lon',type=float,required=True)
    p.add_argument('--miles',type=float,default=30);p.add_argument('--label',default='')
    a=p.parse_args();payload=vars(a);prefs=validate(payload)
    manager=Regions(Path(__file__).resolve().parents[1]/'data')
    job=manager.start(payload,prefs);last=None
    while job['status']=='running':
        if job['message']!=last:print(job['message'],flush=True);last=job['message']
        time.sleep(1);job=manager.job(job['id'])
    print(job['message'],flush=True)
    if job['status']=='failed':sys.exit(1)
    print(manager.info(),flush=True)
