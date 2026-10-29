import hashlib,time,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from test_app import Integration
import integrations,server
class ProviderTests(unittest.TestCase):
 def test_missing_parallel_never_uses_official(self):
  with self.assertRaises(ValueError):integrations.parse({'parallel':None,'official':{'USD':1500}})
 def test_reference_and_staleness(self):
  rows=integrations.parse({'parallel':{'USD':1500},'updated':datetime.now(timezone.utc).isoformat()})
  self.assertEqual(rows[0][2:5],('Parallel market',1500,1500))
  with self.assertRaises(ValueError):integrations.parse({'parallel':{'USD':1500},'updated':'2000-01-01T00:00:00Z'})
class AdminTests(Integration):
 def test_key_lifecycle_and_authorization(self):
  self.request('register',{'email':'admin@test.com','password':'long-password-test'})
  cookie=self.request('login',{'email':'admin@test.com','password':'long-password-test'})[2].split(';')[0]
  self.assertEqual(self.request('admin/keys/create',{'label':'test'},cookie)[0],403)
  with server.db() as c:c.execute("UPDATE users SET role='superadmin' WHERE email='admin@test.com'")
  code,result,_=self.request('admin/keys/create',{'label':'test'},cookie)
  self.assertEqual(code,200)
  with server.db() as c:
   key=c.execute('SELECT * FROM api_keys WHERE hash=?',(hashlib.sha256(result['key'].encode()).hexdigest(),)).fetchone()
  self.assertIsNotNone(key)
  self.assertNotIn(result['key'],str(self.request('admin/integrations',cookie=cookie)[1]))
  self.assertEqual(self.request('admin/keys/revoke',{'id':key['id']},cookie)[0],200)
  with server.db() as c:self.assertEqual(c.execute('SELECT revoked FROM api_keys WHERE id=?',(key['id'],)).fetchone()[0],1)
