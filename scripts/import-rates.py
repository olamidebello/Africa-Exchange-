"""Import an operator-authorized feed. No unlicensed provider scraping."""
import argparse,json,math,sys,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen,Request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import server

def validate(payload):
 if not isinstance(payload,list) or len(payload)>10000:raise ValueError('Expected at most 10000 quote records')
 result=[]
 for r in payload:
  base,quote=r['base'],r['quote'];buy,sell=float(r['buy']),float(r['sell'])
  if not all(isinstance(k,str) and len(k)==3 and k.isascii() and k.isalpha() for k in [base,quote]):raise ValueError('Invalid currency code')
  if not math.isfinite(buy) or not math.isfinite(sell) or not 0<buy<=sell<1e15:raise ValueError('Invalid rate')
  observed=datetime.fromisoformat(r['observed'].replace('Z','+00:00'))
  if observed.tzinfo is None or observed.timestamp()>time.time()+300:raise ValueError('Expected observation timestamp with timezone, not in future')
  if r['market'] not in ['Central bank','FX market','Parallel market','MoneyGram','Western Union']:raise ValueError('Unknown market')
  if not isinstance(r['source'],str) or not r['source']:raise ValueError('Source required')
  result.append((base.upper(),quote.upper(),r['market'],buy,sell,r['source'],observed.astimezone(timezone.utc).isoformat()))
 return result

def ingest(payload):
 rows=validate(payload);server.init();count=0
 with server.db()as c:
  for row in rows:
   if c.execute('SELECT 1 FROM rates WHERE base=? AND quote=? AND market=? AND buy=? AND sell=? AND source=? AND observed=?',row).fetchone():continue
   c.execute('INSERT INTO rates(base,quote,market,buy,sell,source,observed,created) VALUES(?,?,?,?,?,?,?,?)',(*row,time.time()));count+=1
 return count
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('source',help='Local JSON snapshot or authorized HTTPS feed URL');a=parser.parse_args()
 if a.source.startswith('https://'):
  with urlopen(Request(a.source,headers={'User-Agent':'AfricaExchange/1.0'}),timeout=20)as r:
   if not r.url.startswith('https://'):raise ValueError('HTTPS redirect required')
   raw=r.read(2000001)
 else:raw=Path(a.source).read_bytes()
 if len(raw)>2000000:raise ValueError('Feed too large')
 print(json.dumps({'imported':ingest(json.loads(raw))}))
