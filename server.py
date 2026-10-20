import os,sqlite3,json,secrets,hashlib,hmac,time,argparse,math
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
ATTEMPTS={}
ROOT=Path(__file__).parent; DB=os.getenv('DATABASE_PATH',str(ROOT/'data/exchange.db'))
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def password(p,s): return hashlib.scrypt(p.encode(),salt=s.encode(),n=16384,r=8,p=1).hex()
def init():
 Path(DB).parent.mkdir(parents=True,exist_ok=True)
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL); CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,tenant INTEGER REFERENCES tenants(id),email TEXT UNIQUE,salt TEXT,hash TEXT,role TEXT); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user INTEGER REFERENCES users(id),expires REAL); CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,tenant INTEGER REFERENCES tenants(id),user INTEGER REFERENCES users(id),kind TEXT,data TEXT,created REAL); CREATE TABLE IF NOT EXISTS rates(id INTEGER PRIMARY KEY,base TEXT,quote TEXT,market TEXT,buy REAL,sell REAL,source TEXT,observed TEXT,created REAL); CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user INTEGER,action TEXT,created REAL);''')
  c.execute("INSERT OR IGNORE INTO tenants VALUES(1,'Africa Exchange','africa-exchange')")
class App(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'static'),**kw)
 def log_message(self,*a): pass
 def reply(self,data,status=200):
  b=json.dumps(data).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(b)
 def identity(self,c):
  cookie=self.headers.get('Cookie',''); token=next((p.strip()[3:] for p in cookie.split(';') if p.strip().startswith('ax=')),'')
  return c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user=u.id WHERE s.token=? AND s.expires>?',(token,time.time())).fetchone()
 def do_GET(self):
  path=self.path.split('?')[0]
  if not path.startswith('/api/'):
   if path not in ['/app.apk','/logo.png','/app.js','/style.css','/manifest.json','/sw.js']: self.path='/index.html'
   return super().do_GET()
  with db() as c:
   u=self.identity(c)
   if path=='/api/health': return self.reply({'ok':True})
   if path=='/api/rates': return self.reply([dict(r) for r in c.execute('SELECT * FROM rates ORDER BY created DESC LIMIT 500')])
   if path=='/api/me': return self.reply(({'id':u['id'],'email':u['email'],'role':u['role'],'tenant':u['tenant']} if u else None))
   if not u:return self.reply({'error':'Sign in required'},401)
   if path=='/api/alerts':
    results=[]
    for record in c.execute("SELECT * FROM records WHERE tenant=? AND user=? AND kind='alert'",(u['tenant'],u['id'])):
     a=json.loads(record['data']); pair=a.get('title','').upper().split('/')
     if len(pair)!=2:continue
     rate=c.execute('SELECT * FROM rates WHERE base=? AND quote=? AND market=? ORDER BY created DESC LIMIT 1',(pair[0],pair[1],a.get('market','FX market'))).fetchone()
     if not rate:continue
     target=float(a.get('target',0)); triggered=rate['sell']>=target if a.get('direction')=='above' else rate['sell']<=target
     results.append({'id':record['id'],'pair':a['title'],'triggered':triggered,'target':target,'current':rate['sell'],'observed':rate['observed'],'source':rate['source']})
    return self.reply(results)
   if path=='/api/records':return self.reply([dict(r) for r in c.execute('SELECT * FROM records WHERE tenant=? ORDER BY id DESC',(u['tenant'],)) if r['user']==u['id'] or u['role'] in ['admin','superadmin'] or r['kind']=='job'])
   if path=='/api/admin':
    if u['role']!='superadmin':return self.reply({'error':'Forbidden'},403)
    return self.reply({'tenants':[dict(r) for r in c.execute('SELECT * FROM tenants')],'users':[dict(r) for r in c.execute('SELECT id,email,role,tenant FROM users')],'audit':[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]})
  self.reply({'error':'Not found'},404)
 def do_POST(self):
  origin=self.headers.get('Origin')
  if origin and origin.rstrip('/')!=os.getenv('PUBLIC_URL','http://'+self.headers.get('Host','')):return self.reply({'error':'Origin rejected'},403)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length<0 or length>32768: return self.reply({'error':'Request too large'},413)
   d=json.loads(self.rfile.read(length)); path=self.path
   if not isinstance(d,dict):raise ValueError('JSON object required')
   with db() as c:
    u=self.identity(c)
    if path=='/api/register':
     if not isinstance(d.get('password'),str) or not 12<=len(d['password'])<=256: return self.reply({'error':'Use at least 12 password characters'},400)
     email=d['email'].strip().lower()
     if '@' not in email or len(email)>254:raise ValueError('Valid email required')
     salt=secrets.token_hex(16); c.execute('INSERT INTO users(tenant,email,salt,hash,role) VALUES(1,?,?,?,?)',(email,salt,password(d['password'],salt),'user'));return self.reply({'ok':True})
    if path=='/api/login':
     key=hashlib.sha256(str(d.get('email','')).lower().encode()).hexdigest(); now=time.time(); recent=[t for t in ATTEMPTS.get(key,[]) if now-t<300]; ATTEMPTS[key]=recent
     if len(recent)>=15:return self.reply({'error':'Too many attempts. Try again in five minutes.'},429)
     recent.append(now)
     account=c.execute('SELECT * FROM users WHERE email=?',(d.get('email','').lower(),)).fetchone()
     if not account or not hmac.compare_digest(account['hash'],password(d.get('password',''),account['salt'])):return self.reply({'error':'Invalid credentials'},401)
     token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(token,account['id'],time.time()+43200)); c.commit()
     b=b'{"ok":true}';self.send_response(200);self.send_header('Set-Cookie','ax='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+('; Secure' if os.getenv('PUBLIC_URL','').startswith('https:') else ''));self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
    if not u:return self.reply({'error':'Sign in required'},401)
    if path=='/api/password':
     old=d.get('current','');new=d.get('password','')
     if not isinstance(new,str) or not 16<=len(new)<=256:raise ValueError('Use 16 to 256 characters')
     if not isinstance(old,str) or not hmac.compare_digest(u['hash'],password(old,u['salt'])):return self.reply({'error':'Current password is incorrect'},403)
     salt=secrets.token_hex(16);c.execute('UPDATE users SET salt=?,hash=? WHERE id=?',(salt,password(new,salt),u['id']))
     c.execute('DELETE FROM sessions WHERE user=?',(u['id'],))
     c.execute('INSERT INTO audit(user,action,created) VALUES(?,?,?)',(u['id'],'Password changed; sessions revoked',time.time()));return self.reply({'ok':True})
    if path=='/api/logout':c.execute('DELETE FROM sessions WHERE user=?',(u['id'],));return self.reply({'ok':True})
    if path=='/api/records/update':
     record=c.execute('SELECT * FROM records WHERE id=? AND tenant=?',(int(d['id']),u['tenant'])).fetchone()
     if not record:return self.reply({'error':'Record not found'},404)
     if record['user']!=u['id'] and u['role'] not in ['admin','superadmin']:return self.reply({'error':'Forbidden'},403)
     if d.get('delete'):
      c.execute('DELETE FROM records WHERE id=?',(record['id'],));return self.reply({'ok':True})
     content=json.loads(record['data']); status=d.get('status')
     transitions={'open':['assigned','cancelled'],'assigned':['in_progress','cancelled'],'in_progress':['completed'],'completed':[],'cancelled':[]}
     if record['kind']=='job':
      if status not in transitions.get(content.get('status','open'),[]):raise ValueError('Invalid work-order transition')
      content['status']=status
     elif record['kind']=='ticket':
      if status not in ['open','resolved']:raise ValueError('Invalid ticket status')
      content['status']=status
     else:raise ValueError('This record only supports deletion')
     c.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(content),record['id']))
     c.execute('INSERT INTO audit(user,action,created) VALUES(?,?,?)',(u['id'],'record update '+str(record['id']),time.time()));return self.reply({'ok':True})
    if path=='/api/records':
     if d.get('kind') not in ['alert','watchlist','comment','job','application','ticket']:raise ValueError('Unknown record type')
     content=d.get('data',{})
     if not isinstance(content,dict):raise ValueError('Invalid record')
     if d['kind']=='application':
      job=c.execute("SELECT * FROM records WHERE id=? AND tenant=? AND kind='job'",(int(content.get('job',0)),u['tenant'])).fetchone()
      if not job or json.loads(job['data']).get('status','open')!='open':raise ValueError('Work order unavailable')
      if job['user']==u['id']:raise ValueError('Cannot apply to your own work order')
      if any(json.loads(r['data']).get('job')==str(content['job']) for r in c.execute("SELECT data FROM records WHERE user=? AND kind='application'",(u['id'],))):raise ValueError('Already applied')
      content={'job':str(content['job']),'status':'submitted'}
     if d['kind']=='job':content['status']='open'
     if d['kind']=='alert':
      if content.get('direction') not in ['above','below']:raise ValueError('Choose above or below')
      if not math.isfinite(float(content.get('target',0))) or float(content['target'])<=0:raise ValueError('Positive target required')
     c.execute('INSERT INTO records(tenant,user,kind,data,created) VALUES(?,?,?,?,?)',(u['tenant'],u['id'],d['kind'],json.dumps(content),time.time()));return self.reply({'ok':True})
    if u['role']!='superadmin':return self.reply({'error':'Forbidden'},403)
    if path=='/api/admin/rates':
     buy=float(d['buy']);sell=float(d['sell'])
     if not 0<buy<=sell<1e15:raise ValueError('Rates must be positive with sell >= buy')
     if not all(d.get(k) for k in ['base','quote','market','source','observed']):raise ValueError('Complete all rate fields')
     c.execute('INSERT INTO rates(base,quote,market,buy,sell,source,observed,created) VALUES(?,?,?,?,?,?,?,?)',(d['base'].upper(),d['quote'].upper(),d['market'],buy,sell,d['source'],d['observed'],time.time()))
    elif path=='/api/admin/tenants':c.execute('INSERT INTO tenants(name,slug) VALUES(?,?)',(d['name'],d['slug']))
    elif path=='/api/admin/users':
     if d['role'] not in ['user','admin']:raise ValueError('Invalid role')
     c.execute('UPDATE users SET tenant=?,role=? WHERE id=? AND role!=?',(int(d['tenant']),d['role'],int(d['id']),'superadmin'))
     c.execute('DELETE FROM sessions WHERE user=?',(int(d['id']),))
    else:return self.reply({'error':'Not found'},404)
    c.execute('INSERT INTO audit(user,action,created) VALUES(?,?,?)',(u['id'],path,time.time()));return self.reply({'ok':True})
  except (ValueError,KeyError,TypeError,OverflowError,sqlite3.IntegrityError) as e:self.reply({'error':str(e)},400)
if __name__=='__main__':
 init();p=argparse.ArgumentParser();p.add_argument('--admin-email');p.add_argument('--port',type=int,default=18821);a=p.parse_args()
 if a.admin_email:
  import getpass
  secret=os.getenv('ADMIN_PASSWORD') or getpass.getpass('New admin password: ')
  if len(secret)<16:raise SystemExit('Admin password requires 16 characters')
  salt=secrets.token_hex(16)
  with db() as c:c.execute("INSERT INTO users(tenant,email,salt,hash,role) VALUES(1,?,?,?,'superadmin') ON CONFLICT(email) DO UPDATE SET salt=excluded.salt,hash=excluded.hash,role='superadmin'",(a.admin_email.lower(),salt,password(secret,salt)))
 else:ThreadingHTTPServer(('127.0.0.1',a.port),App).serve_forever()
