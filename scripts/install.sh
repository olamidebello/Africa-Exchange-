#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo 'Run as root on the Olamidepanel hosting server.' >&2; exit 1; fi
read -r -p 'TLS contact email: ' tls_email
[[ "$tls_email" == *@* ]] || { echo 'Valid email required'; exit 1; }
apt-get update
apt-get install -y git ansible python3
if [[ ! -d /opt/africa-exchange/.git ]]; then
  git clone https://github.com/olamidebello/Africa-Exchange-.git /opt/africa-exchange
fi
cd /opt/africa-exchange
git pull --ff-only origin main
TLS_EMAIL="$tls_email" ansible-playbook -i ansible/inventory.local.ini ansible/deploy.yml -e 'tls_email={{ lookup("env", "TLS_EMAIL") }}'
getent passwd africa-exchange >/dev/null || { echo 'Deployment did not create the service user; stopping.' >&2; exit 1; }
systemctl is-active --quiet africa-exchange || { echo 'Africa Exchange service is not running; stopping.' >&2; exit 1; }
python3 - <<'CHECK'
import json, urllib.request
with urllib.request.urlopen('https://exchange.africandroid.world/api/health', timeout=20) as response:
    if response.status != 200 or json.load(response).get('ok') is not True:
        raise SystemExit('Public HTTPS health check failed')
CHECK
read -r -p 'Super admin email: ' admin_email
runuser -u africa-exchange -- env DATABASE_PATH=/var/lib/africa-exchange/exchange.db python3 server.py --admin-email "$admin_email"
echo 'Deployment complete: https://exchange.africandroid.world/'
