"""Conversation comparison engine for SpamGuard AI.

Compares earlier and newer messages in an email thread or ongoing correspondence to
identify changes in:
- Sender addresses and domains
- Reply-To addresses and deviations
- Payment details (bank accounts, UPI IDs, IBAN, IFSC, crypto, payment handles)
- Link destinations and new domains
- Sensitive-information requests (passwords, OTPs, KYC/Aadhaar/PAN, banking credentials)

Treats changes as reasons to verify, not automatic proof of fraud.
"""

from email.utils import parseaddr
import re
from typing import Any, Dict, List, Optional, Set
from src.email_content import address_domain, domain_from_url
from src.security_analyzer import extract_urls

# Well-known free / consumer email provider domains.  An address @gmail.com
# is an ordinary email address, not a UPI ID.
_EMAIL_PROVIDER_DOMAINS = frozenset({
    "gmail", "yahoo", "outlook", "hotmail", "icloud", "proton",
    "aol", "zoho", "yandex", "mail", "live", "msn", "rediffmail",
    "inbox", "fastmail", "gmx", "tutanota", "pm", "hey",
    # common corporate/generic suffixes that look like email domains
})

# Known UPI handle suffixes (Indian payment system).
# A proper UPI ID looks like user@okaxis, user@ybl, user@paytm etc.
_UPI_HANDLE_SUFFIXES = frozenset({
    "okaxis", "okhdfcbank", "okicici", "oksbi", "ybl", "ibl", "upi",
    "paytm", "apl", "freecharge", "icici", "sbi", "axisbank",
    "hdfcbank", "kotak", "indus", "barodampay", "unionbankofindia",
    "cbin", "cnrb", "idfcfirst", "rbl", "pnb", "federal",
})

# Patterns that look like real account identifiers only when preceded
# by a contextual keyword.
_ACCOUNT_CONTEXT_RE = re.compile(
    r"\b(?:account|a/c|acct|iban|ifsc|routing|sort\s*code|swift|bic)"
    r"\s*(?:number|no\.?|id|code)?\s*[:=\-]\s*([A-Z0-9]{4,34})\b",
    re.I,
)

# Sensitive information request detection patterns
SENSITIVE_PATTERNS = [
    (r"\b(?:otp|one[- ]time[- ]password|verification code|security code)\b|(?:ओटीपी|सत्यापन कोड)", "One-Time Password (OTP)"),
    (r"\b(?:password|login credentials|security questions?|passcode|pin)\b|(?:पासवर्ड|पिन)", "Password or PIN"),
    (r"\b(?:aadhaar|pan card|passport|ssn|social security|driving license|voter id|national id)\b|(?:आधार|पैन कार्ड)", "Government Identity Document"),
    (r"\b(?:bank account details|internet banking|card number|cvv|expiry date|atm pin)\b|(?:बैंक खाता|सीवीवी)", "Banking / Card Details"),
]

# Negation cues that reverse the meaning of a request verb.
_NEGATION_RE = re.compile(
    r"\b(?:never|not|don't|do not|don\'t|no need to|avoid|nahi|mat|कभी नहीं|ना करें|मत)\b",
    re.I,
)

# Request verbs that indicate someone is *asking* for sensitive information.
_REQUEST_CUE_RE = re.compile(
    r"\b(?:send|share|provide|upload|confirm|verify|enter|submit|reply with|bhejo|batao|दीजिए|भेजें)\b",
    re.I,
)


def _is_upi_id(candidate: str) -> bool:
    """Return True only if the candidate looks like a genuine UPI handle."""
    if "@" not in candidate:
        return False
    local, domain = candidate.rsplit("@", 1)
    return domain.lower() in _UPI_HANDLE_SUFFIXES


def _is_ordinary_email(candidate: str) -> bool:
    """Return True if the candidate looks like an ordinary email address."""
    if "@" not in candidate:
        return False
    parts = candidate.rsplit("@", 1)
    if len(parts) != 2:
        return False
    domain = parts[1].lower()
    # Contains a dot → likely a full domain name (billing@vendor.com)
    if "." in domain:
        return True
    # Matches a well-known email provider shorthand
    if domain in _EMAIL_PROVIDER_DOMAINS:
        return True
    return False


def extract_payment_indicators(text: str) -> List[Dict[str, str]]:
    """Extracts payment identifiers (accounts, UPIs, crypto, payment handles).

    Key fixes:
    - Only matches account numbers preceded by explicit context keywords
      (e.g. "A/C: 1234567890"), not random words after "account".
    - Only classifies foo@bar as a UPI ID if bar is a known UPI suffix.
    - Rejects ordinary email addresses (billing@vendor.com).
    - Rejects short words or common English words extracted from context.
    """
    text = str(text or "")
    found: Dict[str, str] = {}

    # 1. Contextual account numbers (require keyword + separator + number)
    for match in _ACCOUNT_CONTEXT_RE.finditer(text):
        val = match.group(1).strip().upper()
        # Reject if it looks like a domain suffix or a short common word
        if len(val) >= 4 and not val.endswith((".COM", ".ORG", ".NET", ".IN", ".IO")):
            # Reject common English words that appear after "account"
            if val.isalpha() and len(val) <= 8:
                continue  # Skip words like "DETAILS", "NUMBER", "INFO"
            found[val] = "Account / Identifier"

    # 2. Specific UPI handle detection — only known UPI suffixes
    upi_candidates = re.findall(
        r"\b([a-zA-Z0-9.\-_]{2,32}@[a-zA-Z0-9]{2,20})\b", text, re.I
    )
    for u in upi_candidates:
        candidate = u.strip().lower()
        if _is_upi_id(candidate) and not _is_ordinary_email(candidate):
            found[candidate] = "UPI ID"

    # 3. Crypto addresses
    for eth in re.findall(r"\b(0x[a-fA-F0-9]{40})\b", text):
        found[eth] = "Ethereum / Crypto Address"
    for btc in re.findall(
        r"\b([13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-HJ-NP-Z0-9]{25,39})\b", text
    ):
        found[btc] = "Bitcoin Address"

    # 4. PayPal handles
    for pp in re.findall(r"\b(paypal\.me/[A-Za-z0-9._-]+)\b", text, re.I):
        found[pp.lower()] = "PayPal Handle"

    return [{"value": val, "type": typ} for val, typ in sorted(found.items())]


def extract_sensitive_requests(text: str) -> List[str]:
    """Identifies requests for credentials, OTPs, or identity documents.

    Key fix: handles negation. "Never share your password or OTP" is NOT
    classified as a request to share credentials. Works for English, Hindi,
    and Hinglish word order.
    """
    text = str(text or "")
    found = []

    # Check if ANY request cue exists in the text
    request_positions = list(_REQUEST_CUE_RE.finditer(text))
    if not request_positions:
        # No request verb at all — sensitive terms may still appear but
        # there's no actionable request being made
        return []

    # Check whether the entire text is primarily a negation/advisory context.
    # Look at each request verb and see if it's negated.
    has_unnegated_request = False
    for req_match in request_positions:
        # Look at the 120 characters before the request verb for negation
        prefix_start = max(0, req_match.start() - 120)
        prefix = text[prefix_start:req_match.start()]
        if not _NEGATION_RE.search(prefix):
            has_unnegated_request = True
            break

    if not has_unnegated_request:
        # All request cues are negated → this is a warning/advisory, not a request
        return []

    for pattern, name in SENSITIVE_PATTERNS:
        matches = list(re.finditer(pattern, text, re.I))
        for m in matches:
            # Check for negation in the 120 characters before this sensitive term.
            # This handles both English ("Never share your password") and
            # Hindi ("कभी नहीं भेजें अपना पासवर्ड") word orders.
            prefix_start = max(0, m.start() - 120)
            prefix = text[prefix_start:m.start()]
            if _NEGATION_RE.search(prefix):
                continue  # Negated mention — skip

            # Require either an unnegated request cue or an inherently dangerous pattern
            if has_unnegated_request or "password" in pattern or "otp" in pattern:
                found.append(name)
                break  # One match per category is enough

    return sorted(set(found))


def extract_domains_from_text(text: str) -> List[str]:
    """Extracts unique host domains from links in text."""
    urls = extract_urls(text)
    domains = set()
    for u in urls:
        d = domain_from_url(u.get("url", ""))
        if d:
            domains.add(d)
    return sorted(domains)


def _extract_full_urls(text: str) -> Dict[str, str]:
    """Returns {url: domain} for all URLs in text."""
    urls = extract_urls(text)
    result = {}
    for u in urls:
        url = u.get("url", "")
        d = domain_from_url(url)
        if d:
            result[url] = d
    return result


def compare_conversations(
    earlier_text: str = "",
    newer_text: str = "",
    earlier_sender: str = "",
    newer_sender: str = "",
    earlier_reply_to: str = "",
    newer_reply_to: str = "",
    earlier_headers: Optional[Dict[str, str]] = None,
    newer_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Compares earlier correspondence with the newer message.
    Identifies differences and explains why each difference matters.
    Treats changes as reasons to verify, not proof of fraud.
    """
    earlier_headers = earlier_headers or {}
    newer_headers = newer_headers or {}

    # Resolve senders
    earlier_sender = earlier_sender or earlier_headers.get("From", "") or earlier_headers.get("from", "")
    newer_sender = newer_sender or newer_headers.get("From", "") or newer_headers.get("from", "")

    # Resolve reply-to
    earlier_reply_to = earlier_reply_to or earlier_headers.get("Reply-To", "") or earlier_headers.get("reply-to", "")
    newer_reply_to = newer_reply_to or newer_headers.get("Reply-To", "") or newer_headers.get("reply-to", "")

    has_comparison = bool(
        earlier_text.strip() or earlier_sender.strip() or earlier_reply_to.strip()
    )

    if not has_comparison:
        return {
            "has_comparison": False,
            "differences": [],
            "summary": "No earlier message provided for thread comparison.",
            "verification_checklist": [],
            "extra_score": 0,
        }

    differences: List[Dict[str, Any]] = []
    extra_score = 0

    # Track which fields were actually compared
    fields_compared = []
    fields_not_available = []

    # 1. Sender address comparison
    if earlier_sender.strip() and newer_sender.strip():
        fields_compared.append("sender")
        earlier_name, earlier_email = parseaddr(earlier_sender)
        newer_name, newer_email = parseaddr(newer_sender)

        earlier_addr = (earlier_email or earlier_sender).strip().lower()
        newer_addr = (newer_email or newer_sender).strip().lower()

        if earlier_addr != newer_addr:
            earlier_dom = address_domain(earlier_addr)
            newer_dom = address_domain(newer_addr)

            if earlier_dom and newer_dom and earlier_dom != newer_dom:
                differences.append({
                    "category": "sender",
                    "title": "Sender email domain changed",
                    "before": earlier_addr,
                    "after": newer_addr,
                    "why_it_matters": (
                        f"The earlier message came from @{earlier_dom}, but this message is from @{newer_dom}. "
                        "Thread hijacking or lookalike domains are often used to impersonate established contacts."
                    ),
                    "advice": "Contact your partner using an official phone number or established contact channel you had before this message.",
                    "severity": "Needs verification"
                })
                extra_score += 25
            else:
                differences.append({
                    "category": "sender",
                    "title": "Sender email address changed within domain",
                    "before": earlier_addr,
                    "after": newer_addr,
                    "why_it_matters": (
                        f"The message is sent from a different address ({newer_addr}) than earlier messages ({earlier_addr}). "
                        "Organizations sometimes assign new account managers, but sudden changes before financial or sensitive requests should be confirmed."
                    ),
                    "advice": "Confirm whether this new address belongs to the same team before sharing information.",
                    "severity": "Needs verification"
                })
                extra_score += 15
    elif newer_sender.strip() and not earlier_sender.strip():
        fields_not_available.append("earlier sender address")
    elif earlier_sender.strip() and not newer_sender.strip():
        fields_not_available.append("current sender address")

    # 2. Reply address / Reply-To comparison
    newer_name, newer_email = parseaddr(newer_sender)
    newer_from_addr = (newer_email or newer_sender).strip().lower()

    if newer_reply_to.strip():
        fields_compared.append("reply-to")
        _, n_reply_addr = parseaddr(newer_reply_to)
        n_reply = (n_reply_addr or newer_reply_to).strip().lower()

        if earlier_reply_to.strip():
            _, e_reply_addr = parseaddr(earlier_reply_to)
            e_reply = (e_reply_addr or earlier_reply_to).strip().lower()
            if n_reply != e_reply:
                differences.append({
                    "category": "reply_to",
                    "title": "Reply-To address changed from earlier messages",
                    "before": e_reply,
                    "after": n_reply,
                    "why_it_matters": (
                        f"Replies are now directed to {n_reply} instead of {e_reply}. "
                        "Attackers sometimes change the Reply-To address to divert the conversation away from the genuine sender."
                    ),
                    "advice": "Check the recipient field before hitting Reply to make sure you are not directing replies to an unexpected address.",
                    "severity": "Needs verification"
                })
                extra_score += 20
        elif newer_from_addr and address_domain(n_reply) != address_domain(newer_from_addr):
            differences.append({
                "category": "reply_to",
                "title": "Reply address routes to a different domain than sender",
                "before": f"Sender: {newer_from_addr}",
                "after": f"Reply-To: {n_reply}",
                "why_it_matters": (
                    f"Hitting 'Reply' will send your message to {n_reply} (@{address_domain(n_reply)}), "
                    f"not to {newer_from_addr} (@{address_domain(newer_from_addr)})."
                ),
                "advice": "Confirm the reply destination before sending private correspondence.",
                "severity": "Needs verification"
            })
            extra_score += 20

    # 3. Payment details comparison
    earlier_payments = extract_payment_indicators(earlier_text)
    newer_payments = extract_payment_indicators(newer_text)

    earlier_pay_vals = {p["value"] for p in earlier_payments}
    newer_pay_vals = {p["value"] for p in newer_payments}

    if earlier_text.strip() or newer_text.strip():
        fields_compared.append("payment details")

    if newer_pay_vals and (not earlier_pay_vals or newer_pay_vals != earlier_pay_vals):
        new_items = newer_pay_vals - earlier_pay_vals
        replaced = bool(earlier_pay_vals and new_items)
        before_str = ", ".join(sorted(earlier_pay_vals)) if earlier_pay_vals else "No payment details specified earlier"
        after_str = ", ".join(sorted(newer_pay_vals))

        if replaced:
            differences.append({
                "category": "payment",
                "title": "Payment details changed mid-conversation",
                "before": before_str,
                "after": after_str,
                "why_it_matters": (
                    "The recipient's payment destination (account, UPI, or handle) changed from previous messages. "
                    "Invoice redirection and payment diversion scams often claim an account was updated, audited, or changed."
                ),
                "advice": (
                    "Call the supplier or recipient on a phone number you already know from prior invoices or contracts. "
                    "Do NOT call phone numbers printed in this new email to verify the payment change. "
                    "A change alone is not proof of fraud."
                ),
                "severity": "Needs verification"
            })
            extra_score += 30
        elif new_items:
            differences.append({
                "category": "payment",
                "title": "New payment instruction introduced",
                "before": before_str,
                "after": after_str,
                "why_it_matters": (
                    "Payment instructions were introduced in this message that were not present in the earlier discussion."
                ),
                "advice": "Verify the payment purpose and recipient account independently before transferring funds.",
                "severity": "Needs verification"
            })
            extra_score += 15

    # 4. Links and external domains comparison
    earlier_urls = _extract_full_urls(earlier_text)
    newer_urls = _extract_full_urls(newer_text)
    earlier_domains = set(earlier_urls.values())
    newer_domains = set(newer_urls.values())
    introduced_domains = newer_domains - earlier_domains

    if earlier_text.strip() or newer_text.strip():
        fields_compared.append("links")

    if introduced_domains:
        differences.append({
            "category": "links",
            "title": "New website domain introduced in thread",
            "before": ", ".join(sorted(earlier_domains)) if earlier_domains else "No external links in earlier message",
            "after": ", ".join(sorted(introduced_domains)),
            "why_it_matters": (
                f"This message directs you to {', '.join(sorted(introduced_domains))}, which did not appear earlier in the conversation. "
                "Attackers often slip fresh credential-harvesting links or third-party storage links into ongoing conversations."
            ),
            "advice": "Verify whether the sender officially uses this external service before opening or entering credentials.",
            "severity": "Needs verification"
        })
        extra_score += 15

    # 4b. Same-domain URL path changes (legitimate links can change, but worth noting)
    shared_domains = earlier_domains & newer_domains
    if shared_domains:
        earlier_by_domain: Dict[str, Set[str]] = {}
        for url, dom in earlier_urls.items():
            earlier_by_domain.setdefault(dom, set()).add(url)
        newer_by_domain: Dict[str, Set[str]] = {}
        for url, dom in newer_urls.items():
            newer_by_domain.setdefault(dom, set()).add(url)

        for dom in sorted(shared_domains):
            old_urls = earlier_by_domain.get(dom, set())
            new_urls = newer_by_domain.get(dom, set())
            changed_urls = new_urls - old_urls
            if changed_urls and old_urls:
                differences.append({
                    "category": "links",
                    "title": f"Link destination changed within {dom}",
                    "before": ", ".join(sorted(old_urls)),
                    "after": ", ".join(sorted(changed_urls)),
                    "why_it_matters": (
                        f"The specific URL path on {dom} changed from the earlier message. "
                        "Legitimate links can change between messages (e.g. different pages, updated invoices). "
                        "However, link swaps within an ongoing thread are also used in credential-harvesting attacks."
                    ),
                    "advice": (
                        "Check that the destination page matches what you expect. "
                        "Hover over the link to confirm the full URL before clicking."
                    ),
                    "severity": "Informational"
                })
                # Lower score — this is informational, not a strong signal
                extra_score += 5

    # 5. Sensitive information request escalation
    earlier_sensitive = set(extract_sensitive_requests(earlier_text))
    newer_sensitive = set(extract_sensitive_requests(newer_text))
    new_sensitive_requests = newer_sensitive - earlier_sensitive

    if earlier_text.strip() or newer_text.strip():
        fields_compared.append("sensitive information requests")

    if new_sensitive_requests:
        differences.append({
            "category": "sensitive_request",
            "title": "Sudden request for sensitive information",
            "before": ", ".join(sorted(earlier_sensitive)) if earlier_sensitive else "No sensitive credentials or IDs requested earlier",
            "after": ", ".join(sorted(new_sensitive_requests)),
            "why_it_matters": (
                f"The message requests {', '.join(sorted(new_sensitive_requests))}. "
                "Earlier correspondence did not ask for this. Legitimate companies rarely ask for passwords, OTPs, or government IDs via unencrypted email replies."
            ),
            "advice": "Never share OTPs, passwords, or PINs. If verification documents are required, submit them only through the provider's verified official portal.",
            "severity": "Needs verification"
        })
        extra_score += 25

    # Summary — honest about what was and wasn't compared
    verification_checklist = [
        "Treat detected changes as reasons to verify, not automatic proof of fraud. Organizations legitimately update details from time to time.",
        "Verify changes out-of-band: contact the sender via a trusted phone number or office channel you had before this message.",
        "Never use contact information, phone numbers, or verification links contained inside the newer email to verify itself.",
    ]

    if differences:
        summary = f"{len(differences)} difference{'s' if len(differences) != 1 else ''} found between earlier and newer messages."
    else:
        compared_str = ", ".join(fields_compared) if fields_compared else "available fields"
        summary = f"No discrepancies found in the compared fields ({compared_str})."
        if fields_not_available:
            summary += f" Could not compare: {', '.join(fields_not_available)}."

    return {
        "has_comparison": True,
        "differences": differences,
        "summary": summary,
        "fields_compared": fields_compared,
        "fields_not_available": fields_not_available,
        "earlier": {
            "sender": earlier_sender,
            "reply_to": earlier_reply_to,
            "domains": sorted(earlier_domains),
            "payments": [p["value"] for p in earlier_payments],
            "sensitive": sorted(earlier_sensitive)
        },
        "newer": {
            "sender": newer_sender,
            "reply_to": newer_reply_to,
            "domains": sorted(newer_domains),
            "payments": [p["value"] for p in newer_payments],
            "sensitive": sorted(newer_sensitive)
        },
        "verification_checklist": verification_checklist,
        "extra_score": extra_score,
        "disclaimer": "Treat changes as reasons to verify, not automatic proof of fraud."
    }
