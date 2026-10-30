"""Tests for production deployment readiness, monitoring, scrubbing, backups, and storage isolation."""
from datetime import datetime, timedelta, timezone
import json
import pytest
from src.monitoring import scrub_sensitive_data, log_security_event, log_error, get_monitoring_metrics
from scripts.backup_and_retention import purge_expired_user_records, create_backup_archive
from src.user_storage import user_scope, write_json, read_json


def test_scrub_sensitive_data():
    raw_text = "Bearer ya29.a0AfH6SMD12345 password='SuperSecretPassword123' contact user@example.com phone +1 (555) 234-5678"
    scrubbed = scrub_sensitive_data(raw_text)
    assert "[REDACTED_TOKEN]" in scrubbed
    assert "SuperSecretPassword123" not in scrubbed
    assert "user@example.com" not in scrubbed
    assert "[EMAIL_MASKED]" in scrubbed
    assert "[PHONE_MASKED]" in scrubbed


def test_scrub_dict_keys():
    data = {
        "access_token": "secret_abc",
        "email": "victim@bank.com",
        "normal_field": "public_text"
    }
    scrubbed = scrub_sensitive_data(data)
    assert scrubbed["access_token"] == "[REDACTED]"
    assert scrubbed["email"] == "[EMAIL_MASKED]"
    assert scrubbed["normal_field"] == "public_text"


def test_monitoring_metrics_and_error_logging():
    initial = get_monitoring_metrics()["errors_recorded"]
    log_error(ValueError("Invalid token: Bearer abc123xyz"), context="test_auth")
    updated = get_monitoring_metrics()["errors_recorded"]
    assert updated == initial + 1


def test_retention_purge(tmp_path, monkeypatch):
    import scripts.backup_and_retention as br
    users_dir = tmp_path / "users"
    user_folder = users_dir / "user_abc"
    user_folder.mkdir(parents=True)
    monkeypatch.setattr(br, "USERS_DIR", users_dir)

    now = datetime.now(timezone.utc)
    expired_entry = {"id": "1", "expires_at": (now - timedelta(days=2)).isoformat(), "data": "old"}
    valid_entry = {"id": "2", "expires_at": (now + timedelta(days=5)).isoformat(), "data": "valid"}

    history_path = user_folder / "history.json"
    history_path.write_text(json.dumps([expired_entry, valid_entry]))

    purged = purge_expired_user_records()
    assert purged == 1

    remaining = json.loads(history_path.read_text())
    assert len(remaining) == 1
    assert remaining[0]["id"] == "2"


def test_backup_archive_creation(tmp_path, monkeypatch):
    import scripts.backup_and_retention as br
    data_dir = tmp_path / "data"
    backups_dir = data_dir / "backups"
    data_dir.mkdir(parents=True)
    (data_dir / "sample.txt").write_text("sample content")

    monkeypatch.setattr(br, "DATA_DIR", data_dir)
    monkeypatch.setattr(br, "BACKUPS_DIR", backups_dir)

    archive = create_backup_archive(max_backups=2)
    assert archive.exists()
    assert archive.name.endswith(".tar.gz")


def test_backup_restoration_and_deleted_account_protection(tmp_path, monkeypatch):
    import scripts.backup_and_retention as br
    import hashlib
    data_dir = tmp_path / "data"
    users_dir = data_dir / "users"
    backups_dir = data_dir / "backups"
    data_dir.mkdir(parents=True)
    users_dir.mkdir(parents=True)

    monkeypatch.setattr(br, "DATA_DIR", data_dir)
    monkeypatch.setattr(br, "USERS_DIR", users_dir)
    monkeypatch.setattr(br, "BACKUPS_DIR", backups_dir)

    digest_a = hashlib.sha256("user_alice".encode()).hexdigest()
    digest_b = hashlib.sha256("user_bob".encode()).hexdigest()

    (users_dir / digest_a).mkdir()
    (users_dir / digest_a / "history.json").write_text(json.dumps([{"query": "alice message"}]))

    (users_dir / digest_b).mkdir()
    (users_dir / digest_b / "history.json").write_text(json.dumps([{"query": "bob message"}]))

    # Create backup archive containing both accounts
    archive = br.create_backup_archive(max_backups=5)
    assert archive.exists()

    # Alice deletes her account
    br.record_account_deletion_tombstone(digest_a, users_dir=users_dir)
    import shutil
    shutil.rmtree(users_dir / digest_a)

    # Bob's account is also wiped to simulate disaster recovery restore
    shutil.rmtree(users_dir / digest_b)

    # Restore the backup archive
    assert br.restore_backup_archive(archive, target_data_dir=data_dir)

    # Bob's account must be restored
    assert (users_dir / digest_b / "history.json").exists()

    # Alice's account was deleted and MUST NOT be resurrected!
    assert not (users_dir / digest_a).exists()


def test_app_pages_importable():
    """Every app_pages module must be importable without a running Streamlit server."""
    import importlib
    import sys
    import types

    # Stub streamlit so page modules can be imported without a live server
    class MockContext:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    class MockSessionState(dict):
        def setdefault(self, k, default=None):
            if k not in self:
                self[k] = default
            return self[k]
        def __getattr__(self, name):
            return self.get(name)
        def __setattr__(self, name, value):
            self[name] = value

    class StreamlitStop(BaseException):
        pass

    st_stub = types.ModuleType("streamlit")
    st_stub.session_state = MockSessionState({
        "result": {"assessment": "High risk", "summary": "Test summary", "score": 85, "category": "General message", "evidence": [], "limitations": []},
        "language": "English",
        "checked_text": "sample text",
        "save_history": False,
        "retention_days": 7,
        "messages": [],
        "selected_message": None,
        "actions": [],
        "worker": None,
        "gmail_disconnected": False,
    })
    st_stub.user = {"is_logged_in": False, "get": lambda k, d=None: False if k == "is_logged_in" else d}
    st_stub.secrets = {}
    st_stub.stop = lambda: (_ for _ in ()).throw(StreamlitStop())
    st_stub.segmented_control = lambda *a, **kw: "Paste text"
    st_stub.badge = lambda *a, **kw: None
    st_stub.toggle = lambda *a, **kw: False
    st_stub.container = lambda *a, **kw: MockContext()
    st_stub.form = lambda *a, **kw: MockContext()
    st_stub.expander = lambda *a, **kw: MockContext()
    st_stub.spinner = lambda *a, **kw: MockContext()
    st_stub.tabs = lambda t, *a, **kw: [MockContext() for _ in range(len(t) if hasattr(t, '__len__') else 3)]
    st_stub.columns = lambda n, *a, **kw: [MockContext() for _ in range(n if isinstance(n, int) else len(n))]
    for attr in ("caption", "title", "subheader", "selectbox", "markdown",
                 "link_button", "button", "checkbox", "text_area",
                 "text_input", "form_submit_button", "radio",
                 "page_link", "success", "error", "info", "dataframe",
                 "slider", "text", "switch_page", "warning", "rerun", "code", "image", "json", "download_button", "number_input", "progress", "logo"):
        setattr(st_stub, attr, lambda *a, **kw: None)

    import pathlib
    pages_dir = pathlib.Path(__file__).parent.parent / "app_pages"
    failures = []
    for path in sorted(pages_dir.glob("*.py")):
        module_name = f"app_pages.{path.stem}"
        sys.modules.pop(module_name, None)
        sys.modules["streamlit"] = st_stub
        try:
            importlib.import_module(module_name)
        except (StreamlitStop, SystemExit):
            pass
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
        finally:
            sys.modules.pop(module_name, None)

    assert not failures, "app_pages modules failed to import:\n" + "\n".join(failures)


def test_log_rotation_and_retention(tmp_path, monkeypatch):
    import src.monitoring as mon
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    monkeypatch.setattr(mon, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(mon, "MAX_LOG_SIZE_BYTES", 200)
    monkeypatch.setattr(mon, "MAX_LOG_BACKUPS", 3)

    for i in range(25):
        mon.log_security_event("TEST_EVENT", {"index": i, "padding": "x" * 20})

    log_files = list(logs_dir.glob("security_audit.log*"))
    assert len(log_files) > 1
    assert any(".1" in f.name for f in log_files)
