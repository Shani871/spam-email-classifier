"""
Rule-based threat narrative generator for SpamGuard AI.
Synthesizes natural language threat narratives from structured threat-intelligence output,
covering attacker motives, psychological manipulation tactics, and recommended containment.
All analysis is performed locally using heuristic rules — no external AI service is called.
"""

import os
from typing import Dict, Any, Optional

from src.ai_threat_intelligence import compute_threat_intelligence


def generate_offline_reasoning(report: Dict[str, Any], subject: str, sender: str) -> Dict[str, Any]:
    """
    Constructs an intelligent, contextual threat analysis narrative without external API keys.
    """
    score = report["threat_score"]
    level = report["threat_level"]
    vector = report["attack_vector"]
    u_info = report["url_forensics"]
    p_info = report["psychological_forensics"]
    tactics = report["tactics_detected"]

    # Attacker Objective Narrative
    if score >= 75:
        executive_summary = (
            f"This communication shows indicators associated with '{vector}', with a high "
            f"risk indicator of {score}/100. Verify the sender and request independently before taking action."
        )
    elif score >= 50:
        executive_summary = (
            f"This email exhibits suspicious promotional or deceptive patterns (Threat Score: {score}/100). "
            f"While it may not contain direct zero-day exploits, it utilizes pressure cues and unsolicited links."
        )
    else:
        executive_summary = (
            f"No strong warning was found by these checks (Risk indicator: {score}/100). "
            f"The sender, links, and file contents have not been verified."
        )

    # Psychological Exploitation Analysis
    psychological_narrative = []
    coercion = p_info.get("coercion_tactics", {})
    if "urgency_deadline" in coercion:
        psychological_narrative.append(
            "• **Artificial Urgency & Time Compression:** The attacker imposes an arbitrary deadline to induce cognitive panic, "
            "discouraging the victim from validating the request through secondary channels."
        )
    if "fear_intimidation" in coercion:
        psychological_narrative.append(
            "• **Fear & Authority Exploitation:** Threatens account lockout or legal penalties to exploit organizational deference to authority."
        )
    if "financial_coercion" in coercion:
        psychological_narrative.append(
            "• **Financial Panic Manipulation:** Falsely alerts the user to an unexpected debit or invoice to trigger an immediate hasty cancellation."
        )
    if "greed_bait" in coercion:
        psychological_narrative.append(
            "• **Bait & Reward Induction:** Promises unearned prizes or grants to elicit personal identifying information or advance fees."
        )

    if not psychological_narrative:
        psychological_narrative.append("• No manipulative psychological exploitation identified in text content.")

    # Technical Evasion Tactics
    technical_narrative = []
    if u_info.get("has_deceptive_link"):
        technical_narrative.append(
            "• **Deceptive Link Routing:** The display text claims to target a trusted service, while the HTML hyperlink points to an unauthorized external server."
        )
    if u_info.get("has_ip_link"):
        technical_narrative.append(
            "• **Direct IP Addressing:** Avoids DNS domain reputation filters by linking directly to raw IP addresses."
        )
    for u in u_info.get("urls", []):
        brand = u.get("domain_analysis", {}).get("impersonated_brand")
        if brand:
            technical_narrative.append(
                f"• **Brand Typosquatting:** Domain mimics '{brand.title()}' with intentional character substitutions or suspicious subdomains."
            )
            break

    if not technical_narrative:
        technical_narrative.append("• No deceptive technical routing or domain spoofing identified.")

    # Blast Radius / Impact Assessment
    if score >= 75:
        blast_radius = (
            "**High Potential for Account Compromise:** If an employee clicks the embedded link or provides credentials, "
            "adversaries will gain unauthorized account access, potentially enabling lateral movement across organizational systems."
        )
    elif score >= 50:
        blast_radius = (
            "**Moderate Risk:** Exposure to marketing tracking, unsolicited spam campaigns, or secondary credential fishing."
        )
    else:
        blast_radius = "**Limited evidence:** No strong warning found; authenticity has not been verified."

    return {
        "mode": "RULE_BASED_EXPLANATION",
        "executive_summary": executive_summary,
        "psychological_breakdown": psychological_narrative,
        "technical_breakdown": technical_narrative,
        "blast_radius_assessment": blast_radius,
        "recommended_containment": report["security_advisories"]
    }


def explain_threat_with_llm(
    email_text: str,
    subject: str = "",
    sender: str = "",
    api_key: Optional[str] = None,
    consent: bool = False,
) -> Dict[str, Any]:
    """
    Returns a rule-based threat narrative for the given email text.
    The api_key and consent parameters are accepted for forward-compatibility
    but have no effect — analysis is always performed locally.
    """
    report = compute_threat_intelligence(email_text)
    return generate_offline_reasoning(report, subject, sender)
