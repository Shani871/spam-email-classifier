"""
Email Attachment & Payload Security Forensics for SpamGuard AI.
Analyzes attachment filenames, extensions, double extensions, macro-enabled documents,
and disguised payload formats commonly deployed in malware and spear-phishing campaigns.
"""

import os
import re
from typing import List, Dict, Any, Optional

# Executables, scripts, and disk image formats capable of arbitrary code execution
DANGEROUS_EXECUTABLE_EXTENSIONS = {
    "exe", "scr", "bat", "cmd", "ps1", "vbs", "vbe", "js", "jse",
    "wsf", "wsh", "hta", "cpl", "msc", "jar", "iso", "img", "vhd",
    "pif", "application", "gadget", "msp", "com", "reg"
}

# Macro-enabled office document extensions frequently weaponized in spear-phishing
MACRO_DOCUMENT_EXTENSIONS = {
    "xlsm", "xltm", "xlam", "docm", "dotm", "pptm", "potm", "ppam", "ppsm", "sldm"
}

# High-risk archive extensions used to bypass direct perimeter email gateway filters
ARCHIVE_EXTENSIONS = {
    "zip", "rar", "7z", "tar", "gz", "bz2", "xz", "cab", "ace", "arj"
}

# Standard benign document extensions
BENIGN_EXTENSIONS = {
    "pdf", "docx", "xlsx", "pptx", "txt", "csv", "png", "jpg", "jpeg", "gif", "svg", "mp4", "mp3"
}


def analyze_attachment_metadata(
    filename: str,
    file_size_bytes: int = 0,
    mime_type: str = ""
) -> Dict[str, Any]:
    """
    Evaluates an attachment's filename and metadata for cyber threat indicators.
    """
    clean_name = os.path.basename(str(filename or "")).strip()
    if not clean_name:
        return {
            "filename": "",
            "is_dangerous": False,
            "risk_level": "SAFE",
            "risk_reasons": ["Empty filename"],
            "detected_tactics": []
        }

    # Split all extension components (e.g. invoice.pdf.exe -> ['invoice', 'pdf', 'exe'])
    name_parts = clean_name.lower().split(".")
    primary_ext = name_parts[-1] if len(name_parts) > 1 else ""

    risk_reasons = []
    detected_tactics = []
    risk_level = "SAFE"

    # 1. Check for Double Extension Evasion (e.g. invoice.pdf.exe, contract.docx.vbs)
    if len(name_parts) > 2:
        inner_ext = name_parts[-2]
        if inner_ext in BENIGN_EXTENSIONS and primary_ext in (DANGEROUS_EXECUTABLE_EXTENSIONS | MACRO_DOCUMENT_EXTENSIONS):
            risk_reasons.append(
                f"Double Extension Evasion detected: masquerades as '.{inner_ext}' document with executable '.{primary_ext}' payload"
            )
            detected_tactics.append("Double Extension Disguise")
            risk_level = "CRITICAL"

    # 2. Check for Direct Executables / Scripts
    if primary_ext in DANGEROUS_EXECUTABLE_EXTENSIONS:
        risk_reasons.append(f"Dangerous executable/script format ('.{primary_ext}') capable of arbitrary code execution")
        detected_tactics.append("Executable Payload")
        if risk_level != "CRITICAL":
            risk_level = "HIGH"

    # 3. Check for Macro-Enabled Office Documents
    elif primary_ext in MACRO_DOCUMENT_EXTENSIONS:
        risk_reasons.append(
            f"Macro-enabled document format ('.{primary_ext}'). Malicious VBA macros can execute on open"
        )
        detected_tactics.append("Macro-Enabled Document")
        if risk_level != "CRITICAL":
            risk_level = "HIGH"

    # 4. Check for Compressed Archives
    elif primary_ext in ARCHIVE_EXTENSIONS:
        risk_reasons.append(
            f"Compressed archive file ('.{primary_ext}'). Archives are frequently used to obfuscate nested payloads"
        )
        detected_tactics.append("Compressed Container")
        if risk_level == "SAFE":
            risk_level = "SUSPICIOUS"

    # 5. Check for Suspicious Document Filename Keywords
    phishing_attachment_keywords = [
        "invoice", "receipt", "overdue", "payment", "wire", "remittance",
        "swift", "order", "statement", "salary", "bonus", "payroll"
    ]
    name_lower = clean_name.lower()
    for kw in phishing_attachment_keywords:
        if kw in name_lower and (primary_ext in DANGEROUS_EXECUTABLE_EXTENSIONS or primary_ext in MACRO_DOCUMENT_EXTENSIONS or primary_ext in ARCHIVE_EXTENSIONS):
            risk_reasons.append(f"Social engineering lure: filename references '{kw}' paired with non-standard document format")
            detected_tactics.append("Financial Lure Pairing")
            break

    # 6. MIME-type mismatch check if mime_type is provided
    if mime_type:
        mime_lower = mime_type.lower()
        if "pdf" in name_lower and "pdf" not in mime_lower:
            risk_reasons.append(f"MIME type mismatch: file named as PDF but declared as '{mime_type}'")
            detected_tactics.append("MIME Discrepancy")
            if risk_level == "SAFE":
                risk_level = "SUSPICIOUS"

    is_dangerous = risk_level in ["CRITICAL", "HIGH"]

    return {
        "filename": clean_name,
        "extension": primary_ext,
        "file_size_bytes": file_size_bytes,
        "is_dangerous": is_dangerous,
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "detected_tactics": detected_tactics
    }


def inspect_email_attachments(attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Inspects a list of attachments for an email message.
    """
    if not attachments:
        return {
            "attachment_count": 0,
            "has_dangerous_attachments": False,
            "highest_risk_level": "SAFE",
            "attachment_reports": [],
            "threat_penalty": 0
        }

    reports = []
    has_dangerous = False
    max_severity_rank = 0
    severity_ranks = {"SAFE": 0, "SUSPICIOUS": 1, "HIGH": 2, "CRITICAL": 3}
    highest_risk = "SAFE"

    for att in attachments:
        fname = att.get("filename", "")
        fsize = att.get("size", 0)
        fmime = att.get("mime_type", "")
        rep = analyze_attachment_metadata(fname, file_size_bytes=fsize, mime_type=fmime)
        reports.append(rep)

        if rep["is_dangerous"]:
            has_dangerous = True

        r_rank = severity_ranks.get(rep["risk_level"], 0)
        if r_rank > max_severity_rank:
            max_severity_rank = r_rank
            highest_risk = rep["risk_level"]

    # Calculate threat penalty for overall threat score
    threat_penalty = 0
    if highest_risk == "CRITICAL":
        threat_penalty = 40
    elif highest_risk == "HIGH":
        threat_penalty = 25
    elif highest_risk == "SUSPICIOUS":
        threat_penalty = 10

    return {
        "attachment_count": len(attachments),
        "has_dangerous_attachments": has_dangerous,
        "highest_risk_level": highest_risk,
        "attachment_reports": reports,
        "threat_penalty": threat_penalty
    }
