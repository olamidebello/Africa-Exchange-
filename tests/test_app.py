import unittest,tempfile,threading,json,urllib.request,urllib.error,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import server
class Integration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=cls.tmp.name+'/db';server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.App);cls.url='http://127.0.0.1:'+str(cls.http.server_port);threading.Thread(target=cls.http.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.tmp.cleanup()
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
