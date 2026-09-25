"""
Unit tests for automated Gmail remediation policies and sender whitelist/blacklist rules.
"""

import pytest
from src.gmail_actions import (
    add_to_whitelist,
    add_to_blacklist,
    remove_sender_rule,
    check_sender_reputation,
    evaluate_remediation_policy,
    get_sender_rules
)


def test_whitelist_and_blacklist_management():
    test_email = "trusted-partner@corp-domain.com"
    test_spam_domain = "malicious-phishing-host.xyz"

    # Add to whitelist
    add_to_whitelist(test_email)
    assert check_sender_reputation(test_email) == "WHITELISTED"

    # Move to blacklist
    add_to_blacklist(test_email)
    assert check_sender_reputation(test_email) == "BLACKLISTED"

    # Check blacklist domain
    add_to_blacklist(test_spam_domain)
    assert check_sender_reputation(f"attacker@{test_spam_domain}") == "BLACKLISTED"

    # Remove rule
    remove_sender_rule(test_email)
    remove_sender_rule(test_spam_domain)
    assert check_sender_reputation(test_email) == "NEUTRAL"


def test_evaluate_remediation_policy():
    # Whitelisted sender
    add_to_whitelist("admin@trusted.org")
    pol_white = evaluate_remediation_policy("admin@trusted.org", threat_score=80, is_spam=True)
    assert pol_white["policy"] == "DELIVER_INBOX"
    assert pol_white["quarantine_recommended"] is False
    remove_sender_rule("admin@trusted.org")

    # Blacklisted sender
    add_to_blacklist("evil@spammer.com")
    pol_black = evaluate_remediation_policy("evil@spammer.com", threat_score=20, is_spam=False)
    assert pol_black["policy"] == "AUTO_QUARANTINE"
    assert pol_black["quarantine_recommended"] is True
    remove_sender_rule("evil@spammer.com")

    # High threat score
    pol_high = evaluate_remediation_policy("unknown@suspicious.ru", threat_score=90, is_spam=True)
    assert pol_high["policy"] == "AUTO_QUARANTINE"
    assert pol_high["quarantine_recommended"] is True

    # Benign email
    pol_clean = evaluate_remediation_policy("colleague@work.com", threat_score=10, is_spam=False)
    assert pol_clean["policy"] == "DELIVER_INBOX"
    assert pol_clean["quarantine_recommended"] is False
