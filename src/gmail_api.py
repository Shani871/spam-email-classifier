"""
Official Gmail REST API scanner using OAuth 2.0 / Firebase Access Tokens.
Fetches recent inbox messages via HTTPS, decodes headers & bodies,
and evaluates Spam/Ham probability with the ML model.
"""

import base64
import re
import requests
from typing import List, Dict, Any

from src.predict import predict_email


def decode_base64url(data_str: str) -> str:
    """Decodes URL-safe base64 string from Gmail API."""
    if not data_str:
        return ""
    try:
        # Add padding if needed
        padding = len(data_str) % 4
        if padding:
            data_str += "=" * (4 - padding)
        decoded_bytes = base64.urlsafe_b64decode(data_str)
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_body_from_payload(payload: dict) -> str:
    """Recursively extracts text or HTML body from Gmail API payload dictionary."""
    body_text = ""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if body_data and mime_type.startswith("text/"):
        decoded = decode_base64url(body_data)
        if mime_type == "text/html":
            decoded = re.sub(r'<[^>]+>', ' ', decoded)
        return decoded

    parts = payload.get("parts", [])
    for part in parts:
        part_mime = part.get("mimeType", "")
        part_body_data = part.get("body", {}).get("data", "")
        if part_mime == "text/plain" and part_body_data:
            return decode_base64url(part_body_data)
        elif part_mime == "text/html" and part_body_data and not body_text:
            raw_html = decode_base64url(part_body_data)
            body_text = re.sub(r'<[^>]+>', ' ', raw_html)
        elif "parts" in part:
            sub_body = extract_body_from_payload(part)
            if sub_body:
                return sub_body

    return body_text


def scan_gmail_with_oauth(
    access_token: str,
    max_emails: int = 10,
    only_unread: bool = False,
    model_type: str = "nb"
) -> List[Dict[str, Any]]:
    """
    Fetches emails using Google OAuth / Firebase Access Token and classifies them.
    """
    if not access_token:
        raise ValueError("Valid Google OAuth access token is required.")
    if access_token == "signed_in":
        raise ValueError(
            "Account is signed in for identity only without Gmail API access. "
            "Please sign out and sign in with 'Request Gmail scan permission' checked, or connect via Method A (App Password)."
        )

    headers = {"Authorization": f"Bearer {access_token}"}
    query = "in:inbox is:unread" if only_unread else "in:inbox"

    url_list = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    params = {
        "maxResults": max_emails,
        "q": query
    }

    resp = requests.get(url_list, headers=headers, params=params, timeout=15)
    if resp.status_code == 401:
        raise PermissionError("Access token expired or invalid. Please sign in with Google again.")
    elif resp.status_code == 403:
        raise PermissionError(
            "Google blocked access to Gmail (HTTP 403 Forbidden). "
            "This account needs to be added to Google Cloud 'Test Users', or you can connect instantly via Method A (App Password)."
        )
    elif resp.status_code != 200:
        raise RuntimeError(f"Gmail API error ({resp.status_code}): {resp.text}")

    data = resp.json()
    messages_meta = data.get("messages", [])
    if not messages_meta:
        return []

    results = []

    for item in messages_meta:
        msg_id = item.get("id")
        msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full"
        msg_resp = requests.get(msg_url, headers=headers, timeout=10)
        if msg_resp.status_code != 200:
            continue

        msg_json = msg_resp.json()
        payload = msg_json.get("payload", {})
        headers_list = payload.get("headers", [])

        # Extract Subject, From, Date
        subject = "(No Subject)"
        sender = "(Unknown Sender)"
        date_str = ""

        for h in headers_list:
            name_lower = h.get("name", "").lower()
            if name_lower == "subject":
                subject = h.get("value", subject)
            elif name_lower == "from":
                sender = h.get("value", sender)
            elif name_lower == "date":
                date_str = h.get("value", date_str)

        body = extract_body_from_payload(payload)
        snippet = msg_json.get("snippet", "")
        if not body.strip():
            body = snippet

        from src.email_content import payload_metadata
        attachments, html_body = payload_metadata(payload)
        security_headers = {h["name"]: h.get("value", "") for h in headers_list}

        # Normalize text
        body = re.sub(r'\s+', ' ', body).strip()
        full_text = f"Subject: {subject}\n\n{body}"

        pred = predict_email(full_text, model_type=model_type)

        results.append({
            "id": msg_id,
            "provider": "gmail",
            "label_ids": msg_json.get("labelIds", []),
            "thread_id": msg_json.get("threadId", ""),
            "full_text": full_text + "\n" + html_body,
            "headers": security_headers,
            "attachments": attachments,
            "subject": subject,
            "sender": sender,
            "date": date_str,
            "body_preview": (body[:180] + "...") if len(body) > 180 else body,
            "snippet": snippet,
            "prediction": pred["label"],
            "confidence": pred["confidence"],
            "prob_spam": pred["prob_spam"],
            "prob_ham": pred["prob_ham"],
            "is_spam": pred["is_spam"],
            "key_features": pred["key_features"]
        })

    from src.monitoring import record_metric, log_security_event, log_error
    try:
        record_metric("inbox_scans")
        log_security_event("INBOX_SCAN", {"provider": "gmail_oauth", "messages_found": len(results)})
    except Exception as err:
        log_error(err, context="gmail_oauth_scan_monitoring")

    return results


def modify_message_labels(access_token, message_id, add, remove):
    """Change only reversible inbox/spam labels; never delete messages."""
    from src.monitoring import record_metric, log_security_event, log_error
    if not access_token or access_token == "signed_in" or not re.fullmatch(r"[A-Za-z0-9_-]+", str(message_id)):
        return {"success": False, "message": "Reconnect and rescan before taking action."}
    if not set(add + remove) <= {"INBOX", "SPAM"}:
        raise ValueError("Only inbox and spam labels can be changed.")
    try:
        response = requests.post(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"addLabelIds": add, "removeLabelIds": remove}, timeout=15)
        if response.status_code == 200:
            record_metric("provider_actions")
            log_security_event("PROVIDER_ACTION_CONFIRMED", {"action": "modify_labels", "message_id": message_id, "add": add, "remove": remove})
            return {"success": True, "message": "Gmail confirmed the change.", "label_ids": response.json().get("labelIds", [])}
        log_security_event("PROVIDER_ACTION_FAILED", {"action": "modify_labels", "status_code": response.status_code})
        return {"success": False, "message": "Gmail did not confirm the change. Reconnect with inbox action permission, then try again."}
    except requests.RequestException as err:
        log_error(err, context="gmail_modify_labels")
        return {"success": False, "message": "Gmail is unavailable. No successful change was recorded."}


def get_message_labels(access_token, message_id):
    if not access_token or access_token == "signed_in" or not re.fullmatch(r"[A-Za-z0-9_-]+", str(message_id)):
        return None
    try:
        response = requests.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                                headers={"Authorization": f"Bearer {access_token}"}, params={"format": "minimal"}, timeout=15)
        return response.json().get("labelIds", []) if response.status_code == 200 else None
    except requests.RequestException:
        return None
