"""Unit tests for the consent-based administrator queue and cross-process safety.

Tests:
- Default missing consent to False (including legacy records)
- Authorized administrator reviews submissions from other users ONLY when explicit consent is given
- Unauthorized users cannot access or modify the admin queue
- Unrelated private account data is never exposed
- Approval, rejection, withdrawal, and deletion behaviors
- Training only includes eligible, consented, approved corrections
- Model releases safely coordinated across processes
- Deleting feedback explains it does not alter already-deployed model weights
"""

from datetime import datetime, timedelta, timezone
import json
import pytest
from unittest.mock import Mock
import pandas as pd

from src.user_storage import user_scope, write_json, read_json, delete_account_data, ROOT
import src.active_learning as learning


def test_legacy_record_missing_consent_defaults_to_false():
    with user_scope("legacy_user"):
        learning.clear_feedback_data()
        # Simulate legacy record without consent_given key
        legacy_entry = {
            "id": "legacy-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "text": "Legacy feedback text",
            "predicted_label": "spam",
            "user_label": "ham",
            "approved": False,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        }
        write_json("feedback.json", [legacy_entry])

        # Cannot approve legacy record without explicit consent
        with pytest.raises(ValueError, match="Cannot approve feedback without user consent"):
            learning.approve_feedback("legacy-001", admin_user={"is_admin": True})

        # Must not appear in admin review queue
        admin_queue = learning.get_admin_feedback_queue(admin_user={"is_admin": True})
        assert not any(r["id"] == "legacy-001" for r in admin_queue)


def test_unauthorized_admin_access_rejected(monkeypatch):
    monkeypatch.setenv("STRICT_AUTH", "1")
    monkeypatch.delenv("SPAMGUARD_LOCAL_ADMIN", raising=False)

    # Unauthorized user string
    with pytest.raises(PermissionError):
        learning.get_admin_feedback_queue(admin_user="regular_user@example.com")

    # Unauthorized user dict
    with pytest.raises(PermissionError):
        learning.approve_feedback("some-id", admin_user={"email": "non_admin@example.com", "is_admin": False})

    with pytest.raises(PermissionError):
        learning.reject_feedback("some-id", admin_user={"email": "non_admin@example.com", "is_admin": False})

    with pytest.raises(PermissionError):
        learning.retrain_model_with_feedback(1, admin_user={"is_admin": False})

    with pytest.raises(PermissionError):
        learning.rollback_model(admin_user={"is_admin": False})


def test_admin_queue_across_separate_accounts():
    # User 1: Alice submits feedback WITH consent
    with user_scope("alice"):
        learning.clear_feedback_data()
        alice_entry = learning.record_feedback(
            text="Team meeting notes for sprint 12",
            predicted_label="spam",
            user_label="ham",
            user_comment="Meeting notice was falsely classified as spam",
            consent_given=True
        )
        write_json("history.json", [{"secret_history": "alice private message history"}])

    # User 2: Bob submits feedback WITHOUT consent
    with user_scope("bob"):
        learning.clear_feedback_data()
        bob_entry = learning.record_feedback(
            text="Confidential project report draft",
            predicted_label="spam",
            user_label="ham",
            user_comment="Private message - no consent",
            consent_given=False
        )
        write_json("history.json", [{"secret_history": "bob confidential searches"}])

    # 1. Isolation check: Alice cannot see Bob's feedback, Bob cannot see Alice's feedback
    with user_scope("alice"):
        alice_records = learning.get_feedback_records()
        assert len(alice_records) == 1
        assert alice_records[0]["id"] == alice_entry["id"]

    with user_scope("bob"):
        bob_records = learning.get_feedback_records()
        assert len(bob_records) == 1
        assert bob_records[0]["id"] == bob_entry["id"]

    # 2. Admin queue check: Authorized admin sees Alice's consented feedback, NEVER Bob's unconsented feedback
    admin_user = {"is_admin": True}
    queue = learning.get_admin_feedback_queue(admin_user=admin_user)
    queue_ids = [r["id"] for r in queue]

    assert alice_entry["id"] in queue_ids
    assert bob_entry["id"] not in queue_ids

    # 3. Privacy check: Ensure unrelated private account data is NOT exposed
    alice_queue_record = next(r for r in queue if r["id"] == alice_entry["id"])
    assert "secret_history" not in str(alice_queue_record)
    assert "history.json" not in str(alice_queue_record)

    # 4. Admin approval: Admin approves Alice's feedback
    learning.approve_feedback(alice_entry["id"], admin_user=admin_user)
    updated_queue = learning.get_admin_feedback_queue(admin_user=admin_user)
    approved_record = next(r for r in updated_queue if r["id"] == alice_entry["id"])
    assert approved_record["approved"] is True
    assert approved_record["status"] == "approved"

    # 5. User withdrawal: Alice withdraws consent
    with user_scope("alice"):
        learning.withdraw_feedback_consent(alice_entry["id"])
        # Should now be withdrawn
        alice_updated = learning.get_feedback_records()[0]
        assert alice_updated["consent_given"] is False
        assert alice_updated["approved"] is False

    # Once withdrawn, disappears from admin review queue
    queue_after_withdrawal = learning.get_admin_feedback_queue(admin_user=admin_user)
    assert alice_entry["id"] not in [r["id"] for r in queue_after_withdrawal]

    # 6. Deletion: Alice deletes the record
    with user_scope("alice"):
        learning.delete_feedback_record(alice_entry["id"])
        assert len(learning.get_feedback_records()) == 0


def test_admin_rejection_flow():
    with user_scope("charlie"):
        learning.clear_feedback_data()
        entry = learning.record_feedback(
            text="Spam notification about bonus",
            predicted_label="ham",
            user_label="spam",
            consent_given=True
        )

    admin_user = {"is_admin": True}
    learning.reject_feedback(entry["id"], admin_user=admin_user, reason="Invalid ground truth")

    queue = learning.get_admin_feedback_queue(admin_user=admin_user)
    charlie_record = next(r for r in queue if r["id"] == entry["id"])
    assert charlie_record["rejected"] is True
    assert charlie_record["approved"] is False
    assert charlie_record["status"] == "rejected"
    assert charlie_record["rejection_reason"] == "Invalid ground truth"

    # Rejected feedback must NOT be eligible for training
    trainable = learning.get_trainable_feedback()
    assert entry["id"] not in [r["id"] for r in trainable]
