"""Production error monitoring, metrics, and security audit logging for SpamGuard AI.

Ensures credentials, bearer tokens, passwords, and message contents are scrubbed
before entering logs or diagnostics. Features automated log rotation and retention.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import threading
from typing import Any, Dict, Optional

LOGS_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_LOG_BACKUPS = 5
RETENTION_DAYS = 14

_METRICS_LOCK = threading.Lock()
_METRICS = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "checks_performed": 0,
    "threats_detected": 0,
    "inbox_scans": 0,
    "provider_actions": 0,
    "errors_recorded": 0,
}


def scrub_sensitive_data(val: Any) -> Any:
    """Recursively scrubs emails, phone numbers, tokens, and passwords."""
    if isinstance(val, str):
        # Mask bearer tokens / api keys
        val = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+", r"\1[REDACTED_TOKEN]", val)
        val = re.sub(r"(?i)(password|secret|token|api_key)=['\"]?[^'\";\s]+", r"\1=[REDACTED]", val)
        # Mask email addresses
        val = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL_MASKED]", val)
        # Mask telephone numbers
        val = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)", "[PHONE_MASKED]", val)
        return val
    elif isinstance(val, dict):
        return {
            k: ("[REDACTED]" if any(s in k.lower() for s in ["password", "secret", "token", "auth", "credential"]) else scrub_sensitive_data(v))
            for k, v in val.items()
        }
    elif isinstance(val, list):
        return [scrub_sensitive_data(v) for v in val]
    return val


def _rotate_and_prune_logs(log_file: Path) -> None:
    """Rotates logs when exceeding max size and prunes backups exceeding retention."""
    try:
        if log_file.exists() and log_file.stat().st_size >= MAX_LOG_SIZE_BYTES:
            for i in range(MAX_LOG_BACKUPS - 1, 0, -1):
                s = log_file.with_name(f"{log_file.name}.{i}")
                d = log_file.with_name(f"{log_file.name}.{i + 1}")
                if s.exists():
                    s.replace(d)
            log_file.replace(log_file.with_name(f"{log_file.name}.1"))

        # Prune log files older than RETENTION_DAYS
        cutoff = datetime.now(timezone.utc).timestamp() - (RETENTION_DAYS * 86400)
        for old_log in LOGS_DIR.glob("*.log*"):
            if old_log.stat().st_mtime < cutoff:
                try:
                    old_log.unlink()
                except OSError:
                    pass
    except OSError:
        pass


def log_security_event(event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Logs a sanitized security/audit event to persistent JSON Lines log without private payloads."""
    details = scrub_sensitive_data(details or {})
    # Strict privacy safeguard: ensure no 'body', 'message_text', or 'content' is logged
    sanitized_details = {
        k: v for k, v in details.items()
        if k.lower() not in {"body", "message_text", "full_text", "content", "raw_email"}
    }
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": sanitized_details,
    }
    log_file = LOGS_DIR / "security_audit.log"
    _rotate_and_prune_logs(log_file)
    try:
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def record_metric(name: str, count: int = 1) -> None:
    """Increments an in-memory health and activity counter."""
    with _METRICS_LOCK:
        if name in _METRICS:
            _METRICS[name] += count


def get_monitoring_metrics() -> Dict[str, Any]:
    """Returns current runtime health metrics."""
    with _METRICS_LOCK:
        return dict(_METRICS)


def log_error(error: Exception, context: Optional[str] = None) -> None:
    """Records an error event without logging private payloads."""
    record_metric("errors_recorded")
    error_entry = {
        "error_type": error.__class__.__name__,
        "error_message": scrub_sensitive_data(str(error)),
        "context": context or "unspecified",
    }
    log_security_event("INTERNAL_ERROR", error_entry)
