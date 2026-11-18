"""Database layer: schema, account isolation, ownership checks, retention, backups and JSON migration."""
from datetime import datetime, timedelta, timezone
import json
import importlib.util
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from src import db, user_storage
from src.user_storage import user_scope
import src.active_learning as learning

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrations_match_the_schema_definition():
    with db.get_engine().connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), db.metadata) == []
    assert db.health_check()


def test_database_url_shorthands_and_default(monkeypatch):
    monkeypatch.setenv("SPAMGUARD_DATABASE_URL", "postgres://u:p@host:5432/app")
    assert db.database_url() == "postgresql+psycopg://u:p@host:5432/app"
    monkeypatch.setenv("SPAMGUARD_DATABASE_URL", "postgresql://u:p@host/app")
    assert db.database_url() == "postgresql+psycopg://u:p@host/app"
    monkeypatch.delenv("SPAMGUARD_DATABASE_URL")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db.database_url().startswith("sqlite:///") and db.database_url().endswith("data/spamguard.db")


def test_accounts_are_stored_by_hash_only():
    with user_scope("person@example.com"):
        user_storage.add_history("High risk", 90, "General message")
        user_storage.set_sender_rule("x@example.com", "block")
    with db.get_engine().connect() as connection:
        accounts = {row[0] for row in connection.execute(db.history.select().with_only_columns(db.history.c.account_id))}
    assert accounts == {user_storage.account_id("person@example.com")}
    assert "person@example.com" not in str(accounts)


def test_users_cannot_withdraw_or_delete_someone_elses_feedback():
    with user_scope("alice"):
        entry = learning.record_feedback("Alice's correction", "spam", "ham", consent_given=True)
    with user_scope("mallory"):
        with pytest.raises(ValueError):
            learning.withdraw_feedback_consent(entry["id"])
        with pytest.raises(ValueError):
            learning.delete_feedback_record(entry["id"])
    queue = learning.get_admin_feedback_queue(admin_user={"is_admin": True})
    assert entry["id"] in [r["id"] for r in queue]
    with user_scope("alice"):
        learning.delete_feedback_record(entry["id"])
        assert learning.get_feedback_records() == []


def test_unconsented_feedback_cannot_be_approved_or_trained_on():
    entry = learning.record_feedback("No consent here", "spam", "ham", approved=True, consent_given=False)
    assert entry["status"] == "pending"
    with pytest.raises(ValueError, match="consent"):
        learning.approve_feedback(entry["id"], admin_user={"is_admin": True})
    assert learning.get_trainable_feedback() == []


def test_history_keeps_the_latest_entries_and_respects_retention(monkeypatch):
    monkeypatch.setattr(user_storage, "HISTORY_LIMIT_PER_ACCOUNT", 3)
    for score in range(5):
        user_storage.add_history("Needs verification", score, "General message")
    assert [r["score"] for r in user_storage.list_history()] == [4, 3, 2]


def test_sender_rules_switch_and_remove():
    user_storage.set_sender_rule("News@Example.com ", "trust")
    user_storage.set_sender_rule("news@example.com", "block")
    assert user_storage.get_sender_rules() == {"whitelist": [], "blacklist": ["news@example.com"]}
    assert user_storage.set_sender_rule("news@example.com", None)
    assert not user_storage.set_sender_rule("news@example.com", None)
    with pytest.raises(ValueError):
        user_storage.set_sender_rule("a@b.c", "maybe")


def test_account_deletion_removes_everything_and_leaves_a_marker():
    with user_scope("leaver"):
        user_storage.add_history("High risk", 90, "General message")
        learning.record_feedback("A correction", "spam", "ham", consent_given=True)
        user_storage.set_sender_rule("a@example.com", "trust")
        user_storage.delete_account_data()
        assert user_storage.list_history() == [] and user_storage.list_feedback() == []
        assert user_storage.get_sender_rules() == {"whitelist": [], "blacklist": []}
    assert user_storage.account_id("leaver") in user_storage.deleted_account_ids()
    assert user_storage.account_row_counts()["feedback"] == 0


def test_migrating_old_json_storage_is_complete_and_idempotent(tmp_path):
    legacy = tmp_path / "users"
    keep = user_storage.account_id("keeper")
    gone = user_storage.account_id("gone")
    now = datetime.now(timezone.utc)
    (legacy / keep).mkdir(parents=True)
    (legacy / gone).mkdir(parents=True)
    (legacy / keep / "history.json").write_text(json.dumps([
        {"timestamp": now.isoformat(), "assessment": "High risk", "score": 88, "category": "General message",
         "expires_at": (now + timedelta(days=7)).isoformat()},
        {"no": "assessment"}]))
    (legacy / keep / "feedback.json").write_text(json.dumps([
        {"id": "f1", "timestamp": now.isoformat(), "text": "corrected", "predicted_label": "spam", "user_label": "ham",
         "consent_given": True, "approved": True, "expires_at": (now + timedelta(days=20)).isoformat()},
        {"id": "f2", "timestamp": now.isoformat(), "text": "legacy, no consent key", "predicted_label": "spam", "user_label": "ham",
         "approved": True}]))
    (legacy / keep / "sender_rules.json").write_text(json.dumps({"whitelist": ["a@example.com"], "blacklist": ["bad.example"]}))
    (legacy / gone / "history.json").write_text(json.dumps([{"timestamp": now.isoformat(), "assessment": "High risk", "score": 1,
                                                             "category": "General message"}]))
    (legacy / ".deleted_accounts.json").write_text(json.dumps([gone]))

    migration = load_script("migrate_json_to_db")
    assert migration.migrate(legacy, dry_run=True)["feedback"] == 2
    assert user_storage.account_row_counts()["feedback"] == 0
    report = migration.migrate(legacy)
    assert report["history"] == 1 and report["feedback"] == 2 and report["sender_rules"] == 2
    assert report["skipped_deleted_accounts"] == 1 and report["unreadable_rows"] == 1
    again = migration.migrate(legacy)
    assert again["history"] == again["feedback"] == again["sender_rules"] == 0 and again["already_present"] == 5

    with user_scope("keeper"):
        rows = {r["id"]: r for r in user_storage.list_feedback()}
        assert rows["f1"]["status"] == "approved" and rows["f2"]["status"] == "pending" and not rows["f2"]["consent_given"]
        assert user_storage.get_sender_rules() == {"whitelist": ["a@example.com"], "blacklist": ["bad.example"]}
    assert [r["id"] for r in learning.get_trainable_feedback()] == ["f1"]
    with user_scope("gone"):
        assert user_storage.list_history() == []
