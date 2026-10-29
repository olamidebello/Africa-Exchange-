#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root'; exit 1; }
read -r -s -p 'Aboki Forex provider API key: ' provider_key
printf '\n'
[[ "$provider_key" =~ ^[A-Za-z0-9_.-]{10,512}$ ]] || { echo 'Invalid key format'; exit 1; }
umask 077
printf 'ABOKI_FOREX_API_KEY=%s\n' "$provider_key" > /etc/africa-exchange-provider.env
unset provider_key
cd /opt/africa-exchange
sudo -u africa-exchange env DATABASE_PATH=/var/lib/africa-exchange/exchange.db python3 - <<'CHECK'
import server
server.init()
with server.db() as c:
 c.execute('UPDATE provider_config SET enabled=1, interval=3600, last_attempt=0 WHERE id=1')
CHECK
systemctl restart africa-exchange
echo 'Provider configured. Check /api/provider-status after the refresh completes. Invalid or expired keys will not publish rates.'
