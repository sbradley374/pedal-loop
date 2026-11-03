import base64
import unittest
from planner.staging import protect


class StagingTests(unittest.TestCase):
    def test_gate_covers_routes_exports_and_static_assets(self):
        calls=[]
        def app(env,start):
            calls.append(env['PATH_INFO']);start('200 OK',[]);return [b'ok']
        gated=protect(app,'tester','test-only-password')
        for path in ['/','/app.js','/api/results/ride','/api/gpx/ride/0','/api/route-jobs']:
            statuses=[]
            gated({'PATH_INFO':path,'REQUEST_METHOD':'GET'},lambda status,headers:statuses.append(status))
            self.assertEqual(statuses,['401 Unauthorized'])
        self.assertFalse(calls)
        token='Basic '+base64.b64encode(b'tester:test-only-password').decode()
        self.assertEqual(gated({'PATH_INFO':'/','REQUEST_METHOD':'GET','HTTP_AUTHORIZATION':token},lambda *args:None),[b'ok'])
        self.assertEqual(gated({'PATH_INFO':'/api/health','REQUEST_METHOD':'GET'},lambda *args:None),[b'ok'])
        self.assertEqual(calls,['/','/api/health'])

    def test_incomplete_configuration_fails_closed(self):
        for user,password in [('user',''),('', 'password'),('a:b','password')]:
            with self.assertRaises(ValueError):protect(None,user,password)
