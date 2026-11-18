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
from src.user_storage import file_lock
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

    if os.environ.get("SPAMGUARD_LOCAL_ADMIN") == "1" and os.environ.get("SPAMGUARD_ENV") != "production":
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
    """Records a correction for the current account.

    consent_given defaults to False: without consent a correction stays private to its
    author and never reaches the review queue or training.
    """
    if not text.strip():
        raise ValueError("Cannot record feedback for empty text.")
    label = user_label.lower().strip()
    if label not in {"spam", "ham"}:
        raise ValueError("User label must be ham or spam.")
    return user_storage.add_feedback(
        entry_id=uuid.uuid4().hex,
        text=redact_personal_data(text.strip()),
        predicted_label=predicted_label.lower(),
        user_label=label,
        user_comment=redact_personal_data(user_comment.strip()),
        consent_given=bool(consent_given),
        status="approved" if approved and consent_given else "pending",
    )


def get_feedback_records(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Corrections from the CURRENT account only, newest first."""
    rows = user_storage.list_feedback()
    return rows[:limit] if limit else rows


def get_admin_feedback_queue(admin_user: Any = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Corrections from all accounts, for administrators.

    Only corrections with explicit consent are returned, and only their own fields:
    no account identifier, history or rules.
    """
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to view the feedback review queue.")
    records = user_storage.feedback_for_review()
    return records[:limit] if limit else records


def approve_feedback(entry_id: str, admin_user: Any = None) -> None:
    """Approves a correction for training. Requires an administrator and the author's consent."""
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to approve feedback.")
    row = user_storage.get_feedback(entry_id, own_account_only=False)
    if row is None:
        raise ValueError(f"Feedback entry '{entry_id}' not found.")
    if not row["consent_given"]:
        raise ValueError("Cannot approve feedback without user consent.")
    user_storage.update_feedback(entry_id, own_account_only=False, status="approved", rejection_reason="",
                                 reviewed_at=datetime.now(timezone.utc))


def reject_feedback(entry_id: str, admin_user: Any = None, reason: str = "") -> None:
    """Rejects a correction. Requires an administrator."""
    if not is_authorized_admin(admin_user):
        raise PermissionError("Administrator authorization required to reject feedback.")
    if not user_storage.update_feedback(entry_id, own_account_only=False, status="rejected", rejection_reason=reason or "",
                                        reviewed_at=datetime.now(timezone.utc)):
        raise ValueError(f"Feedback entry '{entry_id}' not found.")


def withdraw_feedback_consent(entry_id: str) -> None:
    """The author withdraws consent; the correction leaves the review queue and training."""
    if not user_storage.update_feedback(entry_id, own_account_only=True, consent_given=False, status="withdrawn"):
        raise ValueError(f"Feedback entry '{entry_id}' not found.")


def delete_feedback_record(entry_id: str) -> None:
    """The author deletes a correction.

    This removes it from review and future training. It does not remove its influence
    from a model that was already trained and released.
    """
    if not user_storage.delete_feedback(entry_id):
        raise ValueError(f"Feedback entry '{entry_id}' not found.")


def get_feedback_stats() -> Dict[str, Any]:
    """Returns feedback statistics for the current account."""
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
    """Deletes all corrections of the current account."""
    user_storage.clear_feedback()


def get_trainable_feedback() -> List[Dict[str, Any]]:
    """Corrections eligible for training: consent given, approved, not expired, from any account."""
    return user_storage.trainable_feedback()


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


def missing_training_corpora() -> List[str]:
    """Public corpora the active model was trained on that are not available locally."""
    import os
    from src.train import EXTERNAL_CORPORA, EXTERNAL_DIR
    active = MODELS_DIR / "active.json"
    folder = MODELS_DIR
    try:
        if active.exists():
            version = json.loads(active.read_text(encoding="utf-8"))["version"]
            folder = MODELS_DIR if version == "baseline" else MODELS_DIR / "versions" / version
        used = set(json.loads((folder / "metrics.json").read_text(encoding="utf-8")).get("source_counts", {}))
    except (OSError, ValueError, KeyError):
        return []
    return [name for name in EXTERNAL_CORPORA
            if name.lower() in used and not os.path.exists(os.path.join(EXTERNAL_DIR, f"{name}.csv"))]


def _retrain(minimum: int) -> Dict[str, Any]:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import precision_score, recall_score
    from src.train import load_and_preprocess_data, train_models
    from src.predict import load_model, decision_threshold, _LOADED_MODELS

    rows = get_trainable_feedback()
    if len(rows) < minimum:
        return {"success": False, "message": f"Review and approve at least {minimum} corrections before training."}
    missing = missing_training_corpora()
    if missing:
        return {"success": False, "message": "The active model was trained with public corpora that are not on this server ("
                + ", ".join(missing) + "). Run scripts/fetch_public_corpora.sh first, or the candidate would be trained on far less data."}
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
            # Compare like for like: the active model at its own recorded threshold.
            prediction = (load_model(name).predict_proba(holdout.cleaned_text)[:, 1] >= decision_threshold(name)).astype(int)
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
