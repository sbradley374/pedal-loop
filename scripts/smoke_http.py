#!/usr/bin/env python3
"""Black-box checks against a running server, using cached regions only."""
import argparse
import base64
import os
import json
from pathlib import Path
import time
import urllib.request
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8001')
    parser.add_argument('--result-file',type=Path,help='Write a result ID for a restart check')
    parser.add_argument('--verify-result',type=Path,help='Verify a previously saved result after restart')
    args=parser.parse_args()
    def request(path,payload=None,method=None):
        data=json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(args.base+path,data=data,method=method,headers={'Content-Type':'application/json','Origin':args.base})
        if os.environ.get('STAGING_USER') and os.environ.get('STAGING_PASSWORD'):
            credentials=f"{os.environ['STAGING_USER']}:{os.environ['STAGING_PASSWORD']}"
            req.add_header('Authorization','Basic '+base64.b64encode(credentials.encode()).decode())
        with urllib.request.urlopen(req,timeout=60) as response:
            body=response.read()
            return json.loads(body) if response.headers.get_content_type()=='application/json' else body
    def finish(job):
        deadline=time.monotonic()+60
        while job['status'] in {'queued','running'}:
            if time.monotonic()>deadline:raise AssertionError('Search timed out')
            time.sleep(.1);job=request('/api/route-jobs/'+job['id'])
        return job
    assert request('/api/health')['status']=='ok'
    if args.verify_result:
        result_id=args.verify_result.read_text().strip()
        result=request('/api/results/'+result_id)
        assert result['id']==result_id and result['routes']
        ET.fromstring(request('/api/gpx/'+result_id+'/0'))
        print('Stored ride and GPX survived restart.',flush=True)
        return
    info=request('/api/info')
    region=next(r for r in info['regions'] if 'Burlington' in r['label'])
    selected=request('/api/info?region_id='+region['id'])
    assert selected['active_region']==region['id']
    assert request('/api/info')['active_region']==info['active_region']
    payload={'mode':'osm','region_id':region['id'],'lat':44.4759,'lon':-73.2121,'miles':5,'tolerance':10}
    started=time.monotonic();job=finish(request('/api/route-jobs',payload))
    assert job['status']=='complete',job
    result=request('/api/results/'+job['result_id'])
    if args.result_file:args.result_file.write_text(result['id']+'\n')
    assert all(r['coordinates'][0]==r['coordinates'][-1] for r in result['routes'])
    for route in result['routes']:
        cues=route['navigation_cues']
        assert cues[0]['distance_m']==0
        assert cues[-1]['coordinate_index']==len(route['coordinates'])-1
        assert all(a['distance_m']<=b['distance_m'] for a,b in zip(cues,cues[1:]))
    xml=request('/api/gpx/'+result['id']+'/0');ET.fromstring(xml)
    assert b'Pedal Loop' in request('/?ride='+result['id'])
    print(f"Hosted search/export: {time.monotonic()-started:.2f}s, {len(result['routes'])} alternatives",flush=True)
    started=time.monotonic();repeat=finish(request('/api/route-jobs',payload))
    assert repeat['cached'] and repeat['result_id']==result['id']
    print(f'Repeated cached request: {time.monotonic()-started:.2f}s',flush=True)
    job=request('/api/route-jobs',{'mode':'osm','region_id':info['active_region'],'miles':74})
    request('/api/route-jobs/'+job['id'],method='DELETE')
    job=finish(job);assert job['status']=='cancelled',job
    print('Cancellation, independent region selection, result retrieval, and GPX passed.',flush=True)


if __name__=='__main__':main()
