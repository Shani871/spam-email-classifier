"""
Unit tests for email attachment and payload forensics.
"""

import pytest
from src.attachment_analyzer import analyze_attachment_metadata, inspect_email_attachments


def test_double_extension_detection():
    # Double extension evasion: invoice.pdf.exe
    rep = analyze_attachment_metadata("invoice.pdf.exe")
    assert rep["is_dangerous"] is True
    assert rep["risk_level"] == "CRITICAL"
    assert "Double Extension Disguise" in rep["detected_tactics"]


def test_executable_and_script_detection():
    rep_scr = analyze_attachment_metadata("security_patch.scr")
    assert rep_scr["is_dangerous"] is True
    assert rep_scr["risk_level"] == "HIGH"
    assert "Executable Payload" in rep_scr["detected_tactics"]

    rep_vbs = analyze_attachment_metadata("payment_update.vbs")
    assert rep_vbs["is_dangerous"] is True
    assert rep_vbs["risk_level"] == "HIGH"


def test_macro_document_detection():
    rep = analyze_attachment_metadata("Q3_Financial_Statement.xlsm")
    assert rep["is_dangerous"] is True
    assert rep["risk_level"] == "HIGH"
    assert "Macro-Enabled Document" in rep["detected_tactics"]


def test_benign_attachments():
    rep_pdf = analyze_attachment_metadata("project_report.pdf")
    assert rep_pdf["is_dangerous"] is False
    assert rep_pdf["risk_level"] == "SAFE"

    rep_png = analyze_attachment_metadata("screenshot.png")
    assert rep_png["is_dangerous"] is False
    assert rep_png["risk_level"] == "SAFE"


def test_inspect_email_attachments_batch():
    attachments = [
        {"filename": "contract.docx", "size": 15000},
        {"filename": "remittance_advice.pdf.exe", "size": 450000}
    ]
    report = inspect_email_attachments(attachments)
    assert report["attachment_count"] == 2
    assert report["has_dangerous_attachments"] is True
    assert report["highest_risk_level"] == "CRITICAL"
    assert report["threat_penalty"] == 40


def test_compute_threat_intelligence_with_malicious_attachment():
    from src.ai_threat_intelligence import compute_threat_intelligence
    text = "Please find the requested invoice attached for processing."
    attachments = [{"filename": "invoice_october.pdf.exe", "size": 250000}]
    res = compute_threat_intelligence(text, attachments=attachments)
    assert res["threat_score"] >= 40
    assert "attachment_forensics" in res
    assert res["attachment_forensics"]["has_dangerous_attachments"] is True
    assert any("ATTACHMENT RISK" in adv for adv in res["security_advisories"])
