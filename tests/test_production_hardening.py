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


def test_backup_archives_contents_of_linked_state_directories(tmp_path):
    backup = load_script("backup_and_retention")
    state = tmp_path / "state" / "users" / "abc"
    state.mkdir(parents=True)
    (state / "history.json").write_text("[]", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "users").symlink_to(tmp_path / "state" / "users")
    archive = backup.create_backup_archive(data_dir=data, backups_dir=tmp_path / "backups")
    with tarfile.open(archive) as tar:
        assert "data/users/abc/history.json" in tar.getnames()


def test_word_count_reconstructions_are_detected_but_messages_are_not():
    from src.train import is_bow_reconstruction
    assert is_bow_reconstruction("the the the the to to to ect ect and for for of a a a a in in on is i i i be will")
    assert is_bow_reconstruction("ect a a i s e e d d t j l day b o c c r h u id y rd card car")
    assert not is_bow_reconstruction("ok lar joking wif u oni")
    assert not is_bow_reconstruction("Subject: meeting notes  please review the attached agenda before monday .")
    assert not is_bow_reconstruction("no no no no i will not go")
