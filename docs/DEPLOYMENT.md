# SpamGuard AI: Public Deployment Guide & Requirements

This document outlines the architecture, security practices, configuration, and remaining blockers for deploying SpamGuard AI to a public or production environment.

---

## 1. Production Architecture Overview

SpamGuard AI is designed as a privacy-preserving email and message risk assessment platform.
- **Processing Model**: All checks run locally on the app server process. No user inbox content or email text is dispatched to external proprietary LLMs by default.
- **Process Isolation**: Each user session has isolated memory. Persistent storage is scoped by cryptographic user identifiers (`sha256(identity)`).
- **Storage Tier**: Persistent disk volume mounting `/data` and `/models`.

### Recommended Host Configuration
- **Runtime**: Linux (Ubuntu 22.04 LTS or Debian 12) with Python 3.10 - 3.12.
- **Memory**: Minimum 2 GB RAM (4 GB recommended for scikit-learn model retraining and OCR).
- **Disk**: Persistent volume with at least 10 GB free space for model releases and backups.
- **OCR Dependencies (Optional for Screenshot/QR)**:
  ```bash
  apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-hin libgl1-mesa-glx
  ```

---

## 2. Secrets and Credential Security

1. **No Credentials in Source Code or URLs**:
   - `secrets.toml` is strictly ignored in `.gitignore`.
   - Never log OAuth tokens, app passwords, or full email bodies.
   - Any token-bearing query parameters (such as legacy redirects) are purged automatically on entry in `app.py`.
2. **Injecting Secrets**:
   Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` or set environment variables:
   ```toml
   [auth]
   redirect_uri = "https://your-domain.com/oauth2callback"
   cookie_secret = "GENERATE_64_CHAR_RANDOM_HEX_SECRET"
   expose_tokens = ["access"]

   [auth.google]
   client_id = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
   client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   client_kwargs = { scope = "openid email profile https://www.googleapis.com/auth/gmail.readonly", prompt = "consent select_account" }

   [app]
   admin_emails = ["security-admin@your-domain.com"]
   ```

---

## 3. Storage Isolation & Multi-Process Controls

1. **Transactional File Storage & Cross-Process Locking**:
   - State mutations in `src/user_storage.py` write to a temporary file (`tempfile.mkstemp`) before performing an atomic POSIX `os.replace`.
   - Thread safety is guarded by `threading.RLock()`, and concurrent multi-process safety is guarded by advisory cross-process file locks (`fcntl.flock`).
2. **Coordinated Model Release Controls**:
   - Model candidates trained from reviewed feedback use non-blocking cross-process file-locking (`.release.lock`) and atomic manifest swapping (`active.json`).
   - If an evaluation regresses on precision or recall compared to baseline, the candidate is safely rejected and the active version remains unmodified.
3. **Automated Retention, Backups, and Restore Behavior**:
   - History summaries expire after 1, 7, or 30 days (configured by the user).
   - Saved corrections expire after 30 days.
   - Backups are stored in `data/backups/` with strict directory permissions (`0700`), retaining the last 7 archives.
   - **Restoration & Account Deletion Tombstones**: When an account is deleted, a tombstone is recorded in `data/users/.deleted_accounts.json`. Restoring a backup archive (`restore_backup_archive()`) automatically purges any restored accounts that match the tombstone list, guaranteeing that disaster-recovery restores never resurrect user data deleted by individuals.
   - Configure a daily cron job to run the backup and retention script:
     ```cron
     0 2 * * * /opt/spamguard/.venv/bin/python /opt/spamguard/scripts/backup_and_retention.py >> /var/log/spamguard_backup.log 2>&1
     ```

---

## 4. Reverse Proxy and Network Hardening

Deploy behind Nginx or Caddy with automated HTTPS (Let's Encrypt):

### Caddyfile Example
```caddy
your-domain.com {
    reverse_proxy localhost:8501 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-Proto https
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
```

---

## 5. Error Monitoring & Log Sanitization

`src/monitoring.py` automatically scrubs:
- Bearer tokens and API keys (`[REDACTED_TOKEN]`)
- Passwords and secret values (`[REDACTED]`)
- Email addresses (`[EMAIL_MASKED]`)
- Telephone numbers (`[PHONE_MASKED]`)

Logs are stored in `data/logs/security_audit.log` with strict directory permissions (`0700`).

---

## 6. Public Deployment Blockers & Next Steps

Before enabling public sign-ins for external Google users:

| Area | Status | Requirement / Blocker |
|---|---|---|
| **Google Cloud OAuth Verification** | **Pending** | Requesting restricted scopes (`gmail.readonly`, `gmail.modify`) requires CASA Tier 2 assessment and Google security verification. |
| **Privacy Policy & Terms** | **Pending** | A public HTTPS URL with published Privacy Policy detailing message processing and 30-day retention limits is required by Google. |
| **Domain Verification** | **Pending** | Google Search Console ownership verification for the production domain. |
| **Live Gmail Mailbox Testing** | **Pending** | Live end-to-end testing with an authorized test account (mocked test suite currently passes all checks). |
| **Encrypted Disk Volume** | **Required** | Production host must utilize Linux LUKS or cloud provider volume encryption at rest for `/data`. |
