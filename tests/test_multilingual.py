"""Tests for multilingual support (English, Hindi, Hinglish) and English fallback."""
import pytest
from src.multilingual import (
    ASSESSMENT_LABELS,
    ASSESSMENT_SUMMARIES,
    localize_evidence_item,
    get_localized_recovery_steps,
    get_language_limitations
)
from src.scam_assistant import recovery_steps


def test_assessment_labels_consistency():
    for lang in ["English", "Hindi", "Hinglish"]:
        assert lang in ASSESSMENT_LABELS
        assert "High risk" in ASSESSMENT_LABELS[lang]
        assert "Needs verification" in ASSESSMENT_LABELS[lang]
        assert "No strong warning found" in ASSESSMENT_LABELS[lang]
        assert "Unable to assess" in ASSESSMENT_LABELS[lang]


def test_assessment_summaries():
    for lang in ["English", "Hindi", "Hinglish"]:
        assert lang in ASSESSMENT_SUMMARIES
        for key in ["High risk", "Needs verification", "No strong warning found", "Unable to assess"]:
            assert key in ASSESSMENT_SUMMARIES[lang]
            assert len(ASSESSMENT_SUMMARIES[lang][key]) > 10


def test_localize_evidence_item_hindi_and_hinglish():
    item = {
        "title": "Recruitment payment requested",
        "advice": "Verify the role through official careers page.",
        "excerpt": "pay registration fee"
    }
    # Hindi localization
    hin_item = localize_evidence_item(item, "Hindi")
    assert "भर्ती" in hin_item["title"] or "भुगतान" in hin_item["title"]
    assert "आधिकारिक" in hin_item["advice"]

    # Hinglish localization
    hng_item = localize_evidence_item(item, "Hinglish")
    assert "Job" in hng_item["title"] or "fees" in hng_item["title"]
    assert "careers page" in hng_item["advice"]

    # English unchanged
    eng_item = localize_evidence_item(item, "English")
    assert eng_item["title"] == item["title"]


def test_localize_evidence_fallback_to_english():
    # An unknown evidence title should gracefully fall back to original English text
    unknown_item = {
        "title": "Novel zero-day indicator",
        "advice": "Check network logs immediately.",
        "excerpt": "sample"
    }
    res = localize_evidence_item(unknown_item, "Hindi")
    assert res["title"] == "Novel zero-day indicator"
    assert res["advice"] == "Check network logs immediately."


def test_recovery_steps_all_stages():
    stages = [
        "Only received the message",
        "Clicked a link",
        "Shared a password or OTP",
        "Sent money or payment details"
    ]
    for lang in ["English", "Hindi", "Hinglish"]:
        for stage in stages:
            steps = get_localized_recovery_steps(stage, lang)
            assert len(steps) >= 3
            # Delegated function via scam_assistant
            assert len(recovery_steps(stage, lang)) >= 3


def test_honest_language_limitations():
    hin_limits = get_language_limitations("Hindi")
    assert any("नियम-आधारित" in lim or "मशीन लर्निंग" in lim for lim in hin_limits)

    hng_limits = get_language_limitations("Hinglish")
    assert any("Hinglish" in lim or "ML model" in lim for lim in hng_limits)

    eng_limits = get_language_limitations("English")
    assert len(eng_limits) >= 2


def test_evidence_localizations_complete_coverage():
    """Every evidence key in EVIDENCE_LOCALIZATIONS must have both Hindi and Hinglish entries."""
    from src.multilingual import EVIDENCE_LOCALIZATIONS
    languages = ["Hindi", "Hinglish"]
    missing = []
    for key, translations in EVIDENCE_LOCALIZATIONS.items():
        for lang in languages:
            if lang not in translations:
                missing.append(f"{key!r} missing {lang}")
            else:
                entry = translations[lang]
                if not entry.get("title") or not entry.get("advice"):
                    missing.append(f"{key!r}/{lang} has empty title or advice")
    assert not missing, "Incomplete translations:\n" + "\n".join(missing)


def test_recovery_guides_complete_coverage():
    """Every recovery stage in English must also exist in Hindi and Hinglish."""
    from src.multilingual import RECOVERY_GUIDES
    english_stages = set(RECOVERY_GUIDES["English"].keys())
    for lang in ["Hindi", "Hinglish"]:
        lang_stages = set(RECOVERY_GUIDES.get(lang, {}).keys())
        missing = english_stages - lang_stages
        assert not missing, f"{lang} is missing recovery stages: {missing}"
