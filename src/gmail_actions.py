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


def _ensure_rules_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(RULES_FILE):
        default_rules = {
            "whitelist": [
                "notifications@github.com",
                "security@google.com",
                "service@paypal.com",
                "no-reply@accounts.google.com"
            ],
            "blacklist": [
                "paypa1-security-update.com",
                "chase-fraud-alert.ru",
                "international-lottery.xyz"
            ]
        }
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_rules, f, indent=2)


def get_sender_rules() -> Dict[str, List[str]]:
    """Retrieves current sender whitelist and blacklist."""
    _ensure_rules_file()
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"whitelist": [], "blacklist": []}


def save_sender_rules(rules: Dict[str, List[str]]):
    """Saves updated whitelist and blacklist rules."""
    _ensure_rules_file()
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)


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

    if rep == "WHITELISTED":
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
    destination_folder: str = "[Gmail]/Spam"
) -> Dict[str, Any]:
    """
    Connects to Gmail via IMAP and moves specified email ID to Spam or Trash.
    """
    clean_email = re.sub(r'\s+', '', str(email_address or "")).strip()
    clean_pwd = re.sub(r'[^a-zA-Z0-9]', '', str(app_password or "")).strip()

    if not clean_email or not clean_pwd:
        return {
            "success": False,
            "mode": "SIMULATION",
            "message": f"Simulated quarantine: Message #{email_id} flagged for removal (Credentials not supplied)."
        }

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(clean_email, clean_pwd)
        mail.select("INBOX")

        # Copy to destination folder
        copy_res, _ = mail.copy(email_id, destination_folder)
        if copy_res == "OK":
            # Mark deleted from inbox
            mail.store(email_id, "+FLAGS", "\\Deleted")
            mail.expunge()
            mail.close()
            mail.logout()
            return {
                "success": True,
                "mode": "LIVE_IMAP",
                "message": f"Email #{email_id} successfully quarantined to '{destination_folder}'."
            }
        else:
            mail.close()
            mail.logout()
            return {
                "success": False,
                "mode": "LIVE_IMAP",
                "message": f"Could not move email to '{destination_folder}'. Server response: {copy_res}"
            }
    except Exception as e:
        return {
            "success": False,
            "mode": "LIVE_IMAP",
            "message": f"IMAP quarantine failed: {str(e)}"
        }
