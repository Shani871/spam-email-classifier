# SpamGuard AI setup

Run the app locally with `.venv/bin/python -m streamlit run app.py`. Install `requirements.txt` into your virtual environment first. Existing baseline models are retained; if model artifacts are absent, run `.venv/bin/python src/train.py` explicitly. The app never silently retrains during a message check.

## Secure Google connection

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, fill in your own Google OIDC credentials and a strong random cookie secret, enable the Gmail API, and register the `/oauth2callback` redirect URI. Restart the app after configuring secrets. The default Google provider requests read-only Gmail access; `googleactions` is an optional provider for user-initiated message label changes. Tokens are accessed on the server through `st.user.tokens`, not placed in page URLs. Reauthenticate when Gmail authorization expires. No refresh tokens are persisted by this app.

Google requires verification for public apps requesting restricted Gmail scopes. Read the [official scope and verification guidance](https://developers.google.com/workspace/gmail/api/auth/scopes). A local configuration template does not establish production verification or consent.

The old edited Firebase project configuration is preserved in `docs/firebase-config.previous.json` as migration context. It is not executed. The old popup login and token-bearing URL redirects have been replaced.

## Email-file analysis

Choose **Email file** on the checking screen and upload an exported `.eml` message (up to 10 MB). The parser retains readable text, HTML link destinations, headers and attachment metadata. The preview displays plain text; it does not load remote images, open links, or extract attachment files. Message text is limited to 100,000 characters, with bounds on MIME depth and part count. Unsupported or malformed files show an error or coverage warning.

Uploaded authentication headers are unverified claims. Attachment checks use filenames and metadata, not malware scanning. Warning cards show escaped source sentences with the matched wording highlighted, followed by the interpretation and next step.

## Local screenshot and QR analysis

Install `requirements-images.txt` for image features. QR decoding uses OpenCV and never opens decoded destinations. OCR uses Tesseract when installed, with Apple Vision as a local fallback on macOS. On Linux/Windows, install the Tesseract executable and desired language data separately. Hindi OCR requires `hin` data or platform language support. Missing engines, unclear images, and unreadable QR content produce visible warnings and permit manual text entry. Review extracted text before checking it. Image size is limited to 10 MB and 20 million pixels.

## Feedback and model releases

List verified administrator email addresses in `[app].admin_emails`. Without authentication configured, a trusted local operator can launch the app with `SPAMGUARD_LOCAL_ADMIN=1`; do not enable this on a public deployment.

Corrections are stored privately and automatically redacted for email addresses and phone numbers. Users are presented with a redaction review field to inspect and remove any remaining personal names, physical addresses, or confidential details before submitting. Explicit user consent (`consent_given`) is required before feedback is saved. Submissions remain private and cannot enter administrator review queues or model candidate training without explicit consent.

Deleting account data in Settings permanently purges saved feedback records. However, deleting a correction does not remove its influence from a model version that has already been trained on it; model rollback or retraining is required. At least five approved corrections are required for a candidate release. Training merges approved feedback into baseline training data, excluding normalized holdout texts. The candidate must retain spam precision and recall within 0.5 percentage points of the current model on a fixed baseline holdout. This is a regression gate, not a new independent real-world evaluation. Candidate artifacts are stored in version directories. A single atomic manifest activates both models; the previous version can be restored.

Models are shared across accounts; releasing them requires explicit administrator review and approval. An administrator must individually inspect and approve consented feedback entries before retraining.

## Privacy and retention

Message/image checks run on the app server. No external AI calls are made in the primary flow. Submitted content is held in the private Streamlit session by default. Optional saved summaries exclude message bodies and sender details, expire after 1/7/30 days, and retain at most 100 entries. Corrections expire after 30 days. Expired account records are pruned on access and by hourly cleanup while the app receives requests; schedule `scripts/purge_private_data.py` externally if exact cleanup while idle is required. Deletion removes the current account's saved rules, corrections, summaries, and clears session content and connection details. Account folders use hashed verified OIDC identities; anonymous users receive separate random session identities. Guests cannot recover saved records after the session ends.

Storage writes are atomic with a process-level lock. Deploy as a single app process on a persistent volume. Multi-process/distributed deployments need a transactional database and coordinated model-release locks. There is no encryption-at-rest service in this local implementation; use encrypted host storage and access controls in production.

## Monitoring and inbox actions

The monitor has a private worker for each session. Demo and live modes are explicitly labeled. It never moves messages automatically and stops after 15 minutes. Logs remain in memory, bounded to 500 entries. Background checks require an app-password connection; OAuth scanning is available on the primary checking screen.

IMAP reading uses stable UIDs, UIDVALIDITY and `BODY.PEEK[]` in a read-only mailbox, so checks do not mark unread emails read. The compatibility move helper refuses unsupported moves and does not expunge unrelated messages. The UI offers reversible Gmail label actions only for OAuth-connected messages. Gmail must confirm success before it enters the session action history. Undo restores prior inbox/spam labels and leaves unrelated labels alone.

**Live Gmail verification status**: **PENDING live test account configuration**. Full automated mocked tests in `tests/test_gmail_api.py` verify reading, scanning with minimal scopes (`gmail.readonly`), label modification (`gmail.modify` restricted strictly to `INBOX` and `SPAM`), provider failure handling (HTTP 401, 403, and network timeouts), and full reversible undo cycles. Live verification against an authorized Google mailbox remains pending until credentials and registered test users are provided in `.streamlit/secrets.toml`.

## Conversation comparison

Users can compare an earlier message with the current message in an ongoing email thread. The comparison engine analyzes:
1. **Sender address and domain changes**: Detects lookalike domains or unexpected sender changes within a thread.
2. **Reply address routing**: Identifies when `Reply-To` directs answers to an external address or domain different from earlier messages.
3. **Payment detail modifications**: Extracts and compares bank account numbers, IFSC, IBAN, UPI IDs, cryptocurrency wallets, and payment handles.
4. **New link domains**: Flags when fresh external links or unfamiliar domains are introduced mid-thread.
5. **Sensitive information escalation**: Alerts when a message suddenly requests passwords, OTPs, or government identity documents (Aadhaar, PAN, SSN) not requested earlier.

All detected changes are explicitly framed as **reasons to verify independently out-of-band** (e.g. calling an established, known phone number), not automatic proof of fraud. Legitimate organizations legitimately update bank details or assign new account representatives.

## Detection evaluation benchmark

A dedicated benchmark dataset (`data/detection_evaluation_set.json`) tests modern realistic scams and legitimate messages:
- Includes urgent but genuine workplace and infrastructure alerts to rigorously test for false warnings (false positives).
- Evaluates English, Hindi, and Hinglish messages across common fraud archetypes (recruitment fee scams, invoice redirection, utility disconnection threats, OTP harvesting, and pay-to-withdraw task schemes).
- Measures false warnings (genuine messages flagged with high risk) and missed scams (scams given no warning).
- Separates modern threat assessment from historical spam-classifier metrics (which benchmark traditional 2000s bulk spam keywords).
- Explicitly labels synthetic scenarios and disclaims 100% protection claims.

## Multilingual support

SpamGuard AI supports English, Hindi, and Hinglish for risk warnings, assessment badges, and recovery action steps:
- **Consistent terminology**: Key concepts (High risk, Needs verification, No strong warning found, Unable to assess) follow standardized terminology across languages.
- **English fallback**: Any untranslated technical cue or novel evidence item gracefully falls back to English to prevent missing warnings.
- **Language-specific evaluation**: The modern detection benchmark separately measures scams detected, missed scams, and false warnings across English, Hindi, and Hinglish subsets.
- **Honest coverage limitations**: Hindi and Hinglish threat detection relies on keyword patterns and heuristic rule sets. Machine learning confidence scores are primarily calibrated on English benchmark corpora and must not be treated as a mathematical safety guarantee for vernacular communications.

## Coverage limits

Spam classification and heuristic scam risk are separate. Filename checks are not malware scanning; authentication headers are declared provider evidence, not a fresh cryptographic verification. Hindi and Hinglish use rule subsets and translated guidance; full real-world coverage is not claimed. Conversation comparison operates on supplied earlier and current messages; it does not automatically scrape full historical inboxes without user selection.

Official recovery references: [FTC recovery guidance](https://consumer.ftc.gov/articles/what-do-if-you-were-scammed), [FTC job scam guidance](https://consumer.ftc.gov/articles/job-scams), [India cybercrime reporting portal](https://cybercrime.gov.in/).
