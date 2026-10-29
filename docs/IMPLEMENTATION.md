# Implementation record

| Step | Delivered | Verification and remaining setup |
|---|---|---|
| Foundation & Storage | Private account storage with cross-process `fcntl.flock` transactional file locks, session workers, secure OIDC callback, stable IMAP UIDs, feedback ingestion, candidate gates, atomic activation and rollback via `.release.lock`. | Automated account, training, action-failure, and rollback tests pass (131 tests). Configure Google credentials before live authentication testing. |
| Three-task interface | Check a message → Understand the warning → Take action, with separate Advanced and Settings pages. | Headless journey tests plus browser inspection. Input, results, and privacy preferences survive navigation. |
| UI/UX | Native theme, readable forms, evidence cards, plain labels, prominent next-step action, clear empty/error states, indicators accompanied by text. | Phone viewport verified; native accessible controls used. No formal WCAG compliance audit claimed. |
| Email evidence & .eml parsing | Bounded `.eml` parsing, plain-text preview, preserved hidden link destinations, escaped sentence highlights and separate interpretation; spam and scam indicators presented separately. | Synthetic multipart email tested. Uploaded header claims remain unverified; attachment contents are not scanned. |
| Conversation comparison | Compare earlier and newer messages: sender address & lookalike domains, reply routing, payment details (UPI/IBAN/crypto/bank without false positives), same-domain & cross-domain link changes, sensitive requests (with negation handling: "never share OTP" is recognized as safety reminder, not credential harvesting). | Automated regression tests in `test_conversation_comparison.py`. Framed as reasons to verify out-of-band. |
| Consent-based admin queue | Multi-user administrator review queue for explicitly consented corrections only (`consent_given=True`). Missing consent defaults to `False`. Approvals, rejections, consent withdrawals, and deletions without exposing private submissions. Training gate strictly uses approved, consented entries. | Verified in `test_admin_queue.py` and `test_privacy_and_releases.py`. Deleting feedback purges records but cannot excise weights from existing released models without retraining/rollback. |
| Modern detection evaluation | Realistic benchmark dataset with 29 scenarios including Hindi & Hinglish, urgent but legitimate notices (maintenance, utility notices, safety bulletins), and modern scams. Separate reporting for missed scams, false warnings, high-risk false alarms, and unassessed items. | Benchmarked in `test_detection_evaluation.py`. 100% scam detection on benchmark with 0 high-risk false alarms. Clearly labeled as synthetic. |
| Multilingual integration | English, Hindi, and Hinglish localized assessment summaries, badges, comparison differences, and recovery guidance. Technical message evidence preserved in original form. | Verified in `test_multilingual.py`. Clear disclosures on rule-based nature and ML confidence calibration limits. |
| Monitoring & backup privacy | Operational monitoring connected to message checks, scans, and inbox actions without logging payloads or credentials. 5 MB / 5-file log rotation with 14-day retention. Backup archive creation, tombstone tracking on deletion, and restore verification. Runtime logs and backups ignored in `.gitignore`. | Verified in `test_deployment_readiness.py`. |
| Local images & QR | Editable local OCR output, QR decoding without opening destinations, Hindi/Hinglish labels and recovery guidance. | Verified in `test_image_checks.py`. Requires system Tesseract for non-macOS OCR. |

## Deployment work that requires configuration or separate validation

- Register/configure Google OIDC and Gmail permissions in `.streamlit/secrets.toml`; complete Google verification as applicable. Live Gmail status remains pending configuration.
- Configure administrator emails in `[app].admin_emails` to authorize admin review queues.
- Run live Gmail scanning, move, and undo tests against an authorized mailbox once credentials are provided.
- For high-volume multi-process production deployments across separate nodes, migrate JSON account storage to a managed transactional database (e.g., PostgreSQL).
- Maintain off-site backups with encryption-at-rest for production hosts.

Read [SETUP.md](SETUP.md) and [DEPLOYMENT.md](DEPLOYMENT.md) for configuration details and operational guidelines.

