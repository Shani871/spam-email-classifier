"""
Unit tests for AI threat intelligence scoring and autonomous inbox automation worker.
"""

import pytest
from src.ai_threat_intelligence import compute_threat_intelligence
from src.automation_worker import InboxAutomationWorker, get_global_worker


def test_compute_threat_intelligence_phishing():
    malicious_text = (
        "Subject: URGENT: Your PayPal Account Has Been Suspended!\n\n"
        "Unauthorized login detected. To prevent permanent lock, verify your bank credentials immediately: "
        "http://paypa1-security-verify-account-now.xyz"
    )
    report = compute_threat_intelligence(malicious_text, model_type="svm")
    assert report["threat_score"] >= 75
    assert report["threat_level"] in ["HIGH THREAT", "CRITICAL ATTACK"]
    assert report["is_action_required"] is True
    assert len(report["tactics_detected"]) > 0
    assert len(report["security_advisories"]) > 0
    assert "Credential" in report["attack_vector"] or "Brand" in report["attack_vector"]


def test_compute_threat_intelligence_clean():
    clean_text = (
        "Subject: Project Status & Architecture Review\n\n"
        "Hi Alex, please find the updated project report and meeting minutes attached. "
        "Looking forward to our sync tomorrow morning at 10 AM. Best regards, Shani."
    )
    report = compute_threat_intelligence(clean_text, model_type="svm")
    assert report["threat_score"] < 40
    assert report["threat_level"] in ["CLEAN / SAFE", "LOW RISK"]
    assert report["is_action_required"] is False
    assert report["attack_vector"] == "Benign Business / Personal Communication"


def test_inbox_automation_worker_lifecycle():
    worker = get_global_worker()
    worker.clear_audit_logs()

    # Initial state
    assert worker.is_running() is False
    stats = worker.get_stats()
    assert stats["total_scanned"] == 0

    # Run single manual pass
    results = worker.scan_once()
    assert len(results) > 0
    updated_stats = worker.get_stats()
    assert updated_stats["total_scanned"] >= 1
    assert updated_stats["last_scan_time"] is not None

    recent_logs = worker.get_recent_audit_logs(limit=5)
    assert len(recent_logs) > 0
    assert "threat_score" in recent_logs[0]
    assert "action" in recent_logs[0]

    # Test start and stop
    worker.start()
    assert worker.is_running() is True
    worker.stop()
    assert worker.is_running() is False
