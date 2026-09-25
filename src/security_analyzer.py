"""
Security Forensics & URL Phishing Analyzer for SpamGuard AI.
Inspects email content for deceptive links, typosquatting domains,
suspicious TLDs, psychological coercion cues, and email authentication headers.
"""

import re
import urllib.parse
from typing import List, Dict, Any, Optional

# Suspicious high-risk top-level domains frequently abused by phishing & spam operations
SUSPICIOUS_TLDS = {
    "ru", "xyz", "top", "tk", "ml", "ga", "cf", "gq", "work",
    "click", "buzz", "fit", "rest", "country", "stream", "live",
    "cam", "icu", "link", "online", "site", "vip", "racing"
}

# High-profile brands frequently targeted by spear-phishing & credential harvesting
TARGETED_BRANDS = [
    "paypal", "google", "microsoft", "apple", "amazon", "netflix",
    "chase", "wellsfargo", "bankofamerica", "citibank", "binance",
    "coinbase", "meta", "instagram", "facebook", "dhl", "fedex",
    "usps", "linkedin", "dropbox", "outlook", "office365", "adobe"
]

# Urgency and coercion patterns categorized by psychological exploitation tactic
PSYCHOLOGICAL_PATTERNS = {
    "urgency_deadline": [
        r"\b(?:within|in)\s+(?:24|48|12|2|1)\s+(?:hours|hrs|days|minutes|mins)\b",
        r"\b(?:immediately|urgent|urgently|right now|act now|hurry|final notice|deadline)\b",
        r"\b(?:expires?(?:\s+soon|\s+today|\s+in|\s+promptly)?)\b",
        r"\b(?:last chance|time-sensitive|limited time)\b"
    ],
    "fear_intimidation": [
        r"\b(?:account|access|service|card)\s+(?:(?:has been|is|was)\s+)?(?:suspended|locked|terminated|blocked|disabled|frozen)\b",
        r"\b(?:security alert|fraud alert|security breach|compromised|violation)\b",
        r"\b(?:unauthorized|suspicious|illegal|fraudulent)\s+(?:login|activity|access|transaction|charge)\b",
        r"\b(?:legal action|law enforcement|court|penalty|prosecution|warrant)\b"
    ],
    "financial_coercion": [
        r"\b(?:wire transfer|bitcoin|crypto(?:currency)?|wallet address|western union)\b",
        r"\b(?:cancel payment|cancel transaction|charge of \$[\d,]+|invoice unpaid)\b",
        r"\b(?:refund pending|overdue payment|unrecognized charge)\b"
    ],
    "greed_bait": [
        r"\b(?:congratulations|winner|you won|won \$[\d,]+|cash prize|lottery|jackpot)\b",
        r"\b(?:claim your (?:reward|prize|voucher|gift card|bonus))\b",
        r"\b(?:free (?:gift|iphone|cash|bitcoin|grant))\b"
    ]
}


def extract_urls(text: str) -> List[Dict[str, str]]:
    """
    Extracts URLs along with anchor text if HTML tags are present,
    or bare URLs from plain text.
    """
    results = []
    seen = set()

    # 1. Check for HTML anchor tags: <a href="URL">ANCHOR_TEXT</a>
    anchor_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    for match in anchor_pattern.finditer(text):
        url = match.group(1).strip()
        anchor_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        if url and url not in seen:
            seen.add(url)
            results.append({
                "url": url,
                "anchor_text": anchor_text,
                "is_html_link": True
            })

    # 2. Extract plain text URLs
    url_pattern = re.compile(r'https?://[^\s<>"\')]+|www\.[^\s<>"\')]+', re.IGNORECASE)
    for match in url_pattern.finditer(text):
        raw_url = match.group(0).rstrip(".,;:!?")
        normalized_url = raw_url if raw_url.startswith("http") else "http://" + raw_url
        if normalized_url not in seen:
            seen.add(normalized_url)
            results.append({
                "url": normalized_url,
                "anchor_text": "",
                "is_html_link": False
            })

    return results


def analyze_domain(domain_str: str) -> Dict[str, Any]:
    """
    Analyzes a domain for typosquatting, suspicious TLDs, and IP addresses.
    """
    clean_domain = domain_str.lower().strip()
    # Remove port if present
    if ":" in clean_domain:
        clean_domain = clean_domain.split(":")[0]

    is_ip = bool(re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', clean_domain))
    tld = clean_domain.split(".")[-1] if "." in clean_domain else ""
    is_suspicious_tld = tld in SUSPICIOUS_TLDS

    # Check for brand spoofing / typosquatting
    impersonated_brand = None
    typosquat_flags = []

    # Strip subdomains for targeted analysis
    domain_parts = clean_domain.split(".")
    core_name = domain_parts[-2] if len(domain_parts) >= 2 else clean_domain

    for brand in TARGETED_BRANDS:
        # Exact brand substring with extra hyphens/words (e.g., chase-security-login.com, paypal-verify.com)
        if brand in clean_domain and clean_domain != f"{brand}.com" and not clean_domain.endswith(f".{brand}.com"):
            impersonated_brand = brand
            typosquat_flags.append(f"Contains brand '{brand}' in suspicious non-official domain")
            break

        # Homoglyphs & Leetspeak substitution (e.g., paypa1, g00gle, micr0soft, armazon)
        substitutions = {
            "0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
            "8": "b", "@": "a", "vv": "w", "rn": "m"
        }
        normalized_core = core_name
        for fake_char, real_char in substitutions.items():
            normalized_core = normalized_core.replace(fake_char, real_char)

        if brand in normalized_core and brand not in core_name:
            impersonated_brand = brand
            typosquat_flags.append(f"Character substitution/homoglyph mimicking '{brand}' (detected: '{core_name}')")
            break

    return {
        "domain": clean_domain,
        "is_ip_address": is_ip,
        "tld": tld,
        "is_suspicious_tld": is_suspicious_tld,
        "impersonated_brand": impersonated_brand,
        "typosquat_flags": typosquat_flags,
        "is_suspicious": is_ip or is_suspicious_tld or bool(impersonated_brand)
    }


def analyze_urls(urls: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Evaluates extracted URLs for deceptive destinations and high-risk domains.
    """
    url_reports = []
    has_deceptive_link = False
    has_suspicious_domain = False
    has_ip_link = False

    for item in urls:
        raw_url = item["url"]
        anchor = item.get("anchor_text", "")

        try:
            parsed = urllib.parse.urlparse(raw_url)
            domain = parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            domain = raw_url

        domain_info = analyze_domain(domain)

        # Deceptive link check: Anchor displays a trusted URL/brand but points elsewhere
        # Example: Anchor says "https://paypal.com" but href is "http://attacker.ru"
        is_deceptive = False
        deceptive_reason = None
        if anchor:
            anchor_lower = anchor.lower()
            if ("http://" in anchor_lower or "https://" in anchor_lower or ".com" in anchor_lower):
                # Anchor looks like a URL
                try:
                    anchor_parsed = urllib.parse.urlparse(anchor if anchor.startswith("http") else "http://" + anchor)
                    anchor_domain = anchor_parsed.netloc or anchor_parsed.path.split("/")[0]
                    if anchor_domain and anchor_domain != domain and not domain.endswith("." + anchor_domain):
                        is_deceptive = True
                        deceptive_reason = f"Displayed link '{anchor_domain}' diverges from actual destination '{domain}'"
                except Exception:
                    pass

            for brand in TARGETED_BRANDS:
                if brand in anchor_lower and brand not in domain:
                    is_deceptive = True
                    deceptive_reason = f"Text claims to be '{brand}' but link targets '{domain}'"
                    break

        if is_deceptive:
            has_deceptive_link = True
        if domain_info["is_suspicious"]:
            has_suspicious_domain = True
        if domain_info["is_ip_address"]:
            has_ip_link = True

        url_reports.append({
            "url": raw_url,
            "anchor_text": anchor,
            "domain": domain,
            "domain_analysis": domain_info,
            "is_deceptive": is_deceptive,
            "deceptive_reason": deceptive_reason
        })

    return {
        "url_count": len(urls),
        "urls": url_reports,
        "has_deceptive_link": has_deceptive_link,
        "has_suspicious_domain": has_suspicious_domain,
        "has_ip_link": has_ip_link
    }


def analyze_psychological_coercion(text: str) -> Dict[str, Any]:
    """
    Detects urgency, fear, intimidation, financial pressure, and greed cues.
    """
    matched_tactics = {}
    total_matches = 0

    for tactic, patterns in PSYCHOLOGICAL_PATTERNS.items():
        tactic_matches = []
        for pattern in patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                tactic_matches.extend(found)
        if tactic_matches:
            # Deduplicate while preserving order
            seen = set()
            unique_matches = [m for m in tactic_matches if not (m.lower() in seen or seen.add(m.lower()))]
            matched_tactics[tactic] = unique_matches
            total_matches += len(unique_matches)

    # Calculate psychological urgency score from 0.0 to 1.0
    urgency_score = min(1.0, total_matches * 0.25)

    return {
        "coercion_tactics": matched_tactics,
        "total_cues_found": total_matches,
        "urgency_score": round(urgency_score, 2),
        "has_high_urgency": urgency_score >= 0.50
    }


def inspect_email_security(raw_text: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Performs full security forensic analysis on an email's text and headers.
    """
    extracted_urls = extract_urls(raw_text)
    url_analysis = analyze_urls(extracted_urls)
    psycho_analysis = analyze_psychological_coercion(raw_text)

    # Header authentication checks if headers are provided
    auth_report = {
        "spf": "UNKNOWN",
        "dkim": "UNKNOWN",
        "dmarc": "UNKNOWN",
        "return_path_mismatch": False
    }

    if headers:
        for k, v in headers.items():
            key_lower = k.lower()
            val_lower = str(v).lower()
            if "received-spf" in key_lower:
                auth_report["spf"] = "PASS" if "pass" in val_lower else ("FAIL" if "fail" in val_lower else "SOFTFAIL")
            elif "dkim-signature" in key_lower or "authentication-results" in key_lower:
                if "dkim=pass" in val_lower:
                    auth_report["dkim"] = "PASS"
                elif "dkim=fail" in val_lower:
                    auth_report["dkim"] = "FAIL"
                if "dmarc=pass" in val_lower:
                    auth_report["dmarc"] = "PASS"
                elif "dmarc=fail" in val_lower:
                    auth_report["dmarc"] = "FAIL"

    return {
        "url_forensics": url_analysis,
        "psychological_forensics": psycho_analysis,
        "authentication_forensics": auth_report,
        "threat_indicators_detected": (
            url_analysis["has_deceptive_link"] or
            url_analysis["has_suspicious_domain"] or
            url_analysis["has_ip_link"] or
            psycho_analysis["has_high_urgency"]
        )
    }
