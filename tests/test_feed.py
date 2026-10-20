import importlib.util,unittest,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import server
spec=importlib.util.spec_from_file_location('feed',Path(__file__).resolve().parents[1]/'scripts/import-rates.py');feed=importlib.util.module_from_spec(spec);spec.loader.exec_module(feed)
class FeedTests(unittest.TestCase):
 def test_transactional_import_and_deduplication(self):
  prior=server.DB
  try:
   with tempfile.TemporaryDirectory()as directory:
    server.DB=directory+'/db'
    row={'base':'USD','quote':'NGN','market':'FX market','buy':1500,'sell':1510,'source':'test fixture only','observed':'2026-01-01T00:00:00Z'}
    self.assertEqual(feed.ingest([row]),1);self.assertEqual(feed.ingest([row]),0)
    with self.assertRaises(ValueError):feed.ingest([dict(row,observed='2026-01-02T00:00:00Z'),dict(row,buy=-1)])
    with server.db()as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM rates').fetchone()[0],1)
  finally:server.DB=prior
