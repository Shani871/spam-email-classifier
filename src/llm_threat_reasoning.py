"""
LLM Deep Threat Reasoning & Zero-Day Explainer for SpamGuard AI.
Synthesizes comprehensive natural language threat narratives, detailing attacker motives,
psychological manipulation tactics, potential compromise consequences, and SOC guidance.
Supports both offline semantic generation and live Google Gemini API execution.
"""

import os
import json
import urllib.request
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
            f"This communication is an active cyber threat classified as '{vector}' with a critical "
            f"threat score of {score}/100. The sender ('{sender}') is attempting to deceive the recipient "
            f"into performing an unauthorized or catastrophic action."
        )
    elif score >= 50:
        executive_summary = (
            f"This email exhibits suspicious promotional or deceptive patterns (Threat Score: {score}/100). "
            f"While it may not contain direct zero-day exploits, it utilizes pressure cues and unsolicited links."
        )
    else:
        executive_summary = (
            f"This email conforms to standard benign business or personal communication (Threat Score: {score}/100). "
            f"No malicious links, credential lures, or deceptive manipulation tactics were identified."
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
        blast_radius = "**Negligible Risk:** Normal legitimate communication."

    return {
        "mode": "OFFLINE_SEMANTIC_REASONER",
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
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a full AI threat reasoning narrative.
    Falls back gracefully to the offline semantic reasoner if no API key is provided.
    """
    report = compute_threat_intelligence(email_text)

    # Check for Gemini API key
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if not key:
        return generate_offline_reasoning(report, subject, sender)

    # Attempt Live Google Gemini API call
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{
                    "text": (
                        "You are an elite Cyber Threat Intelligence analyst. Dissect this email and return strict JSON:\n"
                        f"Subject: {subject}\nSender: {sender}\nContent:\n{email_text}\n\n"
                        "Return format:\n"
                        "{\n"
                        '  "executive_summary": "string",\n'
                        '  "psychological_breakdown": ["list", "of", "tactics"],\n'
                        '  "technical_breakdown": ["list", "of", "technical", "evasions"],\n'
                        '  "blast_radius_assessment": "string",\n'
                        '  "recommended_containment": ["list", "of", "actions"]\n'
                        "}"
                    )
                }]
            }]
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=8) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            # Strip markdown json blocks if present
            clean_json = raw_text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            parsed["mode"] = "GEMINI_LIVE_API"
            return parsed

    except Exception as e:
        print(f"[LLM Threat Reasoning] Live API call skipped/failed ({e}). Using offline semantic reasoner.")
        fallback = generate_offline_reasoning(report, subject, sender)
        fallback["mode"] = f"OFFLINE_SEMANTIC_REASONER (Live API fallback: {e})"
        return fallback
