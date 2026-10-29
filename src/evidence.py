"""Observed source excerpts, separate from heuristic interpretation."""
from html import escape
import re
from src.email_content import html_details


def sentence_context(text, match):
    position = text.lower().find(match.lower()) if match else -1
    if position < 0:
        return ""
    start = position
    end = position + len(match)
    while start > 0 and position - start < 180 and text[start - 1] not in "\n.!?":
        start -= 1
    while end < len(text) and end - position < 360 and text[end] not in "\n.!?":
        end += 1
    if end < len(text) and text[end] in ".!?":
        end += 1
    return text[start:end].strip()


def observed_evidence(report, text, headers):
    display_text = html_details(text)["text"] if re.search(r"</?[a-z][^>]*>", text, re.I) else text
    evidence = []
    titles = {"urgency_deadline": "Time pressure language", "fear_intimidation": "Threat or security-alert language",
              "financial_coercion": "Payment or financial language", "greed_bait": "Prize or reward language"}
    for tactic, matches in report["psychological_forensics"]["coercion_tactics"].items():
        for match in matches:
            evidence.append({"title": titles[tactic], "excerpt": match, "sentence": sentence_context(display_text, match),
                             "source": "Message text", "advice": "This wording can occur in legitimate messages too. Verify the request independently."})
    for link in report["url_forensics"]["urls"]:
        if not (link["is_deceptive"] or link["domain_analysis"]["is_suspicious"]):
            continue
        evidence.append({"title": "Displayed link and destination differ" if link["is_deceptive"] else "Link destination has warning indicators",
                         "excerpt": link["url"], "source": "Link destination", "sentence": "",
                         "displayed_text": link["anchor_text"], "advice": link.get("deceptive_reason") or "A domain indicator alone does not prove that the link is malicious."})
    normalized_headers = {name.lower(): str(value) for name, value in (headers or {}).items()}
    auth = report["authentication_forensics"]
    if auth.get("spf") == "FAIL":
        evidence.append({"title": "Header declares SPF failure", "excerpt": normalized_headers.get("received-spf", ""),
                         "source": "Email header (unverified claim)", "sentence": "", "advice": "Confirm authentication results with the receiving email provider."})
    if auth.get("reply_to_mismatch"):
        evidence.append({"title": "Sender and reply address use different domains",
                         "excerpt": f"From: {normalized_headers.get('from', '')}\nReply-To: {normalized_headers.get('reply-to', '')}",
                         "source": "Email headers", "sentence": "", "advice": "Different reply addresses can be legitimate; confirm the intended recipient before replying."})
    for attachment in report["attachment_forensics"]["attachment_reports"]:
        if attachment["is_dangerous"]:
            evidence.append({"title": "Attachment filename has warning indicators", "excerpt": attachment["filename"],
                             "source": "Attachment metadata", "sentence": "", "advice": " ".join(attachment["risk_reasons"]) + ". File contents have not been scanned."})
    return evidence


def highlight_html(sentence, match):
    """Only escaped text and a mark element reach the UI. No links/assets execute."""
    position = sentence.lower().find(match.lower()) if match else -1
    if position < 0:
        return "<blockquote>" + escape(sentence) + "</blockquote>"
    end = position + len(match)
    return "<blockquote>" + escape(sentence[:position]) + "<mark>" + escape(sentence[position:end]) + "</mark>" + escape(sentence[end:]) + "</blockquote>"
