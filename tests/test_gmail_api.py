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


from src.gmail_api import modify_message_labels, get_message_labels


def test_modify_message_labels_rejects_dangerous_labels():
    with pytest.raises(ValueError, match="Only inbox and spam labels can be changed"):
        modify_message_labels("test_token", "msg123", ["TRASH"], [])

    with pytest.raises(ValueError, match="Only inbox and spam labels can be changed"):
        modify_message_labels("test_token", "msg123", ["DELETE"], ["INBOX"])


def test_modify_message_labels_invalid_id():
    res = modify_message_labels("test_token", "bad/id!$", ["SPAM"], ["INBOX"])
    assert res["success"] is False
    assert "Reconnect and rescan" in res["message"]


@patch("requests.post")
def test_modify_message_labels_provider_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "msg_001", "labelIds": ["SPAM"]}
    mock_post.return_value = mock_resp

    result = modify_message_labels("valid_token", "msg_001", ["SPAM"], ["INBOX"])
    assert result["success"] is True
    assert "Gmail confirmed the change" in result["message"]
    assert result["label_ids"] == ["SPAM"]


@patch("requests.post")
def test_modify_message_labels_provider_failure(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Insufficient permissions"
    mock_post.return_value = mock_resp

    result = modify_message_labels("valid_token", "msg_001", ["SPAM"], ["INBOX"])
    assert result["success"] is False
    assert "Gmail did not confirm the change" in result["message"]


@patch("requests.get")
def test_get_message_labels_flow(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "msg_001", "labelIds": ["INBOX", "UNREAD"]}
    mock_get.return_value = mock_resp

    labels = get_message_labels("valid_token", "msg_001")
    assert labels == ["INBOX", "UNREAD"]


@patch("requests.post")
@patch("requests.get")
def test_gmail_action_and_undo_cycle(mock_get, mock_post):
    # Step 1: Query before state
    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"id": "msg_999", "labelIds": ["INBOX"]}
    mock_get.return_value = get_resp

    before_labels = get_message_labels("valid_token", "msg_999")
    assert before_labels == ["INBOX"]

    # Step 2: Move to Spam
    post_move_resp = MagicMock()
    post_move_resp.status_code = 200
    post_move_resp.json.return_value = {"id": "msg_999", "labelIds": ["SPAM"]}
    mock_post.return_value = post_move_resp

    move_outcome = modify_message_labels("valid_token", "msg_999", ["SPAM"], ["INBOX"])
    assert move_outcome["success"] is True
    assert move_outcome["label_ids"] == ["SPAM"]

    # Step 3: Undo move (restore original INBOX, remove SPAM)
    post_undo_resp = MagicMock()
    post_undo_resp.status_code = 200
    post_undo_resp.json.return_value = {"id": "msg_999", "labelIds": ["INBOX"]}
    mock_post.return_value = post_undo_resp

    original = set(before_labels) & {"SPAM", "INBOX"}
    undo_outcome = modify_message_labels("valid_token", "msg_999", sorted(original), sorted({"SPAM", "INBOX"} - original))
    assert undo_outcome["success"] is True
    assert undo_outcome["label_ids"] == ["INBOX"]

