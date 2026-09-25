"""
Tests for src/gmail_api.py OAuth Gmail scanner and parsing helpers.
"""

import base64
import pytest
from unittest.mock import patch, MagicMock

from src.gmail_api import decode_base64url, extract_body_from_payload, scan_gmail_with_oauth


def test_decode_base64url_standard():
    test_str = "Hello World, SpamGuard AI test!"
    encoded = base64.urlsafe_b64encode(test_str.encode("utf-8")).decode("utf-8")
    assert decode_base64url(encoded) == test_str


def test_decode_base64url_unpadded():
    test_str = "Antigravity Streamlit Auth"
    # Create urlsafe base64 without padding
    encoded = base64.urlsafe_b64encode(test_str.encode("utf-8")).decode("utf-8").rstrip("=")
    assert decode_base64url(encoded) == test_str


def test_decode_base64url_empty_and_invalid():
    assert decode_base64url("") == ""
    assert decode_base64url(None) == ""


def test_extract_body_from_plain_payload():
    text = "Important security alert from PayPal."
    b64 = base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")
    payload = {
        "mimeType": "text/plain",
        "body": {"data": b64}
    }
    extracted = extract_body_from_payload(payload)
    assert "Important security alert" in extracted


def test_extract_body_from_html_payload():
    html_text = "<p>Please <b>verify</b> your bank details.</p>"
    b64 = base64.urlsafe_b64encode(html_text.encode("utf-8")).decode("utf-8")
    payload = {
        "mimeType": "text/html",
        "body": {"data": b64}
    }
    extracted = extract_body_from_payload(payload)
    assert "verify" in extracted
    assert "<p>" not in extracted


def test_extract_body_from_multipart_payload():
    plain_text = "Plain text body content."
    b64 = base64.urlsafe_b64encode(plain_text.encode("utf-8")).decode("utf-8")
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": b64}
            }
        ]
    }
    extracted = extract_body_from_payload(payload)
    assert extracted == plain_text


def test_scan_gmail_with_oauth_missing_token():
    with pytest.raises(ValueError, match="Valid Google OAuth access token is required"):
        scan_gmail_with_oauth(access_token="")


@patch("requests.get")
def test_scan_gmail_with_oauth_expired_token(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_get.return_value = mock_resp

    with pytest.raises(PermissionError, match="Access token expired or invalid"):
        scan_gmail_with_oauth(access_token="fake_token_123")


@patch("requests.get")
def test_scan_gmail_with_oauth_empty_inbox(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messages": []}
    mock_get.return_value = mock_resp

    res = scan_gmail_with_oauth(access_token="valid_token_xyz")
    assert res == []


def test_scan_gmail_with_oauth_signed_in_token():
    with pytest.raises(ValueError, match="Account is signed in for identity only"):
        scan_gmail_with_oauth(access_token="signed_in")


@patch("requests.get")
def test_scan_gmail_with_oauth_forbidden_403(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp

    with pytest.raises(PermissionError, match="HTTP 403 Forbidden"):
        scan_gmail_with_oauth(access_token="test_token_403")
