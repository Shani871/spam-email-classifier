"""Private feedback, explicit review, and gated model releases.

Guarantees:
- Submissions require explicit user consent (default is False, including legacy records).
- Only authorized administrators can review and approve feedback across accounts.
- Unrelated private account data is never exposed.
- Retraining only uses eligible, consented, approved corrections.
- Cross-process locking coordinates concurrent training and rollbacks.
- Note: Deleting feedback removes it from future training and the admin queue,
  but does not retroactively remove its influence from an already trained and
  deployed model release (an explicit rollback is required to revert a release).
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
from src import user_storage
from src.user_storage import read_json, write_json, update_json, file_lock
from src.preprocessing import clean_text

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


def is_authorized_admin(admin_user: Any = None) -> bool:
    """Enforces administrator authorization in backend operations."""
    if admin_user is not None:
        if admin_user is True:
            return True
        if isinstance(admin_user, dict):
            if admin_user.get("is_admin") is True or admin_user.get("role") == "admin":
                return True
            email = admin_user.get("email", "")
            admin_emails = [e.strip() for e in os.environ.get("SPAMGUARD_ADMIN_EMAILS", "").split(",") if e.strip()]
            return bool(email and email in admin_emails)
        if isinstance(admin_user, str):
            if admin_user in {"admin", "administrator"}:
                return True
            admin_emails = [e.strip() for e in os.environ.get("SPAMGUARD_ADMIN_EMAILS", "").split(",") if e.strip()]
            return bool(admin_user and admin_user in admin_emails)
        return False

    if os.environ.get("SPAMGUARD_LOCAL_ADMIN") == "1":
        return True
    try:
        from src.ui_shared import is_admin
        if is_admin():
            return True
    except Exception:
        pass
    return False


def redact_personal_data(text: str) -> str:
    """Redacts email addresses and telephone numbers from text."""
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)", "[NUMBER]", text)
    return text


def record_feedback(
    text: str,
    predicted_label: str,
    user_label: str,
    user_comment: str = "",
    approved: bool = False,
    consent_given: bool = False
) -> Dict[str, Any]:
    """Records user feedback.
    
    CRITICAL: consent_given defaults to False to ensure strict user consent.
    """
    if not text.strip():
        raise ValueError("Cannot record feedback for empty text.")
    label = user_label.lower().strip()
    if label not in {"spam", "ham"}:
        raise ValueError("User label must be ham or spam.")
    
    entry = {
        "id": uuid.uuid4().hex,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": redact_personal_data(text.strip()),
        "predicted_label": predicted_label.lower(),
        "user_label": label,
        "user_comment": redact_personal_data(user_comment.strip()),
        "consent_given": bool(consent_given),
        "approved": bool(approved),
        "rejected": False,
        "status": "approved" if approved else "pending",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    }
    update_json("feedback.json", [], lambda rows: rows + [entry])
    return entry


def get_feedback_records(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Gets feedback records for the CURRENT account scope only."""
    rows = list(reversed(read_json("feedback.json", [])))
    return rows[:limit] if limit else rows


def get_admin_feedback_queue(admin_user: Any = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Allows authorized administrators to review submissions from other users.
    
    CRITICAL PRIVACY GUARANTEES:
    - Only submissions where the user explicitly gave consent are returned.
    - Missing consent defaults to False (legacy records without consent are excluded).
    - Unrelated private account data (history, rules, credentials) is NEVER exposed.
    """
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to view the feedback review queue.")

    records = []
    seen_ids = set()
    now = datetime.now(timezone.utc).isoformat()

    # Search all account directories
    if user_storage.ROOT.exists():
        for fb_path in user_storage.ROOT.glob("*/feedback.json"):
            try:
                data = json.loads(fb_path.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    continue
                for row in data:
                    if not isinstance(row, dict):
                        continue
                    # Missing consent strictly defaults to False
                    if not row.get("consent_given", False):
                        continue
                    if row.get("expires_at", now) < now:
                        continue
                    if row.get("id") in seen_ids:
                        continue
                    seen_ids.add(row["id"])

                    # Expose ONLY feedback fields; never expose user account identifiers or paths
                    records.append({
                        "id": row["id"],
                        "timestamp": row.get("timestamp"),
                        "text": row.get("text", ""),
                        "predicted_label": row.get("predicted_label", ""),
                        "user_label": row.get("user_label", ""),
                        "user_comment": row.get("user_comment", ""),
                        "consent_given": True,
                        "approved": bool(row.get("approved", False)),
                        "rejected": bool(row.get("rejected", False)),
                        "status": "approved" if row.get("approved") else ("rejected" if row.get("rejected") else "pending"),
                        "rejection_reason": row.get("rejection_reason", ""),
                        "expires_at": row.get("expires_at")
                    })
            except Exception:
                continue

    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records[:limit] if limit else records


def _find_and_update_feedback(entry_id: str, updater_fn) -> bool:
    """Helper to update a feedback entry across current scope or all accounts."""
    updated = False
    def update_in_list(rows):
        nonlocal updated
        for row in rows:
            if isinstance(row, dict) and row.get("id") == entry_id:
                updater_fn(row)
                updated = True
        return rows

    # Try current scope first
    update_json("feedback.json", [], update_in_list)
    if updated:
        return True

    # Otherwise scan accounts
    if user_storage.ROOT.exists():
        for fb_path in user_storage.ROOT.glob("*/feedback.json"):
            try:
                data = json.loads(fb_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    matched = False
                    for row in data:
                        if isinstance(row, dict) and row.get("id") == entry_id:
                            updater_fn(row)
                            matched = True
                            updated = True
                    if matched:
                        fb_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                        return True
            except Exception:
                continue
    return updated


def approve_feedback(entry_id: str, admin_user: Any = None) -> None:
    """Approves a feedback entry. Requires administrator authorization and explicit consent."""
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to approve feedback.")

    def do_approve(row):
        # Default missing consent to False (including legacy records)
        if not row.get("consent_given", False):
            raise ValueError("Cannot approve feedback without user consent.")
        row["approved"] = True
        row["rejected"] = False
        row["status"] = "approved"

    found = _find_and_update_feedback(entry_id, do_approve)
    if not found:
        raise ValueError(f"Feedback entry '{entry_id}' not found.")


def reject_feedback(entry_id: str, admin_user: Any = None, reason: str = "") -> None:
    """Rejects a feedback entry. Requires administrator authorization."""
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to reject feedback.")

    def do_reject(row):
        row["approved"] = False
        row["rejected"] = True
        row["status"] = "rejected"
        row["rejection_reason"] = reason

    found = _find_and_update_feedback(entry_id, do_reject)
    if not found:
        raise ValueError(f"Feedback entry '{entry_id}' not found.")


def withdraw_feedback_consent(entry_id: str) -> None:
    """Allows a user to withdraw consent from previously submitted feedback."""
    def do_withdraw(row):
        row["consent_given"] = False
        row["approved"] = False
        row["status"] = "withdrawn"

    found = _find_and_update_feedback(entry_id, do_withdraw)
    if not found:
        raise ValueError(f"Feedback entry '{entry_id}' not found.")


def delete_feedback_record(entry_id: str) -> None:
    """Deletes feedback from stored records.
    
    IMPORTANT NOTICE:
    Deleting stored feedback removes it from the review queue and future model training,
    but does NOT retroactively remove its influence from an already trained and released model.
    """
    def do_delete(rows):
        return [r for r in rows if not isinstance(r, dict) or r.get("id") != entry_id]

    update_json("feedback.json", [], do_delete)
    if user_storage.ROOT.exists():
        for fb_path in user_storage.ROOT.glob("*/feedback.json"):
            try:
                data = json.loads(fb_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    filtered = [r for r in data if not isinstance(r, dict) or r.get("id") != entry_id]
                    if len(filtered) != len(data):
                        fb_path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                continue


def get_feedback_stats() -> Dict[str, Any]:
    """Returns feedback statistics for the current user scope."""
    rows = get_feedback_records()
    return {
        "total_feedback": len(rows),
        "false_positives_corrected": sum(r["predicted_label"] == "spam" and r["user_label"] == "ham" for r in rows),
        "false_negatives_corrected": sum(r["predicted_label"] == "ham" and r["user_label"] == "spam" for r in rows),
        "confirmed_correct": sum(r["predicted_label"] == r["user_label"] for r in rows),
        "approved": sum(r.get("approved", False) for r in rows),
        "consented": sum(r.get("consent_given", False) for r in rows)
    }


def clear_feedback_data() -> None:
    """Clears feedback data for the current account scope."""
    write_json("feedback.json", [])


def get_trainable_feedback() -> List[Dict[str, Any]]:
    """Returns eligible, consented, and approved corrections for training.
    
    CRITICAL:
    - consent_given must be explicitly True (missing consent defaults to False).
    - approved must be True.
    - rejected must NOT be True.
    - expired records are excluded.
    """
    eligible = []
    seen_ids = set()
    now = datetime.now(timezone.utc).isoformat()

    def check_rows(rows):
        for r in rows:
            if not isinstance(r, dict):
                continue
            if r.get("id") in seen_ids:
                continue
            if (
                r.get("consent_given", False) is True
                and r.get("approved", False) is True
                and not r.get("rejected", False)
                and r.get("expires_at", now) >= now
            ):
                seen_ids.add(r["id"])
                eligible.append(r)

    # Current scope
    check_rows(read_json("feedback.json", []))

    # All accounts in ROOT
    if user_storage.ROOT.exists():
        for fb_path in user_storage.ROOT.glob("*/feedback.json"):
            try:
                data = json.loads(fb_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    check_rows(data)
            except Exception:
                continue

    return eligible


def _get_release_lock_path() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    return MODELS_DIR / ".release.lock"


def retrain_model_with_feedback(min_feedback_required: int = 5, admin_user: Any = None) -> Dict[str, Any]:
    """Retrains the model with eligible consented & approved feedback using cross-process locking."""
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to retrain and release models.")

    lock_file = _get_release_lock_path()
    try:
        with file_lock(lock_file, shared=False, blocking=False):
            return _retrain(min_feedback_required)
    except BlockingIOError:
        return {"success": False, "message": "Another model release is in progress."}


def _retrain(minimum: int) -> Dict[str, Any]:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import precision_score, recall_score
    from src.train import load_and_preprocess_data, train_models
    from src.predict import load_model, _LOADED_MODELS

    rows = get_trainable_feedback()
    if len(rows) < minimum:
        return {"success": False, "message": f"Review and approve at least {minimum} corrections before training."}
    try:
        # Fixed holdout of baseline examples; feedback never enters evaluation.
        baseline = load_and_preprocess_data().drop_duplicates("cleaned_text")
        training, holdout = train_test_split(baseline, test_size=.2, random_state=42, stratify=baseline.label_binary)
        additions = pd.DataFrame(rows)[["text", "user_label"]].rename(columns={"user_label": "label"})
        additions["cleaned_text"] = additions.text.apply(clean_text)
        additions["label_binary"] = additions.label.map({"ham": 0, "spam": 1})
        additions = additions[~additions.cleaned_text.isin(holdout.cleaned_text) & additions.cleaned_text.ne("")].drop_duplicates("cleaned_text", keep="last")
        if len(additions) < minimum:
            return {"success": False, "message": f"At least {minimum} distinct usable corrections are required outside the protected evaluation set."}
        combined = pd.concat([training, additions]).drop_duplicates("cleaned_text", keep="last")
        version = uuid.uuid4().hex
        folder = MODELS_DIR / "versions" / version
        old = {}
        for name in ("nb", "svm"):
            prediction = load_model(name).predict(holdout.cleaned_text)
            old[name] = {"precision_spam": precision_score(holdout.label_binary, prediction, zero_division=0),
                         "recall_spam": recall_score(holdout.label_binary, prediction, zero_division=0)}
        metrics = train_models(combined, output_dir=str(folder), test_data=holdout)
        regressions = []
        for name, metric_name in (("nb", "naive_bayes"), ("svm", "svm")):
            for metric in ("precision_spam", "recall_spam"):
                if metrics["models"][metric_name][metric] + .005 < old[name][metric]:
                    regressions.append(f"{name}: {metric}")
        manifest = {"version": version, "feedback_count": len(additions), "evaluation": "fixed baseline holdout", "approved": not regressions}
        (folder / "release.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if regressions:
            return {"success": False, "message": "Candidate retained for review; current model kept because evaluation regressed: " + ", ".join(regressions)}
        active = MODELS_DIR / "active.json"
        if active.exists():
            (MODELS_DIR / "previous.json").write_text(active.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            (MODELS_DIR / "previous.json").write_text(json.dumps({"version": "baseline"}), encoding="utf-8")
        temp = MODELS_DIR / ".active.tmp"
        temp.write_text(json.dumps(manifest), encoding="utf-8")
        temp.replace(active)
        _LOADED_MODELS.clear()
        return {"success": True, "message": f"Released a validated model using {len(additions)} reviewed corrections.", "new_metrics": metrics["models"]}
    except Exception:
        return {"success": False, "message": "Candidate training failed. The current model remains active."}


def rollback_model(admin_user: Any = None) -> bool:
    """Restores the previous model release safely across processes."""
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to roll back model releases.")

    from src.predict import _LOADED_MODELS
    lock_file = _get_release_lock_path()
    try:
        with file_lock(lock_file, shared=False, blocking=False):
            previous = MODELS_DIR / "previous.json"
            if not previous.exists():
                return False
            manifest = json.loads(previous.read_text(encoding="utf-8"))
            active = MODELS_DIR / "active.json"
            if manifest["version"] == "baseline":
                active.unlink(missing_ok=True)
            else:
                temporary = MODELS_DIR / ".rollback.tmp"
                temporary.write_text(json.dumps(manifest), encoding="utf-8")
                temporary.replace(active)
            previous.unlink(missing_ok=True)
            _LOADED_MODELS.clear()
            return True
    except BlockingIOError:
        return False
