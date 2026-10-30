"""
Universal IMAP & Live Email Integration Module for SpamGuard AI.
Supports Google Gmail, Microsoft Outlook/Office 365, Yahoo Mail, Apple iCloud,
Zoho, AOL, and Custom IMAP servers over SSL/TLS.
Fetches inbox messages, decodes headers & bodies, and runs the SpamGuard AI
ML classification & forensics pipeline.
"""

import imaplib
import email
from email.header import decode_header
import re
from typing import List, Dict, Any, Tuple, Optional

from src.predict import predict_email

# Predefined configurations for major email providers
KNOWN_IMAP_PROVIDERS = {
    "gmail.com": ("imap.gmail.com", 993, "Google Gmail"),
    "googlemail.com": ("imap.gmail.com", 993, "Google Gmail"),
    "outlook.com": ("outlook.office365.com", 993, "Microsoft Outlook"),
    "hotmail.com": ("outlook.office365.com", 993, "Microsoft Hotmail"),
    "live.com": ("outlook.office365.com", 993, "Microsoft Live"),
    "msn.com": ("outlook.office365.com", 993, "Microsoft MSN"),
    "office365.com": ("outlook.office365.com", 993, "Microsoft Office 365"),
    "yahoo.com": ("imap.mail.yahoo.com", 993, "Yahoo Mail"),
    "ymail.com": ("imap.mail.yahoo.com", 993, "Yahoo Mail"),
    "myyahoo.com": ("imap.mail.yahoo.com", 993, "Yahoo Mail"),
    "icloud.com": ("imap.mail.me.com", 993, "Apple iCloud"),
    "me.com": ("imap.mail.me.com", 993, "Apple iCloud"),
    "mac.com": ("imap.mail.me.com", 993, "Apple iCloud"),
    "zoho.com": ("imap.zoho.com", 993, "Zoho Mail"),
    "aol.com": ("imap.aol.com", 993, "AOL Mail"),
}


def resolve_imap_settings(
    email_address: str,
    custom_host: str = "",
    custom_port: int = 993
) -> Tuple[str, int, str]:
    """
    Determines the IMAP host, port, and provider name.
    If custom_host is provided, it takes precedence.
    Otherwise, inspects the email domain.
    """
    if custom_host and custom_host.strip():
        port = int(custom_port) if custom_port else 993
        return custom_host.strip(), port, "Custom IMAP"

    email_clean = str(email_address or "").strip().lower()
    domain = email_clean.split("@")[-1] if "@" in email_clean else ""

    if domain in KNOWN_IMAP_PROVIDERS:
        return KNOWN_IMAP_PROVIDERS[domain]

    # Default fallback to Gmail
    return "imap.gmail.com", 993, "Google Gmail / IMAP"


def clean_credentials(email_address: str, app_password: str, provider: str = "") -> Tuple[str, str]:
    """
    Cleans email address and password while preserving valid characters.
    For Gmail 16-character app passwords, strips spaces and hyphens.
    For other providers, preserves symbols and strips whitespace.
    """
    clean_email = re.sub(r'[\s\xa0]+', '', str(email_address or '')).strip()
    raw_pwd = str(app_password or '').strip().replace('\xa0', ' ')

    is_gmail = (
        "gmail" in provider.lower()
        or "google" in provider.lower()
        or clean_email.endswith(("@gmail.com", "@googlemail.com"))
    )

    if is_gmail:
        # Gmail app passwords are 16 letters, commonly copied with spaces (e.g. "abcd efgh ijkl mnop")
        stripped = re.sub(r'[\s\-]+', '', raw_pwd)
        if len(stripped) == 16 and stripped.isalnum():
            return clean_email, stripped

    # For other providers, retain punctuation/symbols but remove outer whitespace and control chars
    clean_pwd = re.sub(r'[\r\n\t]+', '', raw_pwd).strip()
    return clean_email, clean_pwd


def decode_str(header_val: Any) -> str:
    """Safely decodes email header string values."""
    if not header_val:
        return ""
    try:
        decoded_parts = decode_header(header_val)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    result.append(part.decode(encoding or "utf-8", errors="replace"))
                except Exception:
                    result.append(part.decode("latin1", errors="replace"))
            else:
                result.append(str(part))
        return " ".join(result).replace('\xa0', ' ').strip()
    except Exception:
        return str(header_val).replace('\xa0', ' ').strip()


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

    body = body.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', body).strip()


def verify_inbox_connection(
    email_address: str,
    app_password: str,
    imap_host: str = "",
    imap_port: int = 993,
    folder: str = "INBOX"
) -> Dict[str, Any]:
    """
    Live connection test utility that validates credentials, server reachability,
    available folders, and unread email count with rich diagnostic feedback.
    """
    host, port, provider = resolve_imap_settings(email_address, imap_host, imap_port)
    clean_email, clean_pwd = clean_credentials(email_address, app_password, provider)

    if not clean_email or not clean_pwd:
        return {
            "success": False,
            "error_type": "MISSING_CREDENTIALS",
            "message": "Both email address and password are required.",
            "provider": provider,
            "host": host,
            "troubleshooting": "Please provide your email address and app-specific password."
        }

    # Demo mode handling
    if clean_email == "demo@spamguard.local" or clean_pwd == "demo":
        return {
            "success": True,
            "provider": "SpamGuard Demo Feed",
            "host": "localhost",
            "port": 993,
            "email": clean_email,
            "folders": ["INBOX", "Spam", "Archive"],
            "unread_count": 3,
            "total_count": 5,
            "message": "Connected to SpamGuard Demo Mailbox with 5 pre-loaded realistic scenarios."
        }

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(host, port)
    except Exception as exc:
        return {
            "success": False,
            "error_type": "SERVER_UNREACHABLE",
            "message": f"Could not connect to {host}:{port}. ({exc})",
            "provider": provider,
            "host": host,
            "port": port,
            "troubleshooting": (
                f"Verify that your network allows outbound SSL connections to {host} on port {port}. "
                "If using a custom server, ensure the hostname and port are correct."
            )
        }

    try:
        mail.login(clean_email, clean_pwd)
    except imaplib.IMAP4.error as exc:
        troubleshooting = ""
        if "gmail" in provider.lower():
            troubleshooting = (
                "Google requires an App Password for IMAP access:\n"
                "1. Go to https://myaccount.google.com/security\n"
                "2. Ensure 2-Step Verification is ON\n"
                "3. Search for 'App passwords' (or visit https://myaccount.google.com/apppasswords)\n"
                "4. Generate a 16-character password and paste it here."
            )
        elif "outlook" in provider.lower() or "office" in provider.lower():
            troubleshooting = (
                "Microsoft requires 2-Step Verification and an App Password:\n"
                "1. Visit https://account.live.com/proofs/manage/additional\n"
                "2. Under 'App passwords', click 'Create a new app password'.\n"
                "3. Use that app password instead of your normal account password."
            )
        elif "yahoo" in provider.lower():
            troubleshooting = (
                "Yahoo requires a generated App Password:\n"
                "1. Visit https://login.yahoo.com/account/security\n"
                "2. Click 'Generate app password' and use the generated token."
            )
        elif "icloud" in provider.lower():
            troubleshooting = (
                "Apple requires an App-Specific Password:\n"
                "1. Visit https://appleid.apple.com\n"
                "2. Under 'Sign-In and Security', select 'App-Specific Passwords'."
            )
        else:
            troubleshooting = "Check your username, password, and whether your email host requires an App Password."

        return {
            "success": False,
            "error_type": "AUTHENTICATION_FAILED",
            "message": f"Login failed for {clean_email} on {host}: {exc}",
            "provider": provider,
            "host": host,
            "port": port,
            "troubleshooting": troubleshooting
        }
    except Exception as exc:
        return {
            "success": False,
            "error_type": "UNKNOWN_ERROR",
            "message": f"Login error: {exc}",
            "provider": provider,
            "host": host,
            "troubleshooting": "Verify credentials and IMAP server settings."
        }

    # Inspect folders & counts
    folders = ["INBOX"]
    total_count = 0
    unread_count = 0
    try:
        typ, folder_list = mail.list()
        if typ == "OK" and folder_list:
            parsed_folders = []
            for f in folder_list:
                if isinstance(f, bytes):
                    match = re.search(r'"([^"]+)"$|([^\s"]+)$', f.decode("utf-8", errors="ignore"))
                    if match:
                        name = match.group(1) or match.group(2)
                        if name:
                            parsed_folders.append(name)
            if parsed_folders:
                folders = parsed_folders

        stat, _ = mail.select(folder, readonly=True)
        if stat == "OK":
            _, all_uids = mail.uid("SEARCH", None, "ALL")
            if all_uids and all_uids[0]:
                total_count = len(all_uids[0].split())
            _, unread_uids = mail.uid("SEARCH", None, "UNSEEN")
            if unread_uids and unread_uids[0]:
                unread_count = len(unread_uids[0].split())
    except Exception:
        pass
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return {
        "success": True,
        "provider": provider,
        "host": host,
        "port": port,
        "email": clean_email,
        "folders": folders,
        "unread_count": unread_count,
        "total_count": total_count,
        "message": f"Connected to {provider} successfully! {unread_count} unread ({total_count} total messages)."
    }


def get_simulated_inbox(
    count: int = 10,
    only_unread: bool = False,
    model_type: str = "svm"
) -> List[Dict[str, Any]]:
    """
    Returns realistic mock email scenarios for demo and testing purposes.
    """
    scenarios = [
        {
            "id": "demo-001",
            "sender": "alert@paypa1-security-verification.com",
            "subject": "CRITICAL: Your PayPal Account will be suspended within 24 hours",
            "date": "Just now",
            "headers": {
                "From": "alert@paypa1-security-verification.com",
                "Subject": "CRITICAL: Your PayPal Account will be suspended within 24 hours",
                "Reply-To": "harvest@paypa1-security-verification.com",
                "Authentication-Results": "spf=fail (sender IP 185.220.101.5) dkim=neutral dmarc=fail"
            },
            "attachments": [],
            "body": (
                "Dear Customer,\n\n"
                "We noticed suspicious login attempts from an unauthorized IP address in Saint Petersburg, Russia. "
                "Your account will be suspended within 24 hours unless you verify your identity immediately.\n\n"
                "Confirm your bank account and password here: http://paypa1-security-verification.com/login\n\n"
                "PayPal Security Team"
            )
        },
        {
            "id": "demo-002",
            "sender": "recruiter@global-tech-careers.org",
            "subject": "Offer of Employment: Remote Software Analyst (₹85,000/month)",
            "date": "2 hours ago",
            "headers": {
                "From": "recruiter@global-tech-careers.org",
                "Subject": "Offer of Employment: Remote Software Analyst",
                "Reply-To": "careers@global-tech-careers.org",
                "Authentication-Results": "spf=pass dkim=pass dmarc=pass"
            },
            "attachments": [{"filename": "Employment_Contract.pdf", "mime_type": "application/pdf", "size": 14200}],
            "body": (
                "Congratulations! You have been selected for the position of Remote Software Analyst. "
                "The monthly stipend is ₹85,000 with flexible hours.\n\n"
                "To finalize onboarding and dispatch your company MacBook Pro, please pay a refundable registration "
                "and training fee of ₹2,500 to our equipment vendor. Send your Aadhaar and bank account details "
                "immediately to confirm your joining."
            )
        },
        {
            "id": "demo-003",
            "sender": "billing@electricity-utility-notice.in",
            "subject": "Urgent: Electricity supply will be disconnected tonight at 9:30 PM",
            "date": "3 hours ago",
            "headers": {
                "From": "billing@electricity-utility-notice.in",
                "Subject": "Urgent: Electricity supply will be disconnected tonight at 9:30 PM",
                "Authentication-Results": "spf=fail dkim=fail dmarc=fail"
            },
            "attachments": [],
            "body": (
                "Dear Consumer, your electricity bill of ₹4,820 remains unpaid. "
                "Your power connection will be cut off tonight at 9:30 PM from the power sub-station. "
                "Please call electricity officer Mr. Sharma immediately on 9876543210 and pay via UPI to prevent disconnection."
            )
        },
        {
            "id": "demo-004",
            "sender": "notifications@github.com",
            "subject": "[GitHub] Security update: Dependabot alerts resolved in main",
            "date": "Yesterday",
            "headers": {
                "From": "notifications@github.com",
                "Subject": "[GitHub] Security update: Dependabot alerts resolved in main",
                "Authentication-Results": "spf=pass dkim=pass (domain=github.com) dmarc=pass"
            },
            "attachments": [],
            "body": (
                "Hi there,\n\n"
                "All 3 Dependabot alerts for your repository have been successfully resolved by pull request #42. "
                "Your automated CI tests completed cleanly with 100% test coverage.\n\n"
                "View repo: https://github.com/my-project/security"
            )
        },
        {
            "id": "demo-005",
            "sender": "priya.sharma@innovate-corp.com",
            "subject": "Meeting Agenda: Q4 Product Roadmap & Sprint Review",
            "date": "2 days ago",
            "headers": {
                "From": "priya.sharma@innovate-corp.com",
                "Subject": "Meeting Agenda: Q4 Product Roadmap & Sprint Review",
                "Authentication-Results": "spf=pass dkim=pass dmarc=pass"
            },
            "attachments": [{"filename": "Q4_Roadmap_Final.xlsx", "mime_type": "application/vnd.ms-excel", "size": 32000}],
            "body": (
                "Hi team,\n\n"
                "Looking forward to our quarterly review tomorrow at 11:00 AM IST. "
                "Please review the attached spreadsheet beforehand and add any questions to our shared doc.\n\n"
                "Best,\nPriya"
            )
        }
    ]

    results = []
    selected = scenarios[:count]
    for item in selected:
        full_text = f"Subject: {item['subject']}\n\n{item['body']}"
        pred = predict_email(full_text, model_type=model_type)
        results.append({
            "id": item["id"],
            "subject": item["subject"],
            "sender": item["sender"],
            "date": item["date"],
            "body_preview": item["body"][:180] + ("..." if len(item["body"]) > 180 else ""),
            "full_text": full_text,
            "headers": item["headers"],
            "attachments": item["attachments"],
            "uidvalidity": "demo",
            "folder": "INBOX",
            "provider": "demo",
            "prediction": pred["label"],
            "confidence": pred["confidence"],
            "prob_spam": pred["prob_spam"],
            "prob_ham": pred["prob_ham"],
            "is_spam": pred["is_spam"],
            "key_features": pred["key_features"]
        })
    return results


def scan_gmail_inbox(
    email_address: str,
    app_password: str,
    folder: str = "INBOX",
    max_emails: int = 10,
    only_unread: bool = False,
    model_type: str = "nb",
    imap_host: str = "",
    imap_port: int = 993,
    timeout: int = 15
) -> List[Dict[str, Any]]:
    """
    Universal IMAP email scanner. Connects securely via IMAP SSL to Gmail,
    Outlook, Yahoo, iCloud, or custom servers, fetches recent messages,
    and runs them through the SpamGuard AI ML pipeline.
    """
    clean_email = str(email_address or "").strip()
    clean_pwd = str(app_password or "").strip()

    # Demo feed support
    if clean_email == "demo@spamguard.local" or clean_pwd == "demo":
        return get_simulated_inbox(max_emails, only_unread, model_type)

    host, port, provider = resolve_imap_settings(clean_email, imap_host, imap_port)
    clean_email, clean_pwd = clean_credentials(clean_email, clean_pwd, provider)

    if not clean_email or not clean_pwd:
        raise ValueError("Both email address and App Password are required.")

    # Connect to IMAP server
    try:
        mail = imaplib.IMAP4_SSL(host, port)
    except Exception as e:
        raise ConnectionError(f"Could not connect to {provider} ({host}:{port}): {e}")

    try:
        mail.login(clean_email, clean_pwd)
    except imaplib.IMAP4.error as e:
        raise PermissionError(
            f"Login to {provider} failed for {clean_email}.\n"
            f"Please ensure:\n"
            f"1. 2-Step Verification is enabled on your email account.\n"
            f"2. You are using a 16-character App Password (not your standard login password).\n"
            f"Details from server: {e}"
        )

    try:
        status, _ = mail.select(folder, readonly=True)
        if status != "OK":
            # If specified folder failed, attempt fallback to INBOX
            if folder != "INBOX":
                status, _ = mail.select("INBOX", readonly=True)
                folder = "INBOX"
            if status != "OK":
                raise ValueError(f"Could not access folder '{folder}'. Check available folders.")

        search_criteria = "UNSEEN" if only_unread else "ALL"
        status, search_data = mail.uid("SEARCH", None, search_criteria)
        if status != "OK":
            return []

        validity_response = mail.response("UIDVALIDITY")[1]
        uidvalidity = validity_response[0].decode() if validity_response and validity_response[0] else ""
        email_ids = search_data[0].split()
        if not email_ids:
            return []

        # Get latest N emails (newest first)
        recent_ids = email_ids[-max_emails:][::-1]
        results = []

        for e_id in recent_ids:
            res, msg_data = mail.uid("FETCH", e_id, "(BODY.PEEK[])")
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
            headers = dict(msg.items())
            attachments, html_parts = [], []
            for part in msg.walk():
                if part.get_filename():
                    attachments.append({
                        "filename": decode_str(part.get_filename()),
                        "mime_type": part.get_content_type(),
                        "size": len(part.get_payload(decode=True) or b"")
                    })
                elif part.get_content_type() == "text/html":
                    html_parts.append(
                        (part.get_payload(decode=True) or b"").decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                    )
            security_text = full_text + "\n" + "\n".join(html_parts)
            pred = predict_email(full_text, model_type=model_type)

            results.append({
                "id": e_id.decode("utf-8", errors="ignore"),
                "subject": subject,
                "sender": sender,
                "date": date_str,
                "body_preview": body[:180] + ("..." if len(body) > 180 else ""),
                "full_text": security_text,
                "headers": headers,
                "attachments": attachments,
                "uidvalidity": uidvalidity,
                "folder": folder,
                "provider": "imap",
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
            mail.logout()
        except Exception:
            pass


# Alias for backward-compatible and modern naming
scan_email_inbox = scan_gmail_inbox
test_inbox_connection = verify_inbox_connection
