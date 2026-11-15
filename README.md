# SpamGuard AI

An evidence-led message checker for everyday people, students, job seekers, and small businesses. It combines an English spam classifier with heuristic checks for deceptive links, recruitment payments, suspicious attachment metadata, and changed invoice details.

## Main journey

1. **Check a message** — paste text, upload an `.eml` email file, compare earlier and current thread messages, review extracted screenshot/QR text, or select an email from a connected inbox.
2. **Understand the warning** — read the assessment, highlighted source sentences, actual link destinations, conversation differences (payment handles, reply routing, sensitive requests), and coverage limits. Observed evidence is separated from interpretation.
3. **Take action** — get relevant next steps, save a correction with consent, or perform a reversible Gmail label action.

Technical tools live in **Advanced**: modern detection evaluation benchmark, model comparison, preprocessing inspection, batch CSV checks, reviewed feedback releases and rollback, and private inbox monitoring. **Settings** contains Google connections, optional app-password scanning, privacy, deletion, and sender rules.

## Run locally

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

For screenshot/QR support, install `requirements-images.txt`. macOS can use Apple Vision locally; other platforms need Tesseract and desired language data. Existing baseline models are included. If missing, explicitly train with `.venv/bin/python src/train.py`.

## Privacy and reliability

- Message checks run on the app server; no external AI service receives message contents by default.
- Credentials and private runtime data are scoped to the session; saved data is scoped to a verified account or a random guest session.
- Optional saved summaries exclude message bodies; corrections require consent and review.
- Secure Google sign-in uses an OIDC callback. Gmail tokens never appear in page URLs.
- Monitoring recommends actions without claiming emails were moved. Demo/live feeds are distinguished.
- Gmail must confirm an action before it is recorded as successful. Undo restores previous inbox/spam labels.
- Trusted sender rules do not suppress strong warnings.
- Reviewed corrections actually enter candidate training; evaluation gates and an atomic version manifest protect existing models, with rollback available.

## Evaluation and limits

The included models were trained on 10,665 real-text messages (old email and SMS benchmarks plus 140 modern legitimate examples). On a 2,133-message held-out set the SVM scores 98.73% accuracy with 14 false positives and 13 false negatives. Settings were chosen by cross-validation, and rows that were word-count reconstructions rather than messages are excluded. These are benchmark numbers on old corpora: on a small set of modern scenarios the classifier alone still misses scams and flags legitimate mail, which is why the app combines it with link, header and rule checks. Full method, leakage checks and limits are in [docs/MODEL_CARD.md](docs/MODEL_CARD.md).

Assessments are **No strong warning found**, **Needs verification**, **High risk**, or **Unable to assess**. A score is an indicator, not the probability of fraud. Filename checks are not malware scanning. Header checks use declared provider evidence, not new cryptographic verification. Hindi/Hinglish have limited rules and translated labels/recovery guidance; broader language detection remains unevaluated. Invoice comparisons need supplied earlier/current text. Google authorization and real inbox actions require deployment configuration and live verification.

## Setup and testing

Read [deployment, authentication, OCR, storage, and release setup](docs/SETUP.md).

```sh
.venv/bin/python -m pytest tests -q
```

Tests use temporary private storage. They cover account separation, retention, feedback ingestion, release/rollback, failed Gmail actions, stable IMAP identifiers, preserved HTML links, job/invoice checks, and the three-step Streamlit journey.

## Deploy

A single-server Docker setup with HTTPS is included: copy `.env.example` to `.env`, set `DOMAIN`, and run `docker compose up -d --build`. Read [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) first, and [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) for what has and has not been verified. The container setup has not been built or run yet, storage is file-based and single-node, and Google sign-in needs your own OAuth client and Google's verification.
