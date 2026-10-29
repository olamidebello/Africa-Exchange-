"""Fixed-host TradeNAIRA adapter. Never substitute official for parallel rates."""
import json,math,time,threading
from datetime import datetime,timezone
from urllib.request import Request,urlopen
import server
LOCK=threading.Lock()
URL='https://tradenaira.com/wp-json/tn/v1/rates'
def parse(payload):
 parallel=payload.get('parallel')
 if not isinstance(parallel,dict) or not parallel:raise ValueError('TradeNAIRA parallel rate unavailable; official rate was not used')
 observed=datetime.fromisoformat(payload['updated'].replace('Z','+00:00'))
 if observed.tzinfo is None or not 0<=time.time()-observed.timestamp()<=172800:raise ValueError('TradeNAIRA observation is stale or invalid')
 rows=[]
 for code,value in parallel.items():
  if not isinstance(code,str) or len(code)!=3 or not code.isascii() or not code.isalpha():raise ValueError('Invalid currency')
  rate=float(value)
  if not math.isfinite(rate) or not 0<rate<1e15:raise ValueError('Invalid parallel rate')
  rows.append((code.upper(),'NGN','Parallel market',rate,rate,URL,observed.astimezone(timezone.utc).isoformat()))
 return rows
def sync():
 if not LOCK.acquire(False):return {'ok':False,'status':'Refresh already running'}
 try:
  try:
   with urlopen(Request(URL,headers={'User-Agent':'AfricaExchange/1.0'}),timeout=20) as response:
    if response.url!=URL:raise ValueError('Unexpected provider redirect')
    raw=response.read(200001)
   if len(raw)>200000:raise ValueError('Provider response too large')
   rows=parse(json.loads(raw));count=0
   with server.db() as c:
    for row in rows:
     if not c.execute('SELECT 1 FROM rates WHERE base=? AND quote=? AND market=? AND buy=? AND sell=? AND source=? AND observed=?',row).fetchone():
      c.execute('INSERT INTO rates(base,quote,market,buy,sell,source,observed,created) VALUES(?,?,?,?,?,?,?,?)',(*row,time.time()));count+=1
   status=f'Refreshed {count} parallel reference rates (single reference, no bid/ask spread provided)';ok=True
  except Exception as error:
   status=str(error) if isinstance(error,ValueError) else 'Provider request failed; previous observations retained'
   ok=False
  with server.db() as c:c.execute('UPDATE provider_config SET last_attempt=?,status=? WHERE id=1',(time.time(),status))
  return {'ok':ok,'status':status}
 finally:LOCK.release()
def worker():
 while True:
  try:
   with server.db() as c:config=c.execute('SELECT * FROM provider_config WHERE id=1').fetchone()
   if config['enabled'] and time.time()-config['last_attempt']>=config['interval']:sync()
  except Exception:pass
  time.sleep(30)
