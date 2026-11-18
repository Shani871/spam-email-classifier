"""Tests must never read or modify a person's saved account data.

Each test gets its own empty SQLite database. Set SPAMGUARD_TEST_DATABASE_URL to run the
suite against PostgreSQL instead (CI does); the tables are emptied before each test.
"""
import os

import pytest
from sqlalchemy import delete

from src import db, user_storage


@pytest.fixture(autouse=True)
def isolated_private_storage(tmp_path, monkeypatch):
    test_url = os.environ.get("SPAMGUARD_TEST_DATABASE_URL")
    monkeypatch.setenv("SPAMGUARD_DATABASE_URL", test_url or f"sqlite:///{tmp_path / 'spamguard-test.db'}")
    monkeypatch.setattr(user_storage, "LEGACY_ROOT", tmp_path / "legacy-users")
    monkeypatch.setattr(user_storage, "_last_purge", 0.0)
    db.reset_engines()
    if test_url:
        with db.get_engine().begin() as connection:
            for table in (*db.ACCOUNT_TABLES, db.deleted_accounts):
                connection.execute(delete(table))
    with user_storage.user_scope("test-account"):
        yield
    db.reset_engines()
