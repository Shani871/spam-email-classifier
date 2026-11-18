"""Tests for production deployment readiness, monitoring, scrubbing, backups, and storage isolation."""
from datetime import datetime, timedelta, timezone
import json
import pytest
from src.monitoring import scrub_sensitive_data, log_security_event, log_error, get_monitoring_metrics
from scripts.backup_and_retention import purge_expired_user_records, create_backup_archive
from src.user_storage import user_scope
from src import user_storage


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


def test_retention_purge():
    from datetime import datetime, timedelta, timezone
    user_storage.add_history("High risk", 90, "General message", retention_days=7)
    user_storage.add_feedback("old", "old text", "spam", "ham", created_at=datetime.now(timezone.utc) - timedelta(days=40),
                              expires_at=datetime.now(timezone.utc) - timedelta(days=10))
    user_storage.add_feedback("new", "new text", "spam", "ham")
    assert purge_expired_user_records() == 1
    assert [r["id"] for r in user_storage.list_feedback()] == ["new"]
    assert len(user_storage.list_history()) == 1


def test_backup_archive_creation(tmp_path):
    user_storage.add_history("High risk", 90, "General message")
    for _ in range(3):
        archive = create_backup_archive(max_backups=2, backups_dir=tmp_path / "backups")
    assert archive.exists() and archive.suffix in {".sqlite3", ".dump"}
    assert len(list((tmp_path / "backups").iterdir())) == 2
    assert oct(archive.stat().st_mode & 0o777) == "0o600"


def test_backup_restoration_and_deleted_account_protection(tmp_path):
    import scripts.backup_and_retention as br
    with user_scope("user_alice"):
        user_storage.add_history("High risk", 80, "General message")
        user_storage.set_sender_rule("alice@example.com", "trust")
    with user_scope("user_bob"):
        user_storage.add_history("Needs verification", 50, "General message")
    archive = br.create_backup_archive(max_backups=5, backups_dir=tmp_path / "backups")

    # Alice deletes her account after the backup was taken; Bob's data is then lost.
    with user_scope("user_alice"):
        user_storage.delete_account_data()
    with user_scope("user_bob"):
        user_storage.delete_account_data()
    from src import db
    from sqlalchemy import delete
    with db.get_engine().begin() as connection:  # simulate losing Bob's deletion marker: this was a disaster, not his choice
        connection.execute(delete(db.deleted_accounts).where(db.deleted_accounts.c.account_id == user_storage.account_id("user_bob")))

    assert br.restore_backup_archive(archive)

    with user_scope("user_bob"):
        assert len(user_storage.list_history()) == 1
    with user_scope("user_alice"):
        assert user_storage.list_history() == []
        assert user_storage.get_sender_rules() == {"whitelist": [], "blacklist": []}
    assert user_storage.account_id("user_alice") in user_storage.deleted_account_ids()


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
        def container(self, *args, **kwargs):
            return MockContext()

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
                 "slider", "text", "switch_page", "warning", "rerun", "code", "image", "json", "download_button", "number_input", "progress", "logo",
                 "pills", "select_slider", "space", "toast", "feedback"):
        setattr(st_stub, attr, lambda *a, **kw: None)

    import pathlib
    pages_dir = pathlib.Path(__file__).parent.parent / "app_pages"
    failures = []
    real_streamlit = sys.modules.get("streamlit")
    stubbed_src = [name for name in ("src.ui_shared", "src.i18n") if name in sys.modules]
    saved_src = {name: sys.modules[name] for name in stubbed_src}
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

    # Put the real Streamlit back so later tests (AppTest) are not run against the stub.
    if real_streamlit is not None:
        sys.modules["streamlit"] = real_streamlit
    else:
        sys.modules.pop("streamlit", None)
    for name in ("src.ui_shared", "src.i18n"):
        sys.modules.pop(name, None)
    sys.modules.update(saved_src)

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
