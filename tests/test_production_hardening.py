"""Rate limiting, IMAP endpoint safety, start-up configuration and output escaping."""
import importlib.util
from pathlib import Path
import ssl
import tarfile
import tomllib
from unittest.mock import Mock

import pytest

from src.rate_limit import RateLimiter, RateLimitExceeded
from src import gmail_scanner
from src.gmail_scanner import validate_imap_endpoint, open_imap_connection, verify_inbox_connection

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rate_limiter_blocks_then_recovers_after_window():
    now = [0.0]
    limiter = RateLimiter({"check": (3, 60)}, clock=lambda: now[0])
    for _ in range(3):
        limiter.hit("check", "caller")
    with pytest.raises(RateLimitExceeded) as blocked:
        limiter.hit("check", "caller")
    assert 1 <= blocked.value.retry_after <= 60
    limiter.hit("check", "someone-else")
    now[0] = 61.0
    limiter.hit("check", "caller")


def test_rate_limit_error_is_a_value_error_with_a_plain_message():
    error = RateLimitExceeded("check", 12.2)
    assert isinstance(error, ValueError)
    assert "13 seconds" in str(error)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1"])
def test_custom_imap_host_resolving_to_private_address_is_rejected(monkeypatch, address):
    family = 10 if ":" in address else 2
    monkeypatch.setattr(gmail_scanner.socket, "getaddrinfo", lambda *a, **k: [(family, 1, 6, "", (address, 993))])
    with pytest.raises(ValueError, match="private or reserved"):
        validate_imap_endpoint("mail.internal.example", 993)


def test_custom_imap_port_and_host_syntax_are_restricted(monkeypatch):
    monkeypatch.setattr(gmail_scanner.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 993))])
    validate_imap_endpoint("mail.example.com", 993)
    with pytest.raises(ValueError, match="port 22"):
        validate_imap_endpoint("mail.example.com", 22)
    with pytest.raises(ValueError, match="valid IMAP server name"):
        validate_imap_endpoint("mail.example.com/../x", 993)


def test_imap_connection_verifies_certificates_and_sets_timeout(monkeypatch):
    opened = Mock()
    monkeypatch.setattr(gmail_scanner.imaplib, "IMAP4_SSL", opened)
    open_imap_connection("imap.gmail.com", 993)
    context = opened.call_args.kwargs["ssl_context"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert opened.call_args.kwargs["timeout"] > 0


def test_verify_connection_reports_blocked_endpoint_without_connecting(monkeypatch):
    opened = Mock()
    monkeypatch.setattr(gmail_scanner.imaplib, "IMAP4_SSL", opened)
    monkeypatch.setattr(gmail_scanner.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 993))])
    result = verify_inbox_connection("user@corp.example", "secret-password", imap_host="imap.corp.example", imap_port=993)
    assert result["success"] is False and result["error_type"] == "ENDPOINT_NOT_ALLOWED"
    opened.assert_not_called()


def test_render_secrets_is_valid_toml_and_escapes_values():
    entrypoint = load_script("container_entrypoint")
    content = entrypoint.render_secrets({
        "GOOGLE_CLIENT_ID": "id.apps.googleusercontent.com", "GOOGLE_CLIENT_SECRET": 'se"cret\\value',
        "SPAMGUARD_PUBLIC_URL": "https://spamguard.example.com/", "SPAMGUARD_COOKIE_SECRET": "a" * 64,
        "SPAMGUARD_ADMIN_EMAILS": "admin@example.com, second@example.com", "SPAMGUARD_ENABLE_GMAIL_ACTIONS": "1"})
    parsed = tomllib.loads(content)
    assert parsed["auth"]["redirect_uri"] == "https://spamguard.example.com/oauth2callback"
    assert parsed["auth"]["google"]["client_secret"] == 'se"cret\\value'
    assert "gmail.readonly" in parsed["auth"]["google"]["client_kwargs"]["scope"]
    assert "gmail.modify" in parsed["auth"]["googleactions"]["client_kwargs"]["scope"]
    assert parsed["app"]["admin_emails"] == ["admin@example.com", "second@example.com"]


def test_render_secrets_guest_mode_and_misconfiguration():
    entrypoint = load_script("container_entrypoint")
    assert entrypoint.render_secrets({}) == ""
    base = {"GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "secret", "SPAMGUARD_PUBLIC_URL": "https://a.example", "SPAMGUARD_COOKIE_SECRET": "b" * 40}
    for broken in ({"SPAMGUARD_COOKIE_SECRET": "short"}, {"SPAMGUARD_COOKIE_SECRET": "REPLACE-WITH-A-LONG-RANDOM-SECRET-VALUE"},
                   {"SPAMGUARD_PUBLIC_URL": "http://a.example"}, {"GOOGLE_CLIENT_SECRET": ""}):
        with pytest.raises(ValueError):
            entrypoint.render_secrets({**base, **broken})


def test_local_admin_switch_is_ignored_in_production(monkeypatch):
    from src import ui_shared, active_learning
    monkeypatch.setenv("SPAMGUARD_LOCAL_ADMIN", "1")
    monkeypatch.setenv("SPAMGUARD_ENV", "production")
    assert ui_shared.local_admin_enabled() is False
    monkeypatch.setattr(ui_shared, "is_admin", lambda: False)
    assert active_learning.is_authorized_admin() is False
    monkeypatch.delenv("SPAMGUARD_ENV")
    assert ui_shared.local_admin_enabled() is True


def test_markdown_in_email_fields_is_neutralised():
    from src.ui_shared import md_escape
    escaped = md_escape("![pixel](http://tracker.example/p.png) [click](http://evil.example) `code`\nnext")
    assert "![" not in escaped and "](" not in escaped and "\n" not in escaped
    assert escaped.count("\\") >= 8


def test_word_count_reconstructions_are_detected_but_messages_are_not():
    from src.train import is_bow_reconstruction
    assert is_bow_reconstruction("the the the the to to to ect ect and for for of a a a a in in on is i i i be will")
    assert is_bow_reconstruction("ect a a i s e e d d t j l day b o c c r h u id y rd card car")
    assert not is_bow_reconstruction("ok lar joking wif u oni")
    assert not is_bow_reconstruction("Subject: meeting notes  please review the attached agenda before monday .")
    assert not is_bow_reconstruction("no no no no i will not go")


def test_choose_threshold_limits_false_positives_on_legitimate_mail():
    import numpy as np
    from src.train import choose_threshold
    rng = np.random.default_rng(0)
    ham = rng.uniform(0.0, 0.9, 1000)
    spam = rng.uniform(0.6, 1.0, 1000)
    y = np.r_[np.zeros(1000), np.ones(1000)]
    threshold = choose_threshold(y, np.r_[ham, spam], target_fpr=0.01)
    assert (ham >= threshold).mean() <= 0.01
    assert 0.5 <= threshold < 0.99
    assert choose_threshold(np.zeros(3), np.array([0.1, 0.2, 0.3]), target_fpr=0.01) == 0.5


def test_prediction_uses_threshold_recorded_with_the_model(tmp_path, monkeypatch):
    import json, shutil
    from src import predict
    for name in ("spam_classifier_svm.pkl", "metrics.json"):
        shutil.copy(ROOT / "models" / name, tmp_path / name)
    metrics = json.loads((tmp_path / "metrics.json").read_text())
    metrics["models"]["svm"]["decision_threshold"] = 0.999
    (tmp_path / "metrics.json").write_text(json.dumps(metrics))
    monkeypatch.setattr(predict, "MODELS_DIR", str(tmp_path))
    predict._LOADED_MODELS.clear()
    try:
        result = predict.predict_email("Congratulations you won a free cash prize, claim now", "svm")
        assert result["threshold"] == 0.999
        assert result["is_spam"] is (result["prob_spam"] >= 0.999)
    finally:
        predict._LOADED_MODELS.clear()


def test_external_corpora_loader_reads_label_subject_body(tmp_path, monkeypatch):
    import pandas as pd
    from src import train
    folder = tmp_path / "zenodo"
    folder.mkdir()
    pd.DataFrame({"subject": ["Hello", "WIN NOW"], "body": ["Meeting notes attached for review.", "Claim your free prize today at our site"],
                  "label": [0, 1]}).to_csv(folder / "Ling.csv", index=False)
    monkeypatch.setattr(train, "EXTERNAL_DIR", str(folder))
    rows = train.load_external_corpora()
    assert sorted(rows["label"]) == ["ham", "spam"]
    assert set(rows["source"]) == {"ling"}
    assert rows["text"].str.startswith("Subject: ").all()
    monkeypatch.setattr(train, "EXTERNAL_DIR", str(tmp_path / "missing"))
    assert train.load_external_corpora().empty


GMAIL_AUTH = ("mx.google.com; dkim=pass header.i=@bank.example header.s=s1; "
              "spf=pass (google.com: domain of alerts@bank.example designates 192.0.2.1 as permitted sender) smtp.mailfrom=alerts@bank.example; "
              "dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=bank.example")


def test_provider_verification_uses_only_the_topmost_authentication_results():
    from src.email_content import provider_sender_verification
    ok = provider_sender_verification([("Delivered-To", "me@example.com"), ("Authentication-Results", GMAIL_AUTH)], "Bank <alerts@bank.example>")
    assert ok["verified"] and ok["domain"] == "bank.example" and ok["reported_by"] == "mx.google.com"
    forged_below = [("Authentication-Results", "mx.google.com; dkim=none; spf=softfail; dmarc=fail header.from=bank.example"),
                    ("Authentication-Results", GMAIL_AUTH)]
    assert not provider_sender_verification(forged_below, "alerts@bank.example")["verified"]
    assert not provider_sender_verification([("Authentication-Results", GMAIL_AUTH)], "alerts@bank-example.top")["verified"]
    assert not provider_sender_verification([], "alerts@bank.example")["verified"]


def test_classifier_points_follow_threshold_and_sender_verification():
    from src.ai_threat_intelligence import classifier_points
    assert classifier_points(0.0, 0.9) == 0
    assert abs(classifier_points(0.9, 0.9) - 20) < 1e-9
    assert classifier_points(0.89, 0.9) < 20
    assert abs(classifier_points(1.0, 0.9) - 45) < 1e-9
    assert abs(classifier_points(1.0, 0.9, sender_verified=True) - 18) < 1e-9


def test_verified_sender_lowers_wording_score_but_not_link_warnings(monkeypatch):
    from src import ai_threat_intelligence
    from src.scam_assistant import check_message

    def confident_spam(text, model_type="svm"):
        return {"assessable": True, "label": "Spam", "is_spam": True, "confidence": 1.0, "prob_spam": 1.0,
                "prob_ham": 0.0, "model_type": model_type, "cleaned_text": text, "key_features": [], "threshold": 0.9}

    monkeypatch.setattr(ai_threat_intelligence, "predict_email", confident_spam)
    alert = "Subject: Payment Received\n\nRs. 12810.83 has been credited to your account via NEFT. For queries call customer support."
    assert check_message(alert, sender="alerts@bank.example")["assessment"] == "Needs verification"
    verified = check_message(alert, sender="alerts@bank.example", sender_verified=True)
    assert verified["assessment"] == "No strong warning found" and verified["sender_verified"]
    phish = "Subject: Verify now\n\nYour account is suspended. Verify immediately at http://paypa1-security-update.com/login"
    assert check_message(phish, sender="alerts@bank.example", sender_verified=True)["assessment"] == "High risk"


def test_job_wording_asks_for_verification_unless_provider_verified_sender():
    from src.scam_assistant import check_message
    alert = "Subject: Acme is hiring a Python Developer\n\nAcme Python Developer: we are looking for engineers. View job and apply on our careers page."
    assert check_message(alert, sender="jobalerts@jobs.example")["assessment"] == "Needs verification"
    assert check_message(alert, sender="jobalerts@jobs.example", sender_verified=True)["assessment"] == "No strong warning found"
    assert check_message(alert, category="Job or internship", sender="jobalerts@jobs.example", sender_verified=True)["assessment"] == "Needs verification"
    scam = "Subject: Job offer\n\nYou are hired. Pay the registration fee of Rs 2000 to confirm your joining."
    assert check_message(scam, sender="hr@jobs.example", sender_verified=True)["assessment"] != "No strong warning found"


def test_feedback_retraining_refuses_without_the_public_corpora(tmp_path, monkeypatch):
    import json
    from src import active_learning, train
    (tmp_path / "metrics.json").write_text(json.dumps({"source_counts": {"ceas_08": 10, "sms": 5}}))
    monkeypatch.setattr(active_learning, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(train, "EXTERNAL_DIR", str(tmp_path / "absent"))
    assert active_learning.missing_training_corpora() == ["CEAS_08"]
    monkeypatch.setattr(active_learning, "get_trainable_feedback", lambda: [{}] * 10)
    outcome = active_learning._retrain(5)
    assert outcome["success"] is False and "fetch_public_corpora" in outcome["message"]
