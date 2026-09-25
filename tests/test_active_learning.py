"""
Unit tests for Active Learning, human-in-the-loop feedback logging, and retraining.
"""

import os
import pytest
from src.active_learning import (
    record_feedback,
    get_feedback_records,
    get_feedback_stats,
    clear_feedback_data
)


def test_record_and_get_feedback():
    clear_feedback_data()

    # Initial state
    stats = get_feedback_stats()
    assert stats["total_feedback"] == 0

    # Record false positive
    rec1 = record_feedback(
        text="Team sync tomorrow at 10 AM in Room 302",
        predicted_label="Spam",
        user_label="Ham",
        user_comment="Meeting invitation falsely flagged as spam"
    )
    assert rec1["predicted_label"] == "spam"
    assert rec1["user_label"] == "ham"

    # Record false negative
    rec2 = record_feedback(
        text="Claim your $500 Walmart voucher now",
        predicted_label="Ham",
        user_label="Spam",
        user_comment="Spam message missed by classifier"
    )
    assert rec2["predicted_label"] == "ham"
    assert rec2["user_label"] == "spam"

    # Check updated stats
    updated_stats = get_feedback_stats()
    assert updated_stats["total_feedback"] == 2
    assert updated_stats["false_positives_corrected"] == 1
    assert updated_stats["false_negatives_corrected"] == 1

    records = get_feedback_records()
    assert len(records) == 2


def test_record_feedback_validation():
    with pytest.raises(ValueError):
        record_feedback("", "Spam", "Ham")

    with pytest.raises(ValueError):
        record_feedback("Valid email text", "Spam", "InvalidLabel")
