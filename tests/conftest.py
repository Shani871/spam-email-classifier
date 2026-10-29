"""Tests must never read or modify a person's saved account data."""
import pytest
from src import user_storage


@pytest.fixture(autouse=True)
def isolated_private_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(user_storage, "ROOT", tmp_path / "accounts")
    with user_storage.user_scope("test-account"):
        yield
