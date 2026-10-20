#!/usr/bin/env python3
"""Black-box checks against a running server, using cached regions only."""
import argparse
import json
import time
import urllib.request
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8001')
    args=parser.parse_args()
    def request(path,payload=None,method=None):
        data=json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(args.base+path,data=data,method=method,headers={'Content-Type':'application/json','Origin':args.base})
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
    info=request('/api/info')
    region=next(r for r in info['regions'] if 'Burlington' in r['label'])
    selected=request('/api/info?region_id='+region['id'])
    assert selected['active_region']==region['id']
    assert request('/api/info')['active_region']==info['active_region']
    payload={'mode':'osm','region_id':region['id'],'lat':44.4759,'lon':-73.2121,'miles':5,'tolerance':10}
    started=time.monotonic();job=finish(request('/api/route-jobs',payload))
    assert job['status']=='complete',job
    result=request('/api/results/'+job['result_id'])
    assert all(r['coordinates'][0]==r['coordinates'][-1] for r in result['routes'])
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
