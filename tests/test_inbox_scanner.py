"""
Comprehensive unit tests for the enhanced universal IMAP and inbox scanner module.
"""

from unittest.mock import Mock, patch
import pytest
from src.gmail_scanner import (
    resolve_imap_settings,
    clean_credentials,
    verify_inbox_connection,
    get_simulated_inbox,
    scan_gmail_inbox,
    scan_email_inbox
)


def test_resolve_imap_settings_known_domains():
    host, port, provider = resolve_imap_settings("alice@gmail.com")
    assert host == "imap.gmail.com"
    assert port == 993
    assert "Gmail" in provider

    host, port, provider = resolve_imap_settings("bob@outlook.com")
    assert host == "outlook.office365.com"
    assert "Outlook" in provider

    host, port, provider = resolve_imap_settings("carol@yahoo.com")
    assert host == "imap.mail.yahoo.com"
    assert "Yahoo" in provider

    host, port, provider = resolve_imap_settings("dave@icloud.com")
    assert host == "imap.mail.me.com"
    assert "iCloud" in provider


def test_resolve_imap_settings_custom_host():
    host, port, provider = resolve_imap_settings("user@custom.org", custom_host="mail.custom.org", custom_port=995)
    assert host == "mail.custom.org"
    assert port == 995
    assert provider == "Custom IMAP"


def test_clean_credentials_gmail():
    email, pwd = clean_credentials(" alice@gmail.com ", "abcd efgh ijkl mnop", "Google Gmail")
    assert email == "alice@gmail.com"
    assert pwd == "abcdefghijklmnop"


def test_clean_credentials_other_provider_preserves_symbols():
    email, pwd = clean_credentials(" bob@outlook.com ", " Complex#Pass_2026! ", "Microsoft Outlook")
    assert email == "bob@outlook.com"
    assert pwd == "Complex#Pass_2026!"


def test_verify_inbox_connection_demo_mode():
    result = verify_inbox_connection("demo@spamguard.local", "demo")
    assert result["success"] is True
    assert result["provider"] == "SpamGuard Demo Feed"
    assert len(result["folders"]) >= 1
    assert result["total_count"] == 5


def test_verify_inbox_connection_missing_credentials():
    result = verify_inbox_connection("", "")
    assert result["success"] is False
    assert result["error_type"] == "MISSING_CREDENTIALS"


def test_get_simulated_inbox():
    emails = get_simulated_inbox(count=3, model_type="svm")
    assert len(emails) == 3
    assert emails[0]["id"] == "demo-001"
    assert "prediction" in emails[0]
    assert "headers" in emails[0]


def test_scan_gmail_inbox_demo_mode():
    emails = scan_gmail_inbox("demo@spamguard.local", "demo", max_emails=2, model_type="svm")
    assert len(emails) == 2
    assert "body_preview" in emails[0]
