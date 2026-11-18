# Deployment and maintenance

This describes the single-server deployment shipped in this repository: the app in a container, PostgreSQL for account data, and Caddy in front for HTTPS. Status of each part is in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md); the image builds and starts in CI, but the full stack has not been run on a server (see "Verification status" below).

## Architecture

```
Internet ──443──> Caddy (TLS, security headers, 12 MB body limit)
                    └──> app:8501  Streamlit, non-root
                            ├──> db:5432  PostgreSQL 16 (volume postgres_data)
                            │      history, feedback, sender_rules, deleted_accounts
                            └──> /var/lib/spamguard  (volume)
                                   logs/     scrubbed audit log, rotated at 5 MB
                                   models/   baseline + released versions + active.json
backup container: pg_dump once a day into volume db_backups, 7 days kept
```

### Data storage

Account data lives in the database (`src/db.py`, `src/user_storage.py`):

| Table | Holds | Kept for |
|---|---|---|
| `history` | Result summaries (assessment, score, category, time), only if the person turns history on | 1, 7 or 30 days, as chosen; last 100 per account |
| `feedback` | Corrections people send, with their consent flag and review status | 30 days |
| `sender_rules` | Trusted and blocked addresses per account | Until removed |
| `deleted_accounts` | Hashes of deleted accounts, so restores don't bring them back | Permanent |

Accounts appear only as a SHA-256 hash of the sign-in identity or a random guest id. Message text from checks, passwords and tokens are never stored.

The schema is managed by Alembic migrations in `migrations/`. They run automatically when the app starts (the container waits up to a minute for the database), and a PostgreSQL advisory lock stops two starting processes from migrating at the same time. To change the schema, add a new file under `migrations/versions/`; never edit an applied one.

`SPAMGUARD_DATABASE_URL` selects the database. Docker Compose sets it to the `db` service. Without it, the app uses a SQLite file (`data/spamguard.db` locally, `/var/lib/spamguard/spamguard.db` in the container), which is fine for development or a single small instance.

### Scaling

Account data is now safe with several app containers sharing one PostgreSQL database. Three things are still per process and would need work before running replicas behind a load balancer:
- **Rate limits** are kept in memory (`src/rate_limit.py`), so each replica counts separately. Moving them to Redis is the next step.
- **Streamlit sessions** live in the process; the load balancer must use sticky sessions.
- **Model releases** use a file lock on the `models/` volume, which must be shared storage, or releases should be done on one node and redeployed.

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
| `POSTGRES_PASSWORD` | yes | Database password, letters and digits only: `openssl rand -hex 24` |
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

The `backup` service runs `pg_dump` once a day into the `db_backups` volume (`spamguard_<time>.dump`) and removes dumps older than 7 days. The app itself deletes expired history and feedback every hour.

Copy dumps off the host; a backup on the same disk does not survive losing the disk:

```sh
docker compose cp backup:/backups ./offsite-backups
```

Restore. A restore must not bring back accounts deleted after the backup was taken, so their deletion markers are saved first and re-applied afterwards:

```sh
docker compose exec app python scripts/backup_and_retention.py export-deletions /tmp/deletions.txt
docker compose cp app:/tmp/deletions.txt ./deletions.txt
docker compose stop app
docker compose cp ./offsite-backups/spamguard_<time>.dump db:/tmp/restore.dump
docker compose exec db pg_restore --clean --if-exists --no-owner --single-transaction -U spamguard -d spamguard /tmp/restore.dump
docker compose start app
docker compose cp ./deletions.txt app:/tmp/deletions.txt
docker compose exec app python scripts/backup_and_retention.py reapply-deletions /tmp/deletions.txt
```

With SQLite (no Compose database), `python scripts/backup_and_retention.py` makes a consistent copy and `python scripts/backup_and_retention.py restore FILE` restores it and re-applies deletions in one step.

Models and logs are on the `spamguard_state` volume, not in the database dumps; snapshot that volume if you need them. Encrypt the host disk at rest; neither the app nor PostgreSQL encrypts its files.

### Moving from the old JSON storage

Earlier versions kept account data as JSON files under `data/users/`. To copy them into the database once:

```sh
python scripts/migrate_json_to_db.py --dry-run     # shows what would be copied
python scripts/migrate_json_to_db.py
```

It is safe to run twice, skips accounts that were deleted, and leaves the JSON files in place for you to delete after checking.

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

Put any HTTPS reverse proxy in front, set `SPAMGUARD_ENV=production`, `SPAMGUARD_TRUST_PROXY=1` and `SPAMGUARD_DATABASE_URL` (for example `postgresql+psycopg://user:password@localhost:5432/spamguard`), and schedule `scripts/backup_and_retention.py` daily (it needs `pg_dump` on the path for PostgreSQL). For screenshot and QR checks install `requirements-images.txt` and Tesseract.

## Verification status

Tested on the development machine: the application, the test suite on SQLite, the start-up configuration logic, SQLite backup and restore, and the JSON-to-database migration.

Tested in GitHub Actions (commit `b596d72`): the image builds, the app container reaches a healthy state, a prediction runs inside it, and it refuses to start with a weak cookie secret. The `container` job in `.github/workflows/tests.yml` repeats this on every push.

The `test` job also runs the whole suite against PostgreSQL 16, and the `container` job starts the image against a PostgreSQL container, checks the migration, stores data and dumps it with `pg_dump`.

Not run anywhere yet: `docker compose up` with Caddy and the backup service, certificate issuance, a full pg_dump restore through the documented steps, and Google sign-in against a real OAuth client, because no server, domain or credentials were available.
