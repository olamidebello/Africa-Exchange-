import importlib.util,unittest,tempfile,json,os
from pathlib import Path
import server
spec=importlib.util.spec_from_file_location('provision',Path(__file__).resolve().parents[1]/'scripts/provision-admin.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ProvisionTests(unittest.TestCase):
 def test_first_admin_provision_is_private_and_repeatable(self):
  prior=server.DB
  try:
   with tempfile.TemporaryDirectory()as d:
    server.DB=d+'/db';path=d+'/credentials.json'
    self.assertTrue(module.provision('owner@example.com',path)['changed'])
    data=json.loads(Path(path).read_text());self.assertEqual(os.stat(path).st_mode&0o777,0o600)
    with server.db() as c:
     user=c.execute("SELECT * FROM users WHERE role='superadmin'").fetchone()
     self.assertEqual(user['hash'],server.password(data['password'],user['salt']))
    self.assertFalse(module.provision('another@example.com',path)['changed'])
    self.assertEqual(json.loads(Path(path).read_text()),data)
  finally:server.DB=prior
