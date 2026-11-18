# Production readiness report

Date: 15 November 2026. This records what was changed, what was tested and how, and what is still open. "Verified" means it was run and observed on the development machine (macOS, Python 3.12.16); anything else says so.

## Verdict

The application runs, its tests pass, and the main security gaps found in the audit are closed. It is not yet proven as a public deployment: the container image builds and starts in CI, but the full stack has never run on a server with a real domain, no Google credentials were available, and the classifier is trained on old public corpora. The items under "Open before public launch" need doing first.

## Test and validation results

| Check | Result |
|---|---|
| Automated tests (`pytest tests`) | 160 passed, 1 skipped (the skipped test needs OpenCV, an optional dependency) |
| Check → Understand → Act flow in a browser | Verified with the fake-payment example: High risk, 100/100, evidence listed, action page loads |
| Advanced (model comparison) and Settings pages | Load without errors |
| Demo mailbox scan and list labels | Verified: two scams High risk, electricity notice Needs verification, GitHub and meeting mail No strong warning |
| Real mailbox scan | Confirmed by the owner on their own inbox after the labelling fix; not retested after the later changes |
| Phone width (375 px) | No horizontal overflow on the Check page; other pages not inspected at this width |
| Browser console | No errors on a clean load |
| Model training | Retrained 18 November on 124,742 public messages; results in [MODEL_CARD.md](MODEL_CARD.md) |
| False alarms on real present-day mail | 93-message sample from the owner's inbox, text only: "Needs verification" 14 → 12, High risk 0. Bank alerts with a provider-verified sender drop to "No strong warning"; the owner rescanned their inbox in the app on 18 November and confirmed normal mail is no longer flagged |
| Tests on Linux with pinned requirements | Passed in GitHub Actions for commit `b596d72` (run 43684267809, `test` job) |
| Docker image build and start | Passed in the same run (`container` job): image builds, container becomes healthy, the model classifies inside it, and start-up is refused with a weak cookie secret |
| Compose stack, Caddy and HTTPS, backup container, Google sign-in | Not run (no Docker, domain or credentials on the development machine; CI starts the app container alone) |
| Load or concurrency testing | Not done |
| Accessibility audit | Not done |

New tests in this round (`tests/test_production_hardening.py`, `tests/test_scam_assistant.py`): rate limiter windows, private-address and port rejection for custom IMAP servers, certificate verification on IMAP, start-up secret rendering and its failure cases, production admin switch, Markdown escaping, backup of linked directories, word-count reconstruction detection, inbox triage labels.

## What changed

### Model
- Excluded 4,631 rows that were word-count reconstructions rather than messages; cross-validation showed they made real-text results worse.
- Chose settings by 5-fold cross-validation over 56 combinations; vocabulary raised from 6,000 to 100,000 terms, SVM C from 1 to 3.
- Held-out result for the SVM: 98.73% accuracy, 96.46% spam precision, 96.71% recall on 2,133 rows. Added per-source errors and a near-duplicate audit to `models/metrics.json`.
- On the 29-scenario modern benchmark the classifier alone did not improve (10 of 14 scams, 5 false warnings, before and after).

### Bugs and behaviour
- Inbox list showed the raw classifier verdict as "SPAM"/"CLEAN"; it now shows the same four-level assessment as the detailed result.
- A single weak wording cue with a low score no longer raises the assessment (benchmark false warnings 5 → 3, all 14 scams still flagged).
- Backups archived a link instead of its contents when a data directory was a symlink.
- Removed an unused module that presented rule output as LLM reasoning, four leftover sample-data files, and a shortcut that treated any account with the password "demo" as the demo mailbox.

### Security
- IMAP connections did not verify TLS certificates (Python's `imaplib` default) and had no timeout; both fixed.
- Custom IMAP host and port were unrestricted, which would let a public instance be used to probe internal addresses; now validated.
- Added rate limits, including a per-mailbox cap on connection attempts.
- Email subjects, senders, attachment names and link text were rendered as Markdown, so a crafted subject could embed a remote image; now escaped. Connected-account text in HTML banners is escaped.
- Streamlit usage statistics were on despite the "no external telemetry" claim; turned off. XSRF protection is explicit; the dev container no longer disables it.
- `SPAMGUARD_LOCAL_ADMIN` is ignored when `SPAMGUARD_ENV=production`.

### Deployment
- Added `Dockerfile`, `docker-compose.yml`, `deploy/Caddyfile`, `.env.example`, `.dockerignore`, `scripts/container_entrypoint.py`, `requirements-lock.txt`, and a CI job that builds and health-checks the image.

## Requested items that were not done, and why

| Item | Status |
|---|---|
| Production database, migrations, query and index tuning | Done 18 November: PostgreSQL (SQLite for development) with Alembic migrations, indexes for the review queue and expiry, daily pg_dump backups. Rate limits are still in memory. |
| Larger, more representative training data | Not done. Only the data in `dataset/` was used; no new corpus was downloaded. This is the main limit on model quality. |
| API endpoint verification | There are no HTTP APIs beyond Streamlit's own; the health endpoint is the only one relied on. |
| Role-based access control | Two roles exist (user, admin by verified email). Nothing finer was added. |
| Docker build and deployment verification | Image build and single-container start verified in CI. The Compose stack and a real deployment have not been run. |
| Domain, HTTPS certificate, Google OAuth verification | Need accounts and decisions only the owner can provide. |
| End-to-end tests against a real Gmail account | Not possible without credentials. |

## Checklist

Done and verified
- [x] Test suite passes locally
- [x] Core journey works in a browser
- [x] Models retrained, evaluated on a held-out set, artifacts saved and loaded by the app
- [x] No secrets in the working tree; `.env` and `secrets.toml` ignored
- [x] TLS verification, endpoint validation and rate limits covered by tests
- [x] Telemetry off, XSRF on
- [x] Container image builds and passes its health check (CI, commit `b596d72`)
- [x] `requirements-lock.txt` installs on Linux and the tests pass there (CI, commit `b596d72`)

Done, not yet verified
- [ ] Compose stack serves the app over HTTPS on a real domain
- [ ] Daily backup container produces restorable archives on the volume

Open before public launch
- [ ] Remove or restrict the Firebase web key that remains in git history (commit `b5e6fa4` and earlier)
- [ ] Create the Google OAuth client, add test users, start Google's verification for Gmail scopes
- [ ] Publish a privacy policy and terms
- [ ] Encrypt the host volume and arrange off-host backup copies
- [ ] Add an uptime monitor on `/_stcore/health`
- [ ] Move rate limits to Redis before running more than one app container
- [ ] Decide whether to add a present-day email corpus and retrain
- [ ] Have someone other than the author review the scam rules and the security changes
