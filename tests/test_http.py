import json
import threading
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from app import create_server


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=create_server(port=0,demo_only=True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,payload=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin: headers['Origin']=origin
        req=urllib.request.Request(self.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req) as response:return response.status,response.read(),response.headers
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
    def test_info_and_page(self):
        code,body,_=self.request('/api/info');self.assertEqual(code,200)
        self.assertFalse(json.loads(body)['osm_available'])
        code,body,_=self.request('/');self.assertEqual(code,200);self.assertIn(b'Pedal Loop',body)
    def test_round_trip_export(self):
        code,body,_=self.request('/api/routes',{'mode':'synthetic','miles':30})
        self.assertEqual(code,200)
        result=json.loads(body)
        code,xml,headers=self.request('/api/gpx/'+result['id']+'/0')
        self.assertEqual(code,200);self.assertEqual(headers.get_content_type(),'application/gpx+xml')
        self.assertIn('synthetic',headers['Content-Disposition'])
        root=ET.fromstring(xml)
        points=root.findall('.//{http://www.topografix.com/GPX/1/1}trkpt')
        self.assertGreater(len(points),10);self.assertEqual(points[0].attrib,points[-1].attrib)
        self.assertEqual(self.request('/api/gpx/'+result['id']+'/-1')[0],404)
    def test_no_silent_real_data_fallback(self):
        code,body,_=self.request('/api/routes',{'mode':'osm'})
        self.assertEqual(code,400);self.assertIn('No OSM snapshot',json.loads(body)['error'])
    def test_bad_inputs_and_missing_export(self):
        self.assertEqual(self.request('/api/routes',{'miles':80})[0],400)
        self.assertEqual(self.request('/api/routes',[])[0],400)
        self.assertEqual(self.request('/api/gpx/missing/0')[0],404)
        self.assertEqual(self.request('/api/routes',{'lat':0,'lon':0})[0],422)
    def test_region_endpoints_in_demo_mode(self):
        self.assertEqual(self.request('/api/regions/load',{'lat':44.4759,'lon':-73.2121,'miles':10})[0],400)
        self.assertEqual(self.request('/api/regions/jobs/missing')[0],404)
    def test_cross_origin_post_rejected(self):
        self.assertEqual(self.request('/api/routes',{},origin='https://example.com')[0],403)

if __name__=='__main__':unittest.main()
