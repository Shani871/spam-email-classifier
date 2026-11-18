# Deployment and maintenance

This describes the single-server deployment shipped in this repository: the app in a container, Caddy in front for HTTPS, and one volume for all state. Status of each part is in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md); the image builds and starts in CI, but the full stack has not been run on a server (see "Verification status" below).

## Architecture

```
Internet ──443──> Caddy (TLS, security headers, 12 MB body limit)
                    └──> app:8501  Streamlit, non-root, one process
                            └──> /var/lib/spamguard  (volume)
                                   users/    account-scoped JSON, hashed directory names
                                   logs/     scrubbed audit log, rotated at 5 MB
                                   backups/  daily archives, last 7 kept
                                   models/   baseline + released versions + active.json
backup container: retention cleanup + archive every 24 h, same volume
```

There is no database server. Account data is JSON files written atomically under file locks (`src/user_storage.py`). That is safe for one app container on one host. Do not run several app replicas or put the volume on a network share: rate limits and session state are per process, and file locks are not reliable across hosts. Moving to several nodes needs a real database first; that work is not done.

## First deployment

Requirements: a Linux host with Docker Engine and the Compose plugin, 2 GB RAM, ports 80 and 443 open, and a DNS record for your domain pointing at the host.

```sh
git clone <repository-url> spamguard && cd spamguard
cp .env.example .env
```

Edit `.env`:

| Variable | Required | Purpose |
|---|---|---|
| `DOMAIN` | yes | Public host name; Caddy obtains the certificate for it |
| `ACME_EMAIL` | no | Let's Encrypt contact address |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | for sign-in | Google OAuth client; leave both empty for guest-only mode |
| `SPAMGUARD_COOKIE_SECRET` | with sign-in | Random, 32+ characters: `openssl rand -hex 32` |
| `SPAMGUARD_ENABLE_GMAIL_ACTIONS` | no | `1` adds the optional move-to-spam permission |
| `SPAMGUARD_ADMIN_EMAILS` | no | Verified Google accounts that may review feedback and release models |
| `SPAMGUARD_IMAP_PORTS` | no | Ports allowed for custom IMAP servers (default `993`) |

Then:

```sh
docker compose up -d --build
docker compose ps          # app should become "healthy"
curl -fsS https://$DOMAIN/_stcore/health
```

The container refuses to start if sign-in is half configured (missing secret, cookie secret under 32 characters, non-HTTPS public URL) or if `SPAMGUARD_LOCAL_ADMIN` is set.

### Google sign-in

In Google Cloud Console create an OAuth client (Web application), enable the Gmail API, and add `https://<DOMAIN>/oauth2callback` as an authorised redirect URI. Until Google has verified the app for the restricted Gmail scopes, only test users you list in the consent screen can connect an inbox. Verification, a published privacy policy and domain ownership are Google's requirements and cannot be completed from this repository.

Without sign-in the app still works for pasted text, `.eml` files, screenshots and app-password IMAP; each browser session is a separate guest.

## Secrets

- Secrets come from `.env` on the host and are rendered into `~/.streamlit/secrets.toml` inside the container (mode 0600) at start-up. `.env` and `.streamlit/secrets.toml` are git-ignored.
- To use a secret store instead, mount a ready `secrets.toml` at `/app/.streamlit/secrets.toml`; the entrypoint then leaves it alone.
- App passwords typed for IMAP are held in server memory for the session only and are never written to disk or logs.

## Security controls in place

| Control | Where |
|---|---|
| HTTPS, HSTS, nosniff, frame and referrer policy | `deploy/Caddyfile` |
| Non-root user, no added capabilities, no-new-privileges | `Dockerfile`, `docker-compose.yml` |
| XSRF protection on, usage statistics off, tracebacks hidden in production | `.streamlit/config.toml`, `Dockerfile` |
| Rate limits per client: checks 30/min, inbox scans 10/min, batch 3 per 5 min, mailbox connection attempts 5 per 5 min, and 8 per 15 min per target mailbox | `src/rate_limit.py` |
| IMAP over TLS with certificate verification and a 15 s timeout | `src/gmail_scanner.py` |
| Custom IMAP servers must resolve to public addresses on an allowed port | `validate_imap_endpoint` |
| Email subjects, senders and link text escaped before display | `md_escape`, `html.escape` |
| Admin functions require a verified Google account on the admin list | `src/ui_shared.py`, `src/active_learning.py` |
| Logs scrub tokens, passwords, email addresses and phone numbers; no message bodies | `src/monitoring.py` |

Rate limits are in memory: they reset on restart and assume the app is reachable only through Caddy (`SPAMGUARD_TRUST_PROXY=1`). Do not publish port 8501 directly.

Not covered: there is no web application firewall, no malware scanning of attachments, and the IMAP host check resolves the name before connecting rather than pinning the address.

## Health and monitoring

- Liveness: `GET /_stcore/health` returns `ok`. The image has a Docker `HEALTHCHECK`, and Caddy starts only after the app is healthy.
- Logs: `docker compose logs -f app` for the server; `/var/lib/spamguard/logs/security_audit.log` for audit events (JSON lines, 14-day retention).
- There is no metrics endpoint or alerting. Point an external uptime monitor at the health URL.

## Backups and restore

The `backup` service runs `scripts/backup_and_retention.py` once a day: it deletes expired history and feedback, then writes `backups/spamguard_backup_<timestamp>.tar.gz` and keeps the last seven. Archives contain account data only; released model versions are on the same volume but not inside the archives.

Copy archives off the host; a backup on the same disk does not survive losing the disk:

```sh
docker compose cp backup:/var/lib/spamguard/backups ./offsite-backups
```

Restore (accounts deleted since the backup stay deleted, via tombstones):

```sh
docker compose stop app
docker compose run --rm backup python -c "from pathlib import Path; from scripts.backup_and_retention import restore_backup_archive; restore_backup_archive(Path('/var/lib/spamguard/backups/<file>.tar.gz'))"
docker compose start app
```

To capture everything including models, snapshot the `spamguard_state` volume. Encrypt the host disk or volume at rest; the app does not encrypt its files.

## Updating

```sh
git pull
docker compose up -d --build
```

The baseline model in the image replaces the baseline on the volume at every start. A model released from the admin page (`models/active.json`) stays active across updates; use "Roll back the last model release" on the Advanced page to return to the previous one.

## Retraining

- From reviewed feedback: Advanced > Feedback and training (admin). A candidate is released only if spam precision and recall do not drop by more than 0.005 on a fixed hold-out.
- From scratch: `sh scripts/fetch_public_corpora.sh`, then `python scripts/model_selection.py` and `python src/train.py` on a development machine, commit `models/`, redeploy. See [MODEL_CARD.md](MODEL_CARD.md).
- The feedback retraining button refuses to run on a server without the downloaded corpora, since the candidate would be trained on far less data than the active model. Run the fetch script on the server first if you want to retrain there.

## Running without Docker

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

Put any HTTPS reverse proxy in front, set `SPAMGUARD_ENV=production` and `SPAMGUARD_TRUST_PROXY=1`, and schedule `scripts/backup_and_retention.py` daily. For screenshot and QR checks install `requirements-images.txt` and Tesseract.

## Verification status

Tested on the development machine: the application, the test suite, the start-up configuration logic, and the backup of linked state directories.

Tested in GitHub Actions (commit `b596d72`): the image builds, the app container reaches a healthy state, a prediction runs inside it, and it refuses to start with a weak cookie secret. The `container` job in `.github/workflows/tests.yml` repeats this on every push.

Not run anywhere yet: `docker compose up` with Caddy, certificate issuance, the backup container, and Google sign-in against a real OAuth client, because no server, domain or credentials were available.
