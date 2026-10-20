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
TLS_EMAIL="$tls_email" ansible-playbook -i 'localhost,' -c local ansible/deploy.yml -e 'tls_email={{ lookup("env", "TLS_EMAIL") }}'
read -r -p 'Super admin email: ' admin_email
runuser -u africa-exchange -- env DATABASE_PATH=/var/lib/africa-exchange/exchange.db python3 server.py --admin-email "$admin_email"
echo 'Deployment complete: https://exchange.africandroid.world/'
