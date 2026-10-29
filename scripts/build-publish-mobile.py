#!/usr/bin/env python3
"""Build a signed Android release and publish only after verification.
Run as root on the Exchange/Apps Store host. Signing state stays outside Git.
"""
import argparse, hashlib, json, os, secrets, shutil, sqlite3, subprocess, tempfile, time, urllib.request, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def run(args, **kw):
    return subprocess.run([str(a) for a in args], check=True, **kw)
def download(url, target):
    with urllib.request.urlopen(url, timeout=180) as src, target.open('wb') as dst:
        shutil.copyfileobj(src, dst)
def extract(archive, target):
    with zipfile.ZipFile(archive) as z:
        if any(p.startswith('/') or '..' in Path(p).parts for p in z.namelist()):
            raise ValueError('Unsafe tool archive')
        z.extractall(target)
def atomic_copy(src, dst):
    if not dst.parent.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.parent.chmod(0o755)
    tmp = dst.with_suffix(dst.suffix + '.tmp')
    shutil.copyfile(src, tmp); tmp.chmod(0o644); tmp.replace(dst)
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--state', type=Path, default=Path('/var/lib/africa-exchange-android'))
    p.add_argument('--store-root', type=Path)
    p.add_argument('--store-db', type=Path, default=Path('/var/lib/africanappsstore/store.sqlite3'))
    p.add_argument('--build-only', action='store_true')
    args = p.parse_args()
    if not args.build_only:
        if not args.store_root or not (args.store_root/'app.py').is_file() or not args.store_db.is_file():
            p.error('Provide the existing Apps Store checkout with --store-root; existing store database required')
        with sqlite3.connect(args.store_db) as c:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='hosted_apps'").fetchone():
                raise ValueError('Store hosted_apps schema missing')
    os.umask(0o077); args.state.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock = (args.state/'build.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    sdk = args.state/'sdk'; manager = sdk/'cmdline-tools/latest/bin/sdkmanager'
    if not manager.exists():
        with tempfile.TemporaryDirectory(dir=args.state) as td:
            td = Path(td); archive = td/'sdk.zip'
            download('https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip', archive)
            extract(archive, td/'tools'); manager.parent.parent.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(td/'tools/cmdline-tools'), str(manager.parent.parent))
            for script in manager.parent.iterdir(): script.chmod(0o700)
    env = dict(os.environ, ANDROID_HOME=str(sdk), ANDROID_SDK_ROOT=str(sdk))
    run([manager, '--licenses'], input=('y\n'*200).encode(), stdout=subprocess.DEVNULL, env=env)
    run([manager, 'platform-tools', 'platforms;android-35', 'build-tools;35.0.0'], env=env)
    for folder in (sdk/'build-tools/35.0.0', sdk/'platform-tools'):
        for tool in folder.rglob('*'):
            if tool.is_file():
                with tool.open('rb') as f: magic = f.read(4)
                if magic in (b'\x7fELF', b'#!/b', b'#!/u'): tool.chmod(0o700)
    gradle = args.state/'gradle-8.9/bin/gradle'
    if not gradle.exists():
        with tempfile.TemporaryDirectory(dir=args.state) as td:
            archive = Path(td)/'gradle.zip'; url = 'https://services.gradle.org/distributions/gradle-8.9-bin.zip'
            download(url, archive)
            expected = urllib.request.urlopen(url+'.sha256', timeout=30).read().decode().split()[0]
            if hashlib.sha256(archive.read_bytes()).hexdigest() != expected: raise ValueError('Gradle checksum mismatch')
            extract(archive, args.state)
        gradle.chmod(0o700)
    key = args.state/'release.jks'; passwordfile = args.state/'signing-password'
    if key.exists() != passwordfile.exists(): raise ValueError('Incomplete signing state; restore key/password backup')
    if not passwordfile.exists():
        passwordfile.write_text(secrets.token_urlsafe(48)); passwordfile.chmod(0o600)
    password = passwordfile.read_text()
    env.update(ANDROID_KEYSTORE=str(key), ANDROID_STORE_PASSWORD=password, ANDROID_KEY_PASSWORD=password, ANDROID_KEY_ALIAS='exchange')
    if not key.exists():
        run(['keytool','-genkeypair','-noprompt','-keystore',key,'-alias','exchange','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Africa Exchange','-storepass:env','ANDROID_STORE_PASSWORD','-keypass:env','ANDROID_KEY_PASSWORD'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        key.chmod(0o600)
    counter = args.state/'version-code'; version = int(counter.read_text())+1 if counter.exists() else 1
    counter.write_text(str(version)); env['APP_VERSION_CODE'] = str(version)
    run([gradle, '-p', ROOT/'mobile', '--no-daemon', '--max-workers=2', 'assembleRelease', 'bundleRelease'], env=env)
    apk = ROOT/'mobile/app/build/outputs/apk/release/app-release.apk'
    run([sdk/'build-tools/35.0.0/apksigner', 'verify', '--verbose', '--print-certs', apk], env=env)
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    info = dict(domain='exchange.africandroid.world', name='Africa Exchange', category='Finance', package='world.africandroid.exchange', website='https://exchange.africandroid.world/', install_url='https://exchange.africandroid.world/#download', apk_url='https://exchange.africandroid.world/app.apk', download_status='available', version=f'1.0.{version}', sha256=digest, platforms='Android 8+', description='Compare sourced currency rates, view history, convert currencies and manage your watchlists with your existing Africa Exchange account.', features=['Currency converter','Source-labelled rates and history','Watchlists and target-rate alerts','Existing account and tenant workspaces'], limitations='Internet required. Uses the live Africa Exchange website. No Google Play or Apple App Store publication.')
    (args.state/'release.json').write_text(json.dumps(info, indent=2))
    if args.build_only:
        print('BUILD VERIFIED:', apk); return
    # Back up the database before updating metadata; keep existing visibility.
    with sqlite3.connect(args.store_db) as c, sqlite3.connect(args.state/f'store-backup-{int(time.time())}.sqlite3') as backup:
        c.backup(backup)
    atomic_copy(apk, ROOT/'static/app.apk')
    atomic_copy(apk, args.store_root/'static/downloads/africa-exchange.apk')
    with sqlite3.connect(args.store_db) as c:
        c.execute('INSERT INTO hosted_apps(domain,metadata,updated) VALUES(?,?,?) ON CONFLICT(domain) DO UPDATE SET metadata=excluded.metadata,updated=excluded.updated', (info['domain'], json.dumps(info), int(time.time())))
    with urllib.request.urlopen(info['apk_url'], timeout=60) as response:
        online = hashlib.sha256(response.read()).hexdigest()
    if online != digest: raise ValueError('Public APK checksum mismatch: check Nginx static routing')
    with urllib.request.urlopen('https://africanappsstore.space/api/hosted-apps', timeout=30) as response:
        catalog = json.load(response)
    print('PUBLISHED signed APK SHA-256:', digest)
    print('Store metadata saved; administrator visibility preserved. Public catalog response verified.')
if __name__ == '__main__': main()
