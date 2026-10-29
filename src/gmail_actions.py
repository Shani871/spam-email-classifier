"""
Automated Inbox Remediation & Sender Policy Management for SpamGuard AI.
Handles automated quarantining, persistent sender whitelist/blacklist rules,
and remediation policies for live and simulated email environments.
"""

import os
import sys
import json
import re
import imaplib
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RULES_FILE = os.path.join(DATA_DIR, "sender_rules.json")


from src.user_storage import read_json, write_json


def get_sender_rules() -> Dict[str, List[str]]:
    return read_json("sender_rules.json", {"whitelist": [], "blacklist": []})


def save_sender_rules(rules: Dict[str, List[str]]):
    write_json("sender_rules.json", rules)


def add_to_whitelist(sender_or_domain: str) -> bool:
    """Adds a sender email or domain to the whitelist."""
    clean = sender_or_domain.lower().strip()
    if not clean:
        return False

    rules = get_sender_rules()
    if clean in rules["blacklist"]:
        rules["blacklist"].remove(clean)
    if clean not in rules["whitelist"]:
        rules["whitelist"].append(clean)
        save_sender_rules(rules)
    return True


def add_to_blacklist(sender_or_domain: str) -> bool:
    """Adds a sender email or domain to the blacklist."""
    clean = sender_or_domain.lower().strip()
    if not clean:
        return False

    rules = get_sender_rules()
    if clean in rules["whitelist"]:
        rules["whitelist"].remove(clean)
    if clean not in rules["blacklist"]:
        rules["blacklist"].append(clean)
        save_sender_rules(rules)
    return True


def remove_sender_rule(sender_or_domain: str) -> bool:
    """Removes a sender email or domain from all lists."""
    clean = sender_or_domain.lower().strip()
    rules = get_sender_rules()
    changed = False
    if clean in rules["whitelist"]:
        rules["whitelist"].remove(clean)
        changed = True
    if clean in rules["blacklist"]:
        rules["blacklist"].remove(clean)
        changed = True

    if changed:
        save_sender_rules(rules)
    return changed


def check_sender_reputation(sender: str) -> str:
    """
    Evaluates sender reputation against persistent rules.
    Returns: 'WHITELISTED', 'BLACKLISTED', or 'NEUTRAL'
    """
    if not sender:
        return "NEUTRAL"

    # Extract email from format 'Name <email@domain.com>'
    match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
    email_addr = match.group(0).lower() if match else sender.lower().strip()
    domain = email_addr.split("@")[-1] if "@" in email_addr else ""

    rules = get_sender_rules()

    # Check exact email match
    if email_addr in rules["whitelist"] or (domain and domain in rules["whitelist"]):
        return "WHITELISTED"

    if email_addr in rules["blacklist"] or (domain and domain in rules["blacklist"]):
        return "BLACKLISTED"

    return "NEUTRAL"


def evaluate_remediation_policy(
    sender: str,
    threat_score: int,
    is_spam: bool
) -> Dict[str, Any]:
    """
    Determines automated remediation action based on sender reputation and threat score.
    """
    rep = check_sender_reputation(sender)

    if rep == "WHITELISTED" and threat_score < 50 and not is_spam:
        return {
            "policy": "DELIVER_INBOX",
            "action": "ALLOWED_BY_WHITELIST",
            "reason": f"Sender '{sender}' is in trusted whitelist.",
            "quarantine_recommended": False
        }

    if rep == "BLACKLISTED":
        return {
            "policy": "AUTO_QUARANTINE",
            "action": "BLOCKED_BY_BLACKLIST",
            "reason": f"Sender '{sender}' is explicitly blacklisted.",
            "quarantine_recommended": True
        }

    if threat_score >= 75:
        return {
            "policy": "AUTO_QUARANTINE",
            "action": "QUARANTINED_HIGH_THREAT",
            "reason": f"Critical threat score ({threat_score}/100) requires immediate isolation.",
            "quarantine_recommended": True
        }

    if threat_score >= 50 or is_spam:
        return {
            "policy": "FLAG_SPAM",
            "action": "MOVE_TO_SPAM_FOLDER",
            "reason": f"Message meets spam criteria (Score: {threat_score}/100).",
            "quarantine_recommended": False
        }

    return {
        "policy": "DELIVER_INBOX",
        "action": "CLEARED_HAM",
        "reason": "Legitimate communication with no security triggers.",
        "quarantine_recommended": False
    }


def execute_quarantine_imap(
    email_address: str,
    app_password: str,
    email_id: str,
    destination_folder: str = "[Gmail]/Spam",
    source_folder: str = "INBOX",
    uidvalidity: str = ""
) -> Dict[str, Any]:
    """Move only a stable UID, without expunging unrelated messages."""
    clean_email = str(email_address or "").strip()
    clean_pwd = re.sub(r"\s+", "", str(app_password or ""))
    if not clean_email or not clean_pwd:
        return {"success": False, "mode": "SIMULATION", "message": "No inbox action taken: account is not connected."}
    if not str(email_id).isdigit() or not uidvalidity:
        return {"success": False, "message": "Rescan this message before moving it; a stable mailbox identifier is required."}
    mail = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(clean_email, clean_pwd)
        status, _ = mail.select(source_folder)
        if status != "OK":
            raise ValueError("Source folder is unavailable.")
        current = mail.response("UIDVALIDITY")[1]
        actual = current[0].decode() if current and current[0] else ""
        if actual != str(uidvalidity):
            raise ValueError("Mailbox identifiers changed. Rescan before taking action.")
        if b"MOVE" not in mail.capabilities:
            raise ValueError("This server does not support safe message moves.")
        result, _ = mail.uid("MOVE", str(email_id), destination_folder)
        if result != "OK":
            raise ValueError("The provider did not confirm the move.")
        return {"success": True, "mode": "LIVE_IMAP", "message": "Email moved successfully. Rescan the destination folder to restore it."}
    except ValueError:
        raise
    except Exception:
        return {"success": False, "mode": "LIVE_IMAP", "message": "Move failed. Reconnect or rescan the mailbox and try again."}
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass
