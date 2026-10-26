# Configuration, Data, and Artifacts (Phase 1)

This repository keeps existing runtime/data/model files intact in Phase 1 to avoid behavior changes.

## Secrets and local configuration

- Use local `.env` files for secrets; do not commit them.
- Copy from `.env.example` and set only your local values.
- Confirmed environment variables used by current code:
  - `GEMINI_API_KEY`
  - `GOOGLE_API_KEY` (fallback alias)
- Streamlit local secrets file (`.streamlit/secrets.toml`) is for local-only use and should remain untracked.

## Firebase and Gmail configuration status

- The current Streamlit UI still uses embedded Firebase client configuration in `app.py`.
- Gmail scanning/authentication currently uses interactive UI flows (App Password input or Google OAuth sign-in) rather than repository-level environment variables.
- Moving Firebase client settings or Gmail auth flow configuration is intentionally deferred to a later, behavior-sensitive phase.

## Runtime files under `data/`

Current files are preserved and tracked in this phase:

- `data/processed_emails.json`
- `data/sender_rules.json`
- `data/threat_audit_log.json`
- `data/user_feedback.csv`

New local runtime-only outputs should go under `data/runtime/` (ignored by Git).

## Model artifacts under `models/`

Current serialized model and metrics artifacts are preserved in Phase 1:

- `models/spam_classifier_nb.pkl`
- `models/spam_classifier_svm.pkl`
- `models/tfidf_vectorizer.pkl`
- `models/metrics.json`

No destructive cleanup or relocation is performed in this phase.

## Datasets under `dataset/`

Existing datasets are intentionally kept in place:

- `dataset/emails-2.csv`
- `dataset/emails.csv`
- `dataset/spam.csv`

Any future migration to external data hosting or LFS is intentionally deferred.
