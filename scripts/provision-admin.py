"""Provision first administrator once; never reset an existing administrator."""
import os,sys,json,secrets,stat
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import server

def provision(email,credential_path):
 if '@' not in email:raise ValueError('Valid administrator email required')
 server.init()
 with server.db() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute("SELECT 1 FROM users WHERE role='superadmin'").fetchone():return {'changed':False,'message':'Existing super admin preserved'}
  if c.execute('SELECT 1 FROM users WHERE email=?',(email.lower(),)).fetchone():raise ValueError('Email belongs to a regular account; choose another provisioning email')
  password=secrets.token_urlsafe(24);salt=secrets.token_hex(16)
  fd=os.open(credential_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  try:
   with os.fdopen(fd,'w')as f:
    json.dump({'url':'https://exchange.africandroid.world/#workspace','email':email.lower(),'password':password,'note':'Sign in, change this password in My workspace, then delete this recovery file.'},f,indent=2);f.flush();os.fsync(f.fileno())
   c.execute("INSERT INTO users(tenant,email,salt,hash,role) VALUES(1,?,?,?,'superadmin')",(email.lower(),salt,server.password(password,salt)))
   c.execute("INSERT INTO audit(user,action,created) VALUES(last_insert_rowid(),'Initial super admin provisioned',?)",(server.time.time(),));c.commit()
  except BaseException:
   Path(credential_path).unlink(missing_ok=True);raise
 return {'changed':True,'message':'First super admin provisioned; credentials saved privately on the server'}
if __name__=='__main__':print(json.dumps(provision(os.getenv('ADMIN_EMAIL','dobcalldemo@gmail.com'),os.getenv('ADMIN_CREDENTIAL_FILE','/etc/africa-exchange-admin.json'))))
