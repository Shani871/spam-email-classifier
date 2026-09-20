"""
Gmail IMAP integration module for live email spam detection.
Connects securely via IMAP SSL to fetch recent inbox messages, extract bodies,
and run them through the Spam Email Classifier pipeline.
"""

import imaplib
import email
from email.header import decode_header
import re
from typing import List, Dict, Any

from src.predict import predict_email


def decode_str(header_val: Any) -> str:
    """Safely decodes email header string values."""
    if not header_val:
        return ""
    decoded_parts = decode_header(header_val)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(encoding or "utf-8", errors="ignore"))
            except Exception:
                result.append(part.decode("latin1", errors="ignore"))
        else:
            result.append(str(part))
    return " ".join(result)


def extract_body(msg) -> str:
    """Extracts plain text or clean text from an email message object."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="ignore") + "\n"
            elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    html = payload.decode("utf-8", errors="ignore")
                    # Strip basic HTML tags
                    clean = re.sub(r'<[^>]+>', ' ', html)
                    body += clean + "\n"
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            content_type = msg.get_content_type()
            if content_type == "text/html":
                clean = re.sub(r'<[^>]+>', ' ', payload.decode("utf-8", errors="ignore"))
                body = clean
            else:
                body = payload.decode("utf-8", errors="ignore")

    return re.sub(r'\s+', ' ', body).strip()


def scan_gmail_inbox(
    email_address: str,
    app_password: str,
    folder: str = "INBOX",
    max_emails: int = 10,
    only_unread: bool = False,
    model_type: str = "nb"
) -> List[Dict[str, Any]]:
    """
    Connects to Gmail via IMAP SSL, fetches recent messages,
    and runs them through the Spam Classifier.

    Returns a list of classified email dictionaries.
    """
    clean_email = email_address.strip()
    clean_password = app_password.replace(" ", "").strip()

    if not clean_email or not clean_password:
        raise ValueError("Both email address and 16-character App Password are required.")

    # Connect to Gmail IMAP server
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    except Exception as e:
        raise ConnectionError(f"Could not connect to Gmail IMAP server: {e}")

    try:
        mail.login(clean_email, clean_password)
    except imaplib.IMAP4.error as e:
        raise PermissionError(
            "Gmail login failed. Please ensure:\n"
            "1. 2-Step Verification is turned ON in your Google Account.\n"
            "2. You are using a 16-character App Password (not your normal Gmail password).\n"
            f"Details: {e}"
        )

    try:
        status, _ = mail.select(folder)
        if status != "OK":
            raise ValueError(f"Could not access folder '{folder}'. Available folders usually include: INBOX, [Gmail]/Spam")

        search_criteria = "UNSEEN" if only_unread else "ALL"
        status, search_data = mail.search(None, search_criteria)
        if status != "OK":
            return []

        email_ids = search_data[0].split()
        if not email_ids:
            return []

        # Get latest N emails (newest first)
        recent_ids = email_ids[-max_emails:][::-1]
        results = []

        for e_id in recent_ids:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            if res != "OK" or not msg_data or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_str(msg.get("Subject", "(No Subject)"))
            sender = decode_str(msg.get("From", "(Unknown Sender)"))
            date_str = msg.get("Date", "")
            body = extract_body(msg)

            # Combined content for NLP classification
            full_text = f"Subject: {subject}\n\n{body}"
            pred = predict_email(full_text, model_type=model_type)

            results.append({
                "id": e_id.decode("utf-8", errors="ignore"),
                "subject": subject,
                "sender": sender,
                "date": date_str,
                "body_preview": body[:180] + ("..." if len(body) > 180 else ""),
                "full_text": full_text,
                "prediction": pred["label"],
                "confidence": pred["confidence"],
                "prob_spam": pred["prob_spam"],
                "prob_ham": pred["prob_ham"],
                "is_spam": pred["is_spam"],
                "key_features": pred["key_features"]
            })

        return results

    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass
