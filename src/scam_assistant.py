"""Evidence-led scam checks. Rules indicate risk, not proof of fraud."""
import re
from src.ai_threat_intelligence import compute_threat_intelligence
from src.email_content import address_domain, domain_from_url, belongs_to, html_details
from src.security_analyzer import extract_urls
from src.evidence import observed_evidence, sentence_context

JOB_RULES = [
    ("Recruitment payment requested", r"(?:pay|deposit|send|transfer|submit).{0,45}(?:registration fee|recruitment fee|security deposit|training fee|joining fee)|(?:registration|recruitment|joining) fee.{0,30}(?:required|mandatory|pay)|(?:registration|joining|training).{0,15}(?:fees?|paisa|paise).{0,20}(?:bhejo|jama|pay|dena)|(?:पंजीकरण|रजिस्ट्रेशन|नौकरी).{0,20}(?:फीस|शुल्क).{0,20}(?:भेज|जमा|देना)", 35,
     "Verify the role through the employer's official careers page before paying."),
    ("Equipment payment or fake-check pattern", r"(?:deposit|cash).{0,25}(?:check|cheque).{0,100}(?:equipment|laptop|send|transfer)|(?:pay|payment|send|purchase|buy).{0,35}(?:equipment|laptop).{0,35}(?:supplier|vendor|fee|advance)|(?:send|transfer|return).{0,30}(?:remaining balance|overpayment)", 35,
     "Independently verify equipment arrangements; do not forward money from an unfamiliar check."),
    ("Sensitive information requested", r"(?:send|share|provide|upload).{0,50}(?:otp|password|bank details|bank account|aadhaar|passport|pan card)|(?:otp|password|bank details).{0,20}(?:bhejo|batao|share karo)|(?:ओटीपी|पासवर्ड|आधार).{0,20}(?:भेज|बताएं|बताओ)|(?:pan card|aadhaar|kyc).{0,40}(?:update|unblock|verify).{0,40}(?:call|contact|bhejo|karein)", 35,
     "Verify the recipient and purpose before sharing documents. Do not share passwords or one-time codes."),
    ("Pay-to-withdraw task scheme", r"(?:deposit|pay|recharge).{0,60}(?:withdraw|unlock.{0,15}earnings|commission)|(?:withdraw|commission).{0,60}(?:deposit|recharge)", 40,
     "Stop and independently verify requests to pay before withdrawing earnings."),
    ("Utility disconnection threat / fake electricity bill",
     r"(?:बिजली|विद्युत)\s*(?:विभाग|बिल|कनेक्शन)?.{0,60}(?:काट\s*दिया\s*जाएगा|कट\s*जाएगा|कट\s*जायेगा|बंद\s*कर\s*दिया\s*जाएगा|काटने).{0,60}(?:संपर्क|कॉल|बिल\s*भर|भुगतान|नंबर|\d{10})|(?:bijli|power|electricity)\s*(?:connection|bill)?.{0,60}(?:disconnect|kat|cut\s*kar|band\s*kar).{0,60}(?:call|sampark|jama|pay|number|\d{10})|(?:disconnect|kat\s*diya).{0,40}(?:bijli|power|connection).{0,40}(?:call|jama|bharo|pay|number|\d{10})|(?:electricity|power|utility)\s+(?:bill|service|connection|supply).{0,60}(?:disconnect|shut off|cut off|suspended).{0,60}(?:call|contact|pay|immediately)",
     45,
     "Electricity providers do not disconnect power within hours via text or ask you to call personal mobile numbers. Verify your bill on the official utility website or app."),
    ("Fake legal notice / traffic challan threat",
     r"(?:ई-चालान|चालान|traffic challan).{0,60}(?:वारंट|कोर्ट|कोर्ट केस|तुरंत भरें|अधिकारी से संपर्क)|(?:arrest warrant|court notice).{0,60}(?:pay|call|contact|settle)",
     45,
     "Official court summons or traffic challans are settled only on government portals (e.g. echallan.parivahan.gov.in). Never call personal numbers.")
]

ASSESSMENTS = {
    "English": {"High risk": "High risk", "Needs verification": "Needs verification", "No strong warning found": "No strong warning found", "Unable to assess": "Unable to assess"},
    "Hindi": {"High risk": "उच्च जोखिम", "Needs verification": "पुष्टि ज़रूरी है", "No strong warning found": "कोई बड़ा चेतावनी संकेत नहीं मिला", "Unable to assess": "जाँच के लिए पर्याप्त जानकारी नहीं"},
    "Hinglish": {"High risk": "Risk zyada hai", "Needs verification": "Pehle verify karein", "No strong warning found": "Koi strong warning nahi mili", "Unable to assess": "Check karne ke liye jaankari kam hai"},
}


def payment_details(text):
    patterns = [r"\b(?:account|a/c|iban|ifsc|upi)\s*(?:number|no\.?|id)?\s*[:=\-]?\s*([A-Z0-9@._-]{5,34})\b"]
    return sorted({match.upper() for pattern in patterns for match in re.findall(pattern, text, re.I)})


def check_message(text, category="General message", sender="", company_domain="", previous_text="", headers=None, attachments=None, model_type="svm", previous_sender="", previous_reply_to="", previous_headers=None):
    text = str(text or "").strip()
    if not text and not headers and not attachments:
        return {"assessment": "Unable to assess", "summary": "Add message text or confirm extracted screenshot text to start.", "evidence": [], "limitations": ["No message content provided."], "score": None, "category": category}
    report = compute_threat_intelligence(text, model_type=model_type, headers=headers, attachments=attachments)
    evidence = observed_evidence(report, text, headers)
    extra_score = 0
    from src.gmail_actions import check_sender_reputation
    reputation = check_sender_reputation(sender or (headers or {}).get("From", ""))
    if reputation == "BLACKLISTED":
        evidence.append({"title": "Sender is on your blocked list", "excerpt": sender, "advice": "Verify the message independently before responding."})
        extra_score += 30
    is_job = category == "Job or internship" or bool(re.search(r"\b(job|internship|recruiter|recruitment|hired|vacancy)\b|नौकरी", text, re.I))
    for title, pattern, weight, advice in JOB_RULES:
        if not is_job and title not in {
            "Sensitive information requested",
            "Pay-to-withdraw task scheme",
            "Utility disconnection threat / fake electricity bill",
            "Fake legal notice / traffic challan threat"
        }:
            continue
        match = re.search(pattern, text, re.I | re.S)
        if match:
            excerpt = match.group(0)
            preceding = text[max(0, match.start()-35):match.start()]
            if re.search(r"\b(?:never|not|don't|do not|no need to|कभी नहीं|न करें|na karein|mat karein)\b", preceding, re.I):
                continue
            # Maintenance / safety exception: if purely routine maintenance without urgent payment demand
            if "disconnection" in title.lower() and re.search(r"\b(?:maintenance|रखरखाव|safety reminder|सुरक्षा नियम)\b", text, re.I) and not re.search(r"\b(?:\d{10}|काट दिया जाएगा|call karein aur bill jama)\b", text, re.I):
                continue
            evidence.append({"title": title, "excerpt": excerpt, "sentence": sentence_context(html_details(text)["text"] if re.search(r"</?[a-z][^>]*>", text, re.I) else text, excerpt), "source": "Message text", "advice": advice})
            extra_score += weight
    expected = domain_from_url(company_domain.strip()) if company_domain.strip() else ""
    if expected:
        sender_domain = address_domain(sender or (headers or {}).get("From", ""))
        domains = {domain_from_url(u["url"]) for u in extract_urls(text)}
        if sender_domain and not belongs_to(sender_domain, expected):
            evidence.append({"title": "Sender differs from the supplied company domain", "excerpt": sender_domain,
                             "advice": "External recruiters can be legitimate. Confirm this recruiter with the employer independently."})
            extra_score += 15
        for domain in sorted(d for d in domains if d and not belongs_to(d, expected)):
            evidence.append({"title": "Link differs from the supplied company domain", "excerpt": domain,
                             "advice": "Check whether the employer officially uses this external service."})
            extra_score += 10
    from src.conversation_comparison import compare_conversations
    before, after = payment_details(previous_text), payment_details(text)
    conv_result = compare_conversations(
        earlier_text=previous_text,
        newer_text=text,
        earlier_sender=previous_sender,
        newer_sender=sender or (headers or {}).get("From", ""),
        earlier_reply_to=previous_reply_to,
        newer_reply_to=(headers or {}).get("Reply-To", ""),
        earlier_headers=previous_headers,
        newer_headers=headers
    )
    if conv_result["has_comparison"]:
        for diff in conv_result["differences"]:
            # If payment difference already has a specific title format expected by tests, preserve it
            title = "Payment details differ from the earlier message" if diff["category"] == "payment" and "changed" in diff["title"].lower() else diff["title"]
            evidence.append({
                "title": title,
                "excerpt": f"Earlier: {diff['before']}; current: {diff['after']}",
                "advice": f"{diff['advice']} Treat changes as reasons to verify, not automatic proof of fraud.",
                "source": "Conversation comparison",
                "diff_category": diff["category"],
                "before": diff["before"],
                "after": diff["after"],
                "why_it_matters": diff["why_it_matters"]
            })
        # Use the comparison engine's aggregated score for consistency
        extra_score += conv_result.get("extra_score", 0)
    elif previous_text.strip() and after and before != after:
        evidence.append({"title": "Payment details differ from the earlier message", "excerpt": f"Earlier: {', '.join(before) or 'not found'}; current: {', '.join(after)}",
                         "advice": "Call the supplier using a previously trusted number before making payment. A change alone is not proof of fraud."})
        extra_score += 25
    limitations = ["Risk indicators do not establish authenticity. Absence of a warning does not prove safety.",
                   "Attachments are checked by metadata only; file contents are not scanned for malware.",
                   "The spam model was evaluated on an English benchmark, not all modern scam types."]
    if not headers:
        limitations.append("Sender authentication cannot be checked from pasted text alone.")
    if re.search(r"[\u0900-\u097f]", text):
        limitations.append("Hindi rules have limited coverage. English model confidence should not be relied on for Hindi text.")
    if category == "Invoice or payment" and not previous_text:
        limitations.append("No earlier message supplied: payment-detail changes cannot be compared.")
    score = min(100, report["threat_score"] + extra_score)
    meaningful = bool(evidence or report["url_forensics"]["url_count"] or len(text.split()) >= 4)
    if not meaningful or (not report.get("assessment_available", True) and not evidence):
        assessment = "Unable to assess"
    elif re.search(r"[\u0900-\u097f]", text) and not evidence:
        assessment = "Unable to assess"
    elif score >= 70:
        assessment = "High risk"
    elif evidence or score >= 40 or is_job or category == "Invoice or payment":
        assessment = "Needs verification"
    else:
        assessment = "No strong warning found"
    summary = {
        "High risk": "Several warning indicators were found. Pause before paying, clicking, or sharing information.",
        "Needs verification": "Verify this request independently before taking a sensitive action.",
        "No strong warning found": "These checks found no strong warning. The sender and request are not verified.",
        "Unable to assess": "There is too little useful content for a reliable assessment."}[assessment]
    from src.multilingual import ASSESSMENT_SUMMARIES
    localized_summaries = {
        lang: ASSESSMENT_SUMMARIES.get(lang, {}).get(assessment, summary)
        for lang in ["English", "Hindi", "Hinglish"]
    }
    return {"assessment": assessment, "summary": summary, "score": score if meaningful else None,
            "evidence": evidence, "limitations": limitations, "category": category,
            "report": report, "job_check": is_job,
            "localized_summaries": localized_summaries,
            "payment_comparison": {"before": before, "after": after},
            "conversation_comparison": conv_result}


def recovery_steps(stage, language="English"):
    from src.multilingual import get_localized_recovery_steps
    return get_localized_recovery_steps(stage, language)
