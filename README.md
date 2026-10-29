# Africa Exchange

**Africa’s currencies. One clear view.**

Target: https://exchange.africandroid.world/ on the Olamidepanel server. Africa Jobs is deliberately protected from overwrite.

## Run

Python 3.11+, no third-party runtime dependencies:

```sh
python3 server.py --admin-email you@example.com
python3 server.py
python3 -m unittest discover -s tests -v
```

Admin creation prompts for a 16+ character password; no default credentials. Open http://127.0.0.1:18821. Production uses an HTTPS reverse proxy. DATABASE_PATH selects persistent SQLite storage. PUBLIC_URL must match the external HTTPS origin.

## Deploy on Olamidepanel server

Point exchange.africandroid.world at the hosting server. Review existing DNS and certificates first. Run on that host, or over SSH with an Ansible inventory:

```sh
ansible-playbook -i ansible/inventory.example ansible/deploy.yml -e tls_email=YOUR_EMAIL
```

Optional manual administrator reset on the server (deployment now automatically creates the first administrator):

```sh
sudo -u africa-exchange DATABASE_PATH=/var/lib/africa-exchange/exchange.db python3 /opt/africa-exchange/server.py --admin-email YOUR_EMAIL
```

This installs a dedicated systemd service, loopback port 18821 and Nginx virtual host. Certbot runs only with tls_email supplied. Existing TLS configuration is preserved. No unknown Olamidepanel inventory schema is modified; register the domain/service in the panel's Hosting Domains interface after deployment.

## Implemented

Source-labelled buy/sell market quotes, search/filter, CSV export, per-source history, reversible converter, iframe converter embed, registration/login/logout, private sessions, personal watchlists, target-rate records, comments/support records, tenant-separated work orders and applications, super admin rate publication, tenant creation, membership management and audit log. Tenant assignment is controlled by super admin; self-registration joins the default tenant. Tenant admins can review their tenant records. Terms, privacy and copyright pages are included.

No sample market prices are presented as live data. Publish verified quotes through super admin. Target-rate entries support in-app evaluation; no automatic notification delivery exists. Work orders support posting, applications and status transitions. This is an initial implementation, not complete NGN Rates or Field Nation parity. No preconfigured live feed, payment/escrow, dispatch, chat, background checks, password-reset email, background alert delivery, billing, tenancy subdomains or comprehensive production abuse controls is included yet. Legal text should be adapted to the operator's actual legal identity, jurisdiction and retention policy before public launch.

## Android and Apps Store

Native Android WebView client loads the HTTPS production site. The same master logo is used for website, hero, favicon and launcher icon. Use GitHub Actions “Signed Android release” after configuring persistent signing secrets: ANDROID_KEYSTORE_BASE64, ANDROID_STORE_PASSWORD, ANDROID_KEY_ALIAS, ANDROID_KEY_PASSWORD. Never commit a signing key. Workflow builds a signed release and creates a GitHub release. Android SDK / JDK17 / Gradle8.9 required for local builds.

Download and verify the release APK, then run:

```sh
ansible-playbook -i ansible/inventory.example ansible/publish-mobile.yml -e apk_path=/ABSOLUTE/PATH/app-release.apk -e apps_store_root=/VERIFIED/STORE/WEBROOT
```

The publication playbook verifies the signature using local apksigner, copies the APK to both hosts' web roots (assuming same hosting server), supplies an additive JSON listing for catalog import, and checks downloads. Existing store catalogs are not overwritten. Catalog UI import requires inspection of the real Apps Store repository/schema. The website download button remains hidden until an APK exists. A source checkout alone does not mean deployment, an APK build or store listing is complete.

## Continued implementation

Additional controls now include work-order transitions (open → assigned → in progress → completed, with cancellation before progress), in-tenant application validation, duplicate/self-application prevention, record deletion, in-app target-rate evaluation, and a sell-rate history chart. Alerts are evaluated when the user clicks **Check my alerts**; this does not send background push/email notifications.

Run the automatic installer **on the Olamidepanel server** after DNS is configured:

```sh
git clone https://github.com/olamidebello/Africa-Exchange-.git /opt/africa-exchange
sudo bash /opt/africa-exchange/scripts/install.sh
```

### Authorized rate feed

`scripts/import-rates.py` imports local JSON snapshots or operator-authorized HTTPS feeds. It validates the whole snapshot before inserting, rejects invalid/nonfinite rates and timestamps, and skips duplicate observations. Provider adapter format:

```json
[{"base":"USD","quote":"NGN","market":"FX market","buy":1500,"sell":1510,"source":"YOUR VERIFIED PROVIDER URL","observed":"2026-01-01T00:00:00Z"}]
```

The above is a schema example, not a current rate. The importer requires an authorized provider or an operator-produced export in this format; no feed is preconfigured or claimed live. Enable hourly refresh with `ansible/rate-feed.yml` and `rate_feed_url`. API endpoints and CSV/embed redistribution require appropriate provider permission. Existing source records remain visible if a feed fails; observation timestamps identify staleness.

## Automatic super admin provisioning

The installer uses `dobcalldemo@gmail.com` as TLS contact by default (override with TLS_EMAIL). The playbook creates the first super admin with this email (override with admin_email), generates a random password, and stores credentials in `/etc/africa-exchange-admin.json` with mode 0600. It never resets existing super admins. Read that file as root, sign in, and use My workspace → Account security to set your password; all old sessions are revoked. Remove the initial credential file after securing your account. No password is committed or printed in Ansible output. Provisioning runs in the deploy playbook before application startup.

```sh
cd /opt/africa-exchange
git pull --ff-only origin main
sudo bash scripts/install.sh
sudo cat /etc/africa-exchange-admin.json
```

This provisions the Africa Exchange super admin GUI. It does not create an Olamidepanel administrator or bypass existing panel authentication.

## Afira currency

The shared currency catalogue (`GET /api/currencies`) includes Afira, proposed code AFR, symbol Ⱥ, pronunciation Ah-FEE-rah and subdivision 100 cents. Admin rate entry suggests AFR, quotes involving AFR are labelled proposed, and converter outputs use Ⱥ with two decimal places. There is no seeded or assumed AFR exchange rate. Once a sourced AFR quote is published, the existing history, CSV, watchlists, alerts, converter and mobile WebView support it.

## TradeNAIRA and API administration

Super admin → API providers & keys controls the fixed TradeNAIRA parallel-rate provider, enables automatic refresh (15 minutes to 24 hours), displays refresh errors, and triggers manual refresh. The default public market filter is Parallel market. The provider requires no upstream API key in beta and attribution links are included. No arbitrary provider URL or secret is accepted. Null parallel data, invalid values and observations older than 48 hours are rejected; official rates are never substituted. A single reference is stored in both buy/sell fields because the provider does not supply a bid/ask spread. Existing observations retain their dates on failures.

Admins can publish corrected observations, remove erroneous observations, and generate/revoke read-only client keys. Keys are shown only at creation and stored as SHA-256 hashes. Send `Authorization: Bearer KEY` to `GET /api/v1/rates`; this endpoint returns published observations, including history, not guaranteed executable or current prices. Keys do not grant administrator access. Rotate by generating a replacement, updating the client, then revoking the previous key.

Deploy the updated checkout using the existing installer, restart `africa-exchange`, sign in, enable TradeNAIRA refresh, and save. Scheduling runs inside the application while the service is running. Provider settings and API keys persist in the existing database. Additional commercial providers require separate adapters and provider-specific authentication support.


## Pull and deploy updates with Ansible

Run on the server currently hosting `exchange.africandroid.world`:

```sh
cd /opt/africa-exchange
git pull --ff-only origin main
sudo ansible-playbook -i ansible/inventory.local.ini ansible/pull-deploy.yml -e tls_email=dobcalldemo@gmail.com
```

For a first install, `sudo bash scripts/install.sh` installs Ansible and runs the same deployment tasks. For remote deployment, copy `ansible/inventory.example`, set the actual current hosting server, and run `ansible-playbook -i YOUR_INVENTORY ansible/pull-deploy.yml -e tls_email=dobcalldemo@gmail.com`.

The playbook pulls `main` without overwriting local changes, creates a consistent private SQLite backup under `/var/backups/africa-exchange/`, checks Python syntax, preserves accounts/provider settings/API key hashes, restarts the service when source changes, validates Nginx, and checks application and provider-control endpoints. Supplying `tls_email` also provisions/verifies HTTPS; ensure DNS points at this host first. Backups contain sensitive application data; retain them according to your backup policy. Deployment does not automatically restore a backup after failure.

After deployment, sign in as super admin and enable TradeNAIRA automatic refresh in **API providers & keys**. Provider settings are preserved during subsequent deployments. A missing parallel quote remains unavailable rather than using an official rate.


## Active provider: TradeNAIRA

TradeNAIRA is the only active importer. No upstream key is required. Any existing ABOKI_FOREX_API_KEY setting is ignored. Aboki is not called. Enable the provider in super admin settings; unavailable parallel rates are reported without substituting official rates.
