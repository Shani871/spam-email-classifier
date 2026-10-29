"""Account-scoped storage. Credentials never enter persistent storage."""
from contextvars import ContextVar
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
import time

ROOT = Path(__file__).resolve().parents[1] / "data" / "users"
_scope = ContextVar("spamguard_scope", default="local")
_storage_lock = threading.RLock()


try:
    import fcntl
except ImportError:
    fcntl = None


@contextmanager
def file_lock(lock_file_path: Path, shared: bool = False, blocking: bool = True):
    """Advisory cross-process file lock using fcntl.flock."""
    lock_file_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        f = open(lock_file_path, "a+", encoding="utf-8")
    except OSError:
        # Fallback if opening fails
        yield
        return

    mode = (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) if fcntl else 0
    if not blocking and fcntl:
        mode |= fcntl.LOCK_NB

    locked = False
    if fcntl:
        try:
            fcntl.flock(f.fileno(), mode)
            locked = True
        except (BlockingIOError, OSError):
            f.close()
            raise BlockingIOError(f"Could not acquire lock on {lock_file_path}")

    try:
        yield
    finally:
        if locked and fcntl:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            f.close()
        except OSError:
            pass


def current_scope():
    return _scope.get()


@contextmanager
def user_scope(identity):
    token = _scope.set(str(identity))
    try:
        yield
    finally:
        _scope.reset(token)


def account_dir(identity=None):
    digest = hashlib.sha256(str(identity or current_scope()).encode()).hexdigest()
    return ROOT / digest


def _account_lock(identity=None):
    folder = account_dir(identity)
    return folder / ".account.lock"


def read_json(name, default, identity=None):
    with _storage_lock:
        folder = account_dir(identity)
        lock_path = folder / ".account.lock"
        needs_rewrite = False
        retained = None
        with file_lock(lock_path, shared=True):
            path = folder / name
            if not path.exists():
                return default
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return default
            if isinstance(value, list):
                now = datetime.now(timezone.utc).isoformat()
                retained = [row for row in value if not isinstance(row, dict) or row.get("expires_at", now) >= now]
                if retained != value:
                    needs_rewrite = True
                    value = retained
        if needs_rewrite and retained is not None:
            write_json(name, retained, identity)
        return value


def write_json(name, value, identity=None):
    with _storage_lock:
        folder = account_dir(identity)
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = folder / ".account.lock"
        with file_lock(lock_path, shared=False):
            fd, temporary = tempfile.mkstemp(dir=folder)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(value, handle, ensure_ascii=False, indent=2)
                os.replace(temporary, folder / name)
            finally:
                if os.path.exists(temporary):
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass


def update_json(name, default, update, identity=None):
    with _storage_lock:
        folder = account_dir(identity)
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = folder / ".account.lock"
        with file_lock(lock_path, shared=False):
            path = folder / name
            if path.exists():
                try:
                    current_val = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    current_val = default
            else:
                current_val = default
            value = update(current_val)
            fd, temporary = tempfile.mkstemp(dir=folder)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(value, handle, ensure_ascii=False, indent=2)
                os.replace(temporary, folder / name)
            finally:
                if os.path.exists(temporary):
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
            return value


def delete_account_data(identity=None):
    import shutil
    with _storage_lock:
        target_identity = str(identity or current_scope())
        digest = hashlib.sha256(target_identity.encode()).hexdigest()
        folder = ROOT / digest
        lock_path = folder / ".account.lock"
        with file_lock(lock_path, shared=False):
            if folder.exists():
                shutil.rmtree(folder)
        # Record tombstone so restores never resurrect deleted accounts
        try:
            from scripts.backup_and_retention import record_account_deletion_tombstone
            record_account_deletion_tombstone(digest, users_dir=ROOT)
        except Exception:
            pass


_last_cleanup = 0


def purge_expired_records():
    """Prune inactive accounts too; called at most hourly while the app runs."""
    global _last_cleanup
    with _storage_lock:
        if time.time() - _last_cleanup < 3600:
            return
        _last_cleanup = time.time()
        if not ROOT.exists():
            return
        now = datetime.now(timezone.utc).isoformat()
        for path in ROOT.glob("*/*.json"):
            if path.name not in {"history.json", "feedback.json"}:
                continue
            rows = json.loads(path.read_text(encoding="utf-8"))
            kept = [row for row in rows if row.get("expires_at", now) >= now]
            if kept != rows:
                fd, temporary = tempfile.mkstemp(dir=path.parent)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(kept, handle)
                os.replace(temporary, path)
