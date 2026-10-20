#!/usr/bin/env python3
"""Offline real-road benchmarks. Fail on broken invariants, report unavailable loops."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner.graph import load, distance
from planner.routing import plan, validate


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    groups=[('Providence','providence.osm.json.gz',41.8268,-71.4025,[
        {'miles':20},{'miles':30},{'miles':50},{'miles':30,'traffic':0},
        {'miles':30,'avoid_major':True},{'miles':10,'tolerance':5}]),
        ('Burlington','region-86dc3c4a39ee1d6e.osm.json.gz',44.4759,-73.2121,[
        {'miles':5},{'miles':10},{'miles':10,'hills':'avoid'},
        {'miles':10,'hills':'seek'},{'miles':10,'avoid_major':True}])]
    report={'created_at':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
            'platform':platform.platform(),'cases':[]}
    for name,file,lat,lon,cases in groups:
        before=time.monotonic();g=load(root/'data'/file);loading=time.monotonic()-before
        for i,case in enumerate(cases):
            prefs=validate({'lat':lat,'lon':lon,**case})
            row={'region':name,'preferences':prefs,'snapshot_sha256':g.metadata['snapshot_sha256'],
                 'graph_load_seconds':round(loading,3),'first_search_in_region':i==0}
            before=time.monotonic()
            try:
                result=plan(g,prefs)
                row['routes']=[]
                for route in result['routes']:
                    coords=route['coordinates'];assert coords[0]==coords[-1]
                    exact=sum(distance(a,b) for a,b in zip(coords,coords[1:]))/1609.344
                    assert abs(exact-route['distance_miles'])<.051
                    assert abs(exact-prefs['miles'])/prefs['miles']<=prefs['tolerance']/100+1e-9
                    assert route['repeated_pct']<=20
                    if prefs['avoid_major']:assert route['major_road_pct']==0
                    if prefs['max_ascent'] is not None:assert route['ascent_ft']<=prefs['max_ascent']
                    row['routes'].append({k:route[k] for k in ('distance_miles','distance_error_pct','major_road_pct','traffic_proxy','ascent_ft','descent_ft','max_grade_pct','unknown_surface_pct','repeated_pct')})
                row['status']='ok';row['search']=result['search']
            except ValueError as exc:
                row.update(status='no_match',error=str(exc))
            row['elapsed_seconds']=round(time.monotonic()-before,3)
            report['cases'].append(row)
            print(f"{name} {case}: {row['status']} in {row['elapsed_seconds']}s",flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    return 0 if all(case['status']=='ok' for case in report['cases']) else 1


if __name__=='__main__':sys.exit(main())
