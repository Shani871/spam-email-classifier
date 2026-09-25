"""
Unit tests for security forensics, URL phishing detection, and psychological coercion analysis.
"""

import pytest
from src.security_analyzer import (
    extract_urls,
    analyze_domain,
    analyze_urls,
    analyze_psychological_coercion,
    inspect_email_security
)


def test_extract_urls_plain_and_html():
    text = (
        "Check this link: https://legitimate-service.org and this anchor: "
        '<a href="http://hidden-payload.xyz/download">Click Here to Claim</a>'
    )
    extracted = extract_urls(text)
    assert len(extracted) == 2
    urls = [x["url"] for x in extracted]
    assert "https://legitimate-service.org" in urls
    assert "http://hidden-payload.xyz/download" in urls

    # Check anchor text extraction
    html_item = next(x for x in extracted if x["is_html_link"])
    assert html_item["anchor_text"] == "Click Here to Claim"


def test_analyze_domain_typosquatting():
    # Homoglyph substitution: paypa1 instead of paypal
    d1 = analyze_domain("paypa1-security.com")
    assert d1["impersonated_brand"] == "paypal"
    assert len(d1["typosquat_flags"]) > 0
    assert d1["is_suspicious"] is True

    # Substring brand spoofing: chase-security-fraud-alert.ru
    d2 = analyze_domain("chase-security-fraud-alert.ru")
    assert d2["impersonated_brand"] == "chase"
    assert d2["is_suspicious_tld"] is True
    assert d2["is_suspicious"] is True


def test_analyze_domain_ip_and_tld():
    d_ip = analyze_domain("192.168.1.100")
    assert d_ip["is_ip_address"] is True
    assert d_ip["is_suspicious"] is True

    d_safe = analyze_domain("google.com")
    assert d_safe["is_suspicious"] is False
    assert d_safe["impersonated_brand"] is None


def test_deceptive_link_detection():
    # Anchor text claims to be PayPal, but href is evil-hacker.xyz
    raw = [
        {
            "url": "http://evil-hacker.xyz/login",
            "anchor_text": "https://paypal.com/signin",
            "is_html_link": True
        }
    ]
    analysis = analyze_urls(raw)
    assert analysis["has_deceptive_link"] is True
    assert analysis["has_suspicious_domain"] is True
    report = analysis["urls"][0]
    assert report["is_deceptive"] is True
    assert "diverges" in report["deceptive_reason"] or "claims to be" in report["deceptive_reason"]


def test_psychological_coercion_tactics():
    phishing_text = (
        "URGENT: Your account has been suspended due to unauthorized transaction! "
        "You must cancel payment within 24 hours or face permanent termination. "
        "Claim your refund immediately!"
    )
    result = analyze_psychological_coercion(phishing_text)
    assert result["has_high_urgency"] is True
    assert result["urgency_score"] >= 0.50
    assert "urgency_deadline" in result["coercion_tactics"]
    assert "fear_intimidation" in result["coercion_tactics"]
    assert "financial_coercion" in result["coercion_tactics"]


def test_inspect_email_security_end_to_end():
    text = (
        "Security Alert: Your Chase Bank account is locked! "
        "Click here immediately: http://chase-security-login.xyz/unlock"
    )
    report = inspect_email_security(text)
    assert report["threat_indicators_detected"] is True
    assert report["url_forensics"]["has_suspicious_domain"] is True
    assert report["psychological_forensics"]["has_high_urgency"] is True
