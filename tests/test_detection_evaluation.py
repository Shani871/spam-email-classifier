"""Tests for the detection evaluation benchmark and comparison with historical ML metrics."""
import pytest
from src.detection_evaluation import load_evaluation_set, evaluate_detection


def test_load_evaluation_set():
    data = load_evaluation_set()
    assert len(data) >= 15
    # Verify required keys
    for item in data:
        assert "id" in item
        assert "text" in item
        assert item["ground_truth"] in {"scam", "legitimate"}
        assert item["language"] in {"English", "Hindi", "Hinglish"}
        assert item.get("synthetic") is True
        assert "synthetic_source" in item


def test_languages_covered():
    data = load_evaluation_set()
    languages = {item["language"] for item in data}
    assert languages == {"English", "Hindi", "Hinglish"}


def test_urgent_genuine_examples_present():
    data = load_evaluation_set()
    urgent_legit = [item for item in data if item["scenario_type"] == "urgent_genuine" and item["ground_truth"] == "legitimate"]
    assert len(urgent_legit) >= 3


def test_evaluate_detection_metrics():
    res = evaluate_detection()
    assert "total_samples" in res
    assert res["total_samples"] >= 15
    assert "false_warnings_count" in res
    assert "missed_scams_count" in res
    assert "detection_rate" in res
    assert "historical_classifier_comparison" in res
    # Ensure synthetic disclaimer is present
    assert "synthetic" in res["synthetic_notice"].lower()
    # Ensure language breakdown exists
    assert "English" in res["by_language"]
    assert "Hindi" in res["by_language"]
    assert "Hinglish" in res["by_language"]


def test_historical_ml_separated_from_scamguard():
    res = evaluate_detection()
    hist = res["historical_classifier_comparison"]
    assert "scams_detected" in hist
    assert "missed_scams" in hist
    assert "why_different" in hist
    assert "Historical spam classifiers" in hist["why_different"]
