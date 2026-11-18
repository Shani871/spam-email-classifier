"""Account-scoped storage in the database (see src/db.py).

Every function works on the account set with `user_scope(identity)`. Accounts are stored
only as a SHA-256 hash of the sign-in identity or random guest id. Credentials and message
bodies of checks are never stored; feedback text is stored only when the person submits a
correction.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
import hashlib
from pathlib import Path
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import and_, delete, func, insert, select, update

from src.db import ACCOUNT_TABLES, as_utc, deleted_accounts, feedback, get_engine, history, sender_rules, utcnow

# Folder used by the old JSON storage; only read by scripts/migrate_json_to_db.py.
LEGACY_ROOT = Path(__file__).resolve().parents[1] / "data" / "users"

HISTORY_LIMIT_PER_ACCOUNT = 100
FEEDBACK_RETENTION_DAYS = 30
PURGE_INTERVAL_SECONDS = 3600

_scope = ContextVar("spamguard_scope", default="local")
_purge_lock = threading.Lock()
_last_purge = 0.0

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None


@contextmanager
def file_lock(lock_file_path: Path, shared: bool = False, blocking: bool = True):
    """Advisory cross-process file lock (used for model releases, which are files)."""
    lock_file_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle = open(lock_file_path, "a+", encoding="utf-8")
    mode = (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) if fcntl else 0
    if fcntl and not blocking:
        mode |= fcntl.LOCK_NB
    try:
        if fcntl:
            try:
                fcntl.flock(handle.fileno(), mode)
            except (BlockingIOError, OSError):
                raise BlockingIOError(f"Could not acquire lock on {lock_file_path}")
        yield
    finally:
        if fcntl:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


# --- Account scope -----------------------------------------------------------------------

def current_scope() -> str:
    return _scope.get()


@contextmanager
def user_scope(identity):
    token = _scope.set(str(identity))
    try:
        yield
    finally:
        _scope.reset(token)


def account_id(identity=None) -> str:
    return hashlib.sha256(str(identity or current_scope()).encode()).hexdigest()


# --- History (assessment summaries, no message content) ----------------------------------

def add_history(assessment: str, score, category: str, retention_days: int = 7) -> None:
    now = utcnow()
    owner = account_id()
    with get_engine().begin() as db:
        db.execute(insert(history).values(account_id=owner, created_at=now, expires_at=now + timedelta(days=int(retention_days)),
                                          assessment=str(assessment)[:40], score=None if score is None else int(score),
                                          category=str(category)[:40]))
        # Keep only the most recent entries per account.
        keep = select(history.c.id).where(history.c.account_id == owner).order_by(history.c.created_at.desc(), history.c.id.desc()) \
            .limit(HISTORY_LIMIT_PER_ACCOUNT).scalar_subquery()
        db.execute(delete(history).where(history.c.account_id == owner, history.c.id.not_in(keep)))


def list_history(limit: int = HISTORY_LIMIT_PER_ACCOUNT) -> List[Dict[str, Any]]:
    now = utcnow()
    with get_engine().connect() as db:
        rows = db.execute(select(history).where(history.c.account_id == account_id(), history.c.expires_at >= now)
                          .order_by(history.c.created_at.desc()).limit(limit)).mappings().all()
    return [{"timestamp": as_utc(r["created_at"]).isoformat(), "assessment": r["assessment"], "score": r["score"],
             "category": r["category"], "expires_at": as_utc(r["expires_at"]).isoformat()} for r in rows]


# --- Feedback (corrections people choose to send) ----------------------------------------

def _feedback_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "timestamp": as_utc(row["created_at"]).isoformat(),
        "text": row["text"],
        "predicted_label": row["predicted_label"],
        "user_label": row["user_label"],
        "user_comment": row["user_comment"],
        "consent_given": bool(row["consent_given"]),
        "approved": row["status"] == "approved",
        "rejected": row["status"] == "rejected",
        "status": row["status"],
        "rejection_reason": row["rejection_reason"],
        "expires_at": as_utc(row["expires_at"]).isoformat(),
    }


def add_feedback(entry_id: str, text: str, predicted_label: str, user_label: str, user_comment: str = "",
                 consent_given: bool = False, status: str = "pending", created_at=None, expires_at=None) -> Dict[str, Any]:
    created = created_at or utcnow()
    values = dict(id=entry_id, account_id=account_id(), created_at=created,
                  expires_at=expires_at or created + timedelta(days=FEEDBACK_RETENTION_DAYS), text=text,
                  predicted_label=predicted_label, user_label=user_label, user_comment=user_comment,
                  consent_given=bool(consent_given), status=status, rejection_reason="")
    with get_engine().begin() as db:
        db.execute(insert(feedback).values(**values))
    return _feedback_dict(values)


def list_feedback() -> List[Dict[str, Any]]:
    """The current account's unexpired corrections, newest first."""
    with get_engine().connect() as db:
        rows = db.execute(select(feedback).where(feedback.c.account_id == account_id(), feedback.c.expires_at >= utcnow())
                          .order_by(feedback.c.created_at.desc())).mappings().all()
    return [_feedback_dict(r) for r in rows]


def feedback_for_review() -> List[Dict[str, Any]]:
    """Unexpired corrections from all accounts whose senders gave consent. Never includes the account."""
    with get_engine().connect() as db:
        rows = db.execute(select(feedback).where(feedback.c.consent_given.is_(True), feedback.c.status != "withdrawn",
                                                 feedback.c.expires_at >= utcnow())
                          .order_by(feedback.c.created_at.desc())).mappings().all()
    return [_feedback_dict(r) for r in rows]


def trainable_feedback() -> List[Dict[str, Any]]:
    with get_engine().connect() as db:
        rows = db.execute(select(feedback).where(feedback.c.consent_given.is_(True), feedback.c.status == "approved",
                                                 feedback.c.expires_at >= utcnow())).mappings().all()
    return [_feedback_dict(r) for r in rows]


def get_feedback(entry_id: str, own_account_only: bool = True) -> Optional[Dict[str, Any]]:
    condition = feedback.c.id == entry_id
    if own_account_only:
        condition = and_(condition, feedback.c.account_id == account_id())
    with get_engine().connect() as db:
        row = db.execute(select(feedback).where(condition)).mappings().first()
    return _feedback_dict(row) if row else None


def update_feedback(entry_id: str, own_account_only: bool = True, **values) -> bool:
    """Update one correction. `own_account_only=False` is for administrators reviewing corrections."""
    allowed = {"consent_given", "status", "rejection_reason", "reviewed_at"}
    values = {k: v for k, v in values.items() if k in allowed}
    condition = feedback.c.id == entry_id
    if own_account_only:
        condition = and_(condition, feedback.c.account_id == account_id())
    with get_engine().begin() as db:
        return db.execute(update(feedback).where(condition).values(**values)).rowcount > 0


def delete_feedback(entry_id: str) -> bool:
    with get_engine().begin() as db:
        return db.execute(delete(feedback).where(feedback.c.id == entry_id, feedback.c.account_id == account_id())).rowcount > 0


def clear_feedback() -> None:
    with get_engine().begin() as db:
        db.execute(delete(feedback).where(feedback.c.account_id == account_id()))


# --- Sender rules -------------------------------------------------------------------------

def get_sender_rules() -> Dict[str, List[str]]:
    with get_engine().connect() as db:
        rows = db.execute(select(sender_rules.c.address, sender_rules.c.rule).where(sender_rules.c.account_id == account_id())
                          .order_by(sender_rules.c.created_at)).all()
    return {"whitelist": [a for a, r in rows if r == "trust"], "blacklist": [a for a, r in rows if r == "block"]}


def set_sender_rule(address: str, rule: Optional[str]) -> bool:
    """Set `rule` ("trust" or "block") for an address or domain, or remove it with None."""
    clean = (address or "").lower().strip()[:320]
    if not clean:
        return False
    owner = account_id()
    with get_engine().begin() as db:
        removed = db.execute(delete(sender_rules).where(sender_rules.c.account_id == owner, sender_rules.c.address == clean)).rowcount
        if rule is None:
            return removed > 0
        if rule not in {"trust", "block"}:
            raise ValueError("rule must be 'trust', 'block' or None")
        db.execute(insert(sender_rules).values(account_id=owner, address=clean, rule=rule, created_at=utcnow()))
    return True


# --- Deletion, retention ------------------------------------------------------------------

def delete_account_data(identity=None) -> None:
    """Delete everything stored for an account and record a deletion marker.

    The marker (a hash, no data) lets backup restores remove the account again.
    """
    owner = account_id(identity)
    with get_engine().begin() as db:
        for table in ACCOUNT_TABLES:
            db.execute(delete(table).where(table.c.account_id == owner))
        if not db.execute(select(deleted_accounts.c.account_id).where(deleted_accounts.c.account_id == owner)).first():
            db.execute(insert(deleted_accounts).values(account_id=owner, deleted_at=utcnow()))


def deleted_account_ids() -> List[str]:
    with get_engine().connect() as db:
        return [r[0] for r in db.execute(select(deleted_accounts.c.account_id)).all()]


def apply_account_deletions(account_ids: Iterable[str]) -> int:
    """Remove data for the given account hashes and record them as deleted. Returns rows removed."""
    removed = 0
    ids = sorted(set(account_ids))
    if not ids:
        return 0
    with get_engine().begin() as db:
        for table in ACCOUNT_TABLES:
            removed += db.execute(delete(table).where(table.c.account_id.in_(ids))).rowcount
        existing = {r[0] for r in db.execute(select(deleted_accounts.c.account_id).where(deleted_accounts.c.account_id.in_(ids)))}
        missing = [i for i in ids if i not in existing]
        if missing:
            db.execute(insert(deleted_accounts), [{"account_id": i, "deleted_at": utcnow()} for i in missing])
    return removed


def purge_expired_records(force: bool = False) -> int:
    """Delete expired history and feedback. Runs at most hourly per process unless forced."""
    global _last_purge
    with _purge_lock:
        if not force and time.time() - _last_purge < PURGE_INTERVAL_SECONDS:
            return 0
        _last_purge = time.time()
    now = utcnow()
    with get_engine().begin() as db:
        removed = db.execute(delete(history).where(history.c.expires_at < now)).rowcount
        removed += db.execute(delete(feedback).where(feedback.c.expires_at < now)).rowcount
    return removed


def account_row_counts() -> Dict[str, int]:
    """Row counts per table (for health checks and migration reports; no content)."""
    with get_engine().connect() as db:
        return {table.name: db.execute(select(func.count()).select_from(table)).scalar_one()
                for table in (*ACCOUNT_TABLES, deleted_accounts)}
