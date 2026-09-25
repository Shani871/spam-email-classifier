"""
AI Threat Intelligence & Phishing Scoring Engine for SpamGuard AI.
Merges Tier-1 Machine Learning predictions with deep security forensics
to calculate a unified Phishing Threat Score (0-100), classify attack vectors,
and synthesize actionable security remediation advisories.
"""

import os
from typing import Dict, Any, Optional, List

from src.predict import predict_email
from src.security_analyzer import inspect_email_security
from src.attachment_analyzer import inspect_email_attachments


def compute_threat_intelligence(
    email_text: str,
    model_type: str = "nb",
    headers: Optional[Dict[str, str]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Evaluates an email using both ML classification and deep security forensics.

    Returns a rich threat intelligence report including:
    - threat_score (0-100)
    - threat_level (CLEAN, LOW RISK, SUSPICIOUS, HIGH THREAT, CRITICAL ATTACK)
    - attack_vector
    - ml_verdict
    - forensics_breakdown
    - psychological_tactics
    - security_advisories
    """
    # 1. Run Tier-1 ML Classifier
    ml_result = predict_email(email_text, model_type=model_type)

    # 2. Run Security Forensics (URLs, Typosquatting, Coercion, Headers)
    forensics = inspect_email_security(email_text, headers=headers)

    url_info = forensics["url_forensics"]
    psycho_info = forensics["psychological_forensics"]
    auth_info = forensics["authentication_forensics"]

    # 3. Calculate Threat Score (0 - 100)
    # Start with ML model probability (scaled 0 to 45)
    ml_prob = ml_result["prob_spam"]
    score = ml_prob * 45.0

    tactics_detected = []
    advisories = []

    # Threat boost from URL Forensics
    if url_info["has_deceptive_link"]:
        score += 35.0
        tactics_detected.append("Deceptive Link Routing (Text does not match target URL)")
        advisories.append("🚨 DO NOT CLICK: Embedded links point to a different destination than displayed text.")

    if url_info["has_ip_link"]:
        score += 25.0
        tactics_detected.append("Direct IP Link (Bypassing DNS domain reputation)")
        advisories.append("⚠️ Suspicious URL using raw IP address instead of a recognized domain.")

    if url_info["has_suspicious_domain"]:
        score += 20.0
        tactics_detected.append("High-Risk Domain / Suspicious TLD Detected")
        advisories.append("⚠️ Destination domain uses a high-risk TLD frequently abused in spam campaigns.")

    # Check for specific typosquatting / brand spoofing
    for u in url_info["urls"]:
        d_info = u.get("domain_analysis", {})
        if d_info.get("impersonated_brand"):
            score += 25.0
            brand = d_info["impersonated_brand"]
            tactics_detected.append(f"Brand Impersonation / Typosquatting: Mimicking '{brand.title()}'")
            advisories.append(f"🚨 Brand Spoofing: Domain appears engineered to impersonate {brand.title()}.")
            break

    # Threat boost from Psychological Coercion
    coercion = psycho_info["coercion_tactics"]
    if "urgency_deadline" in coercion:
        score += 10.0
        tactics_detected.append("Artificial Urgency & Deadline Manipulation")
        advisories.append("⏳ Uses artificial time pressure to force hasty decisions without verification.")

    if "fear_intimidation" in coercion:
        score += 15.0
        tactics_detected.append("Fear & Intimidation (Threats of account suspension or penalties)")
        advisories.append("🛡️ Common phishing lure: Threats of account suspension or unauthorized access.")

    if "financial_coercion" in coercion:
        score += 15.0
        tactics_detected.append("Financial Coercion (Wire transfers, refunds, or cryptocurrency)")
        advisories.append("💳 Never send wire transfers or crypto based on unverified email requests.")

    if "greed_bait" in coercion:
        score += 15.0
        tactics_detected.append("Greed Bait (Fake lottery, cash prizes, or unearned gifts)")
        advisories.append("🎁 Classic lottery/prize scam: Demands personal details for nonexistent winnings.")

    # Header failures
    if auth_info.get("spf") == "FAIL":
        score += 15.0
        tactics_detected.append("SPF Authentication Failure (Sender server not authorized)")
        advisories.append("🚫 SPF Verification Failed: The sending mail server is not authorized by the domain owner.")

    # Attachment forensics
    att_report = inspect_email_attachments(attachments or [])
    if att_report["has_dangerous_attachments"]:
        score += att_report["threat_penalty"]
        for rep in att_report["attachment_reports"]:
            if rep["is_dangerous"]:
                for t in rep["detected_tactics"]:
                    tactics_detected.append(f"Malicious Attachment: {t} ({rep['filename']})")
                for r in rep["risk_reasons"]:
                    advisories.append(f"🚨 ATTACHMENT RISK: {r}")

    # Bound score between 0 and 100
    final_score = int(round(max(0.0, min(100.0, score))))

    # 4. Determine Threat Level
    if final_score >= 88:
        threat_level = "CRITICAL ATTACK"
        threat_color = "#ef4444"
    elif final_score >= 70:
        threat_level = "HIGH THREAT"
        threat_color = "#f97316"
    elif final_score >= 45:
        threat_level = "SUSPICIOUS"
        threat_color = "#eab308"
    elif final_score >= 20:
        threat_level = "LOW RISK"
        threat_color = "#38bdf8"
    else:
        threat_level = "CLEAN / SAFE"
        threat_color = "#22c55e"

    # 5. Classify Attack Vector
    if url_info["has_deceptive_link"] or any("Impersonation" in t for t in tactics_detected):
        attack_vector = "Credential Harvesting & Brand Spoofing"
    elif "financial_coercion" in coercion or any("Wire" in t or "Bank" in t for t in tactics_detected):
        attack_vector = "Financial Scam & Wire Transfer Fraud"
    elif "greed_bait" in coercion:
        attack_vector = "Lottery & Prize Scam"
    elif "fear_intimidation" in coercion and final_score >= 60:
        attack_vector = "Account Takeover / Security Impersonation"
    elif ml_result["is_spam"]:
        attack_vector = "Unsolicited Bulk Spam / Marketing"
    else:
        attack_vector = "Benign Business / Personal Communication"

    # Default advisory if safe
    if not advisories:
        advisories.append("✅ No active phishing tactics or deceptive links detected. Safe to read.")

    return {
        "threat_score": final_score,
        "threat_level": threat_level,
        "threat_color": threat_color,
        "attack_vector": attack_vector,
        "is_action_required": final_score >= 50,
        "ml_result": ml_result,
        "url_forensics": url_info,
        "psychological_forensics": psycho_info,
        "authentication_forensics": auth_info,
        "attachment_forensics": att_report,
        "tactics_detected": tactics_detected,
        "security_advisories": advisories
    }
