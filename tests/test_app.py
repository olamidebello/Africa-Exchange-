import unittest,tempfile,threading,json,urllib.request,urllib.error,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import server
class Integration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=cls.tmp.name+'/db';server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.App);cls.url='http://127.0.0.1:'+str(cls.http.server_port);threading.Thread(target=cls.http.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.tmp.cleanup()
 def setUp(self):
  with server.db() as c:
   for table in ["sessions","records","rates","audit","users","tenants"]:c.execute("DELETE FROM "+table)
  server.init();server.ATTEMPTS.clear()
 def request(self,path,data=None,cookie=None):
  req=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**({'Cookie':cookie}if cookie else {})})
  try:
   with urllib.request.urlopen(req)as r:return r.status,json.load(r),r.headers.get('Set-Cookie')
  except urllib.error.HTTPError as e:return e.code,json.load(e),None
 def test_auth_and_isolation(self):
  for email in ['one@test.com','two@test.com']:
   self.assertEqual(self.request('register',{'email':email,'password':'long-password-test'})[0],200)
  a=self.request('login',{'email':'one@test.com','password':'long-password-test'})[2].split(';')[0];b=self.request('login',{'email':'two@test.com','password':'long-password-test'})[2].split(';')[0]
  self.assertEqual(self.request('admin',cookie=a)[0],403)
  self.assertEqual(self.request('records',{'kind':'watchlist','data':{'pair':'USD/NGN'}},a)[0],200)
  self.assertEqual(len(self.request('records',cookie=b)[1]),0)
  with server.db()as c:
   c.execute("INSERT INTO tenants VALUES(2,'Other','other')");c.execute("UPDATE users SET tenant=2 WHERE email='two@test.com'")
  self.request('records',{'kind':'job','data':{'title':'Tenant one job'}},a)
  self.assertEqual(len(self.request('records',cookie=b)[1]),0)
  self.request('logout',{},a);self.assertIsNone(self.request('me',cookie=a)[1])
 def test_unauthorized_and_empty_rates(self):
  self.assertEqual(self.request('records')[0],401);self.assertEqual(self.request('rates')[1],[])
if __name__=='__main__':unittest.main()

class WorkflowTests(Integration):
 def test_work_order_transitions_and_application_validation(self):
  for email in ['owner@workflow.test','applicant@workflow.test']:
   self.request('register',{'email':email,'password':'workflow-password-long'})
  owner=self.request('login',{'email':'owner@workflow.test','password':'workflow-password-long'})[2].split(';')[0]
  applicant=self.request('login',{'email':'applicant@workflow.test','password':'workflow-password-long'})[2].split(';')[0]
  self.request('records',{'kind':'job','data':{'title':'Install router'}},owner)
  job=next(r for r in self.request('records',cookie=owner)[1] if r['kind']=='job' and json.loads(r['data']).get('title')=='Install router')['id']
  self.assertEqual(self.request('records',{'kind':'application','data':{'job':str(job)}},owner)[0],400)
  self.assertEqual(self.request('records',{'kind':'application','data':{'job':str(job)}},applicant)[0],200)
  self.assertEqual(self.request('records',{'kind':'application','data':{'job':str(job)}},applicant)[0],400)
  self.assertEqual(self.request('records/update',{'id':job,'status':'assigned'},applicant)[0],403)
  self.assertEqual(self.request('records/update',{'id':job,'status':'completed'},owner)[0],400)
  for state in ['assigned','in_progress','completed']:
   self.assertEqual(self.request('records/update',{'id':job,'status':state},owner)[0],200)
 def test_alert_evaluation_and_input_shape(self):
  self.request('register',{'email':'alert@workflow.test','password':'alert-password-long'})
  token=self.request('login',{'email':'alert@workflow.test','password':'alert-password-long'})[2].split(';')[0]
  self.assertEqual(self.request('records',{'kind':'alert','data':{'title':'USD/NGN','target':'1500','direction':'above','market':'FX market'}},token)[0],200)
  with server.db() as c:c.execute("INSERT INTO rates(base,quote,market,buy,sell,source,observed,created) VALUES('USD','NGN','FX market',1590,1600,'test fixture','2026-01-01T00:00:00Z',9999999999)")
  self.assertTrue(self.request('alerts',cookie=token)[1][0]['triggered'])
  self.assertEqual(self.request('records',[],token)[0],400)

class PasswordTests(Integration):
 def test_password_change_revokes_session(self):
  self.request('register',{'email':'password@example.com','password':'before-password-long'})
  cookie=self.request('login',{'email':'password@example.com','password':'before-password-long'})[2].split(';')[0]
  self.assertEqual(self.request('password',{'current':'wrong','password':'after-password-long'},cookie)[0],403)
  self.assertEqual(self.request('password',{'current':'before-password-long','password':'after-password-long'},cookie)[0],200)
  self.assertIsNone(self.request('me',cookie=cookie)[1])
  self.assertEqual(self.request('login',{'email':'password@example.com','password':'after-password-long'})[0],200)
