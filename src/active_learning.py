"""
Active Learning & Human-in-the-Loop Feedback Module for SpamGuard AI.
Captures user misclassification feedback, maintains a continuous improvement dataset,
and executes safe incremental retraining of the ML models with quality validation gates.
"""

import os
import sys
import csv
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.preprocessing import clean_text

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
FEEDBACK_CSV = os.path.join(DATA_DIR, "user_feedback.csv")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
METRICS_PATH = os.path.join(MODELS_DIR, "metrics.json")


def _ensure_feedback_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(FEEDBACK_CSV):
        with open(FEEDBACK_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "text", "predicted_label", "user_label", "user_comment"])


def record_feedback(
    text: str,
    predicted_label: str,
    user_label: str,
    user_comment: str = ""
) -> Dict[str, Any]:
    """
    Records a user correction or confirmation into the active learning dataset.
    """
    clean_msg = text.strip()
    if not clean_msg:
        raise ValueError("Cannot record feedback for empty text.")

    user_label_clean = user_label.strip().lower()
    if user_label_clean not in ["ham", "spam"]:
        raise ValueError(f"Invalid user label '{user_label}'. Must be 'ham' or 'spam'.")

    pred_label_clean = predicted_label.strip().lower()
    _ensure_feedback_file()

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "text": clean_msg,
        "predicted_label": pred_label_clean,
        "user_label": user_label_clean,
        "user_comment": user_comment.strip()
    }

    with open(FEEDBACK_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            entry["timestamp"],
            entry["text"],
            entry["predicted_label"],
            entry["user_label"],
            entry["user_comment"]
        ])

    return entry


def get_feedback_records(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all or the most recent feedback records.
    """
    _ensure_feedback_file()
    try:
        df = pd.read_csv(FEEDBACK_CSV)
        if df.empty:
            return []
        records = df.to_dict(orient="records")
        records.reverse()  # Newest first
        if limit:
            return records[:limit]
        return records
    except Exception:
        return []


def get_feedback_stats() -> Dict[str, Any]:
    """
    Returns summary metrics of logged feedback.
    """
    _ensure_feedback_file()
    try:
        df = pd.read_csv(FEEDBACK_CSV)
        if df.empty:
            return {
                "total_feedback": 0,
                "false_positives_corrected": 0,
                "false_negatives_corrected": 0,
                "confirmed_correct": 0
            }

        # Normalize labels
        df["predicted_label"] = df["predicted_label"].str.lower()
        df["user_label"] = df["user_label"].str.lower()

        fp = len(df[(df["predicted_label"] == "spam") & (df["user_label"] == "ham")])
        fn = len(df[(df["predicted_label"] == "ham") & (df["user_label"] == "spam")])
        correct = len(df[df["predicted_label"] == df["user_label"]])

        return {
            "total_feedback": len(df),
            "false_positives_corrected": fp,
            "false_negatives_corrected": fn,
            "confirmed_correct": correct
        }
    except Exception:
        return {
            "total_feedback": 0,
            "false_positives_corrected": 0,
            "false_negatives_corrected": 0,
            "confirmed_correct": 0
        }


def retrain_model_with_feedback(min_feedback_required: int = 1) -> Dict[str, Any]:
    """
    Merges user feedback into the base dataset and executes model retraining.
    Validates performance and reloads cache in predict module.
    """
    stats = get_feedback_stats()
    if stats["total_feedback"] < min_feedback_required:
        return {
            "success": False,
            "message": f"Requires at least {min_feedback_required} feedback entry to retrain (current: {stats['total_feedback']})."
        }

    # Backup previous metrics
    old_metrics = {}
    if os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                old_metrics = json.load(f)
        except Exception:
            pass

    try:
        # Load feedback data
        df_fb = pd.read_csv(FEEDBACK_CSV)
        df_fb_clean = df_fb[["text", "user_label"]].rename(columns={"user_label": "label"})

        # Load base datasets
        from src.train import load_and_preprocess_data, train_models
        df_base = load_and_preprocess_data()

        # Combine with feedback, prioritizing user feedback on duplicate texts
        df_combined = pd.concat([df_base, df_fb_clean], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=["text"], keep="last")

        print(f"[Active Learning] Retraining with {len(df_combined)} samples ({len(df_fb_clean)} from user feedback)...")

        # Execute training
        train_models()

        # Invalidate in-memory cached models in predict module
        import src.predict as predict_module
        predict_module._LOADED_MODELS.clear()

        # Load new metrics
        new_metrics = {}
        if os.path.exists(METRICS_PATH):
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                new_metrics = json.load(f)

        return {
            "success": True,
            "message": f"Model successfully retrained with {len(df_fb)} feedback entries!",
            "feedback_count": len(df_fb),
            "total_samples": len(df_combined),
            "old_metrics": old_metrics.get("models", {}),
            "new_metrics": new_metrics.get("models", {})
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Retraining failed: {str(e)}"
        }


def clear_feedback_data():
    """Clears all feedback entries (useful for unit testing and test resets)."""
    _ensure_feedback_file()
    with open(FEEDBACK_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "text", "predicted_label", "user_label", "user_comment"])
