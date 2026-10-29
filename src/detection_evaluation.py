"""Detection evaluation benchmark for SpamGuard AI.

Evaluates realistic scam and legitimate messages (including urgent genuine emails,
Hindi, and Hinglish examples) separately from historical spam-classifier accuracy.
Clearly labels synthetic examples and avoids unsupported accuracy claims.
"""

from pathlib import Path
import json
from typing import Any, Dict, List, Optional
from src.scam_assistant import check_message

EVAL_PATH = Path(__file__).resolve().parents[1] / "data" / "detection_evaluation_set.json"


def load_evaluation_set(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Loads the curated detection evaluation benchmark."""
    target = path or EVAL_PATH
    if not target.exists():
        return []
    return json.loads(target.read_text(encoding="utf-8"))


def evaluate_detection(
    samples: Optional[List[Dict[str, Any]]] = None,
    model_type: str = "svm"
) -> Dict[str, Any]:
    """
    Evaluates detection accuracy, false warnings, and missed scams on realistic messages.
    Compares ScamGuard hybrid risk assessment vs historical ML classifier output.
    """
    data = samples if samples is not None else load_evaluation_set()
    if not data:
        return {"error": "Evaluation dataset is empty or not found."}

    results = []
    by_language: Dict[str, Dict[str, Any]] = {
        "English": {"total": 0, "scams": 0, "scams_detected": 0, "missed_scams": 0, "legit": 0, "false_warnings": 0, "high_risk_false_alarms": 0, "unable_to_assess": 0},
        "Hindi": {"total": 0, "scams": 0, "scams_detected": 0, "missed_scams": 0, "legit": 0, "false_warnings": 0, "high_risk_false_alarms": 0, "unable_to_assess": 0},
        "Hinglish": {"total": 0, "scams": 0, "scams_detected": 0, "missed_scams": 0, "legit": 0, "false_warnings": 0, "high_risk_false_alarms": 0, "unable_to_assess": 0},
    }

    false_warnings_list = []
    missed_scams_list = []

    historical_ml_stats = {
        "scams_detected": 0,
        "missed_scams": 0,
        "legit_correct": 0,
        "false_warnings": 0,
    }

    urgent_genuine_stats = {
        "total": 0,
        "cleared_without_high_risk": 0,
        "flagged_high_risk": 0,
    }

    for item in data:
        text = item["text"]
        cat = item.get("category", "General message")
        sender = item.get("sender", "")
        ground_truth = item["ground_truth"]  # "scam" or "legitimate"
        lang = item.get("language", "English")
        scenario = item.get("scenario_type", "routine_legitimate")

        outcome = check_message(text, category=cat, sender=sender, model_type=model_type)
        assessment = outcome["assessment"]
        ml_label = outcome.get("report", {}).get("ml_result", {}).get("label", "unknown").lower()

        # Hybrid detection considers "High risk" or "Needs verification" as a warning
        is_scam_flagged = assessment in {"High risk", "Needs verification"}

        if lang not in by_language:
            by_language[lang] = {
                "total": 0, "scams": 0, "scams_detected": 0, "missed_scams": 0,
                "legit": 0, "false_warnings": 0, "high_risk_false_alarms": 0, "unable_to_assess": 0
            }

        by_language[lang]["total"] += 1

        if assessment == "Unable to assess":
            by_language[lang]["unable_to_assess"] += 1

        if ground_truth == "scam":
            by_language[lang]["scams"] += 1
            if is_scam_flagged:
                by_language[lang]["scams_detected"] += 1
            else:
                by_language[lang]["missed_scams"] += 1
                missed_scams_list.append({
                    "id": item["id"],
                    "language": lang,
                    "scenario": scenario,
                    "text": text,
                    "assessment": assessment,
                    "score": outcome["score"],
                    "notes": item.get("notes", "")
                })

            # Historical ML alone
            if ml_label == "spam":
                historical_ml_stats["scams_detected"] += 1
            else:
                historical_ml_stats["missed_scams"] += 1

        else:  # legitimate
            by_language[lang]["legit"] += 1
            # Separate tracking: High-risk false alarms vs Needs verification false warnings
            if assessment == "High risk":
                by_language[lang]["high_risk_false_alarms"] += 1
                false_warnings_list.append({
                    "id": item["id"],
                    "language": lang,
                    "scenario": scenario,
                    "severity": "HIGH_RISK_FALSE_ALARM",
                    "text": text,
                    "assessment": assessment,
                    "score": outcome["score"],
                    "evidence_titles": [e["title"] for e in outcome.get("evidence", [])],
                    "notes": item.get("notes", "")
                })
            elif assessment == "Needs verification":
                by_language[lang]["false_warnings"] += 1
                false_warnings_list.append({
                    "id": item["id"],
                    "language": lang,
                    "scenario": scenario,
                    "severity": "NEEDS_VERIFICATION_FALSE_WARNING",
                    "text": text,
                    "assessment": assessment,
                    "score": outcome["score"],
                    "evidence_titles": [e["title"] for e in outcome.get("evidence", [])],
                    "notes": item.get("notes", "")
                })

            if scenario == "urgent_genuine":
                urgent_genuine_stats["total"] += 1
                if assessment == "High risk":
                    urgent_genuine_stats["flagged_high_risk"] += 1
                else:
                    urgent_genuine_stats["cleared_without_high_risk"] += 1

            # Historical ML alone
            if ml_label == "spam":
                historical_ml_stats["false_warnings"] += 1
            else:
                historical_ml_stats["legit_correct"] += 1

        results.append({
            "id": item["id"],
            "language": lang,
            "scenario": scenario,
            "ground_truth": ground_truth,
            "assessment": assessment,
            "score": outcome["score"],
            "ml_label": ml_label
        })

    total_scams = sum(b["scams"] for b in by_language.values())
    total_scams_detected = sum(b["scams_detected"] for b in by_language.values())
    total_missed_scams = sum(b["missed_scams"] for b in by_language.values())

    total_legit = sum(b["legit"] for b in by_language.values())
    total_false_warnings = sum(b["false_warnings"] for b in by_language.values())
    total_high_risk_false_alarms = sum(b["high_risk_false_alarms"] for b in by_language.values())
    total_unable_to_assess = sum(b["unable_to_assess"] for b in by_language.values())

    detection_rate = (total_scams_detected / total_scams) if total_scams else 0.0
    false_warning_rate = (total_false_warnings / total_legit) if total_legit else 0.0

    return {
        "benchmark_type": "Realistic modern threat & genuine message evaluation",
        "synthetic_notice": "All test samples are realistic synthetic scenarios based on FTC, CERT-In, and observed fraud patterns. Avoid claiming real-world accuracy from this small benchmark.",
        "evaluation_independence_disclosure": "This benchmark is kept separate from the historical model training set (data/spam.csv). Heuristic rules were tuned against common observed patterns; specific test scenarios are disclosed in data/detection_evaluation_set.json.",
        "total_samples": len(data),
        "total_scams": total_scams,
        "scams_detected": total_scams_detected,
        "missed_scams_count": total_missed_scams,
        "detection_rate": round(detection_rate, 4),
        "total_legit": total_legit,
        "false_warnings_count": total_false_warnings,
        "high_risk_false_alarms_count": total_high_risk_false_alarms,
        "unable_to_assess_count": total_unable_to_assess,
        "false_warning_rate": round(false_warning_rate, 4),
        "urgent_genuine_breakdown": urgent_genuine_stats,
        "by_language": by_language,
        "historical_classifier_comparison": {
            "description": "Historical ML Classifier (Naive Bayes / SVM) evaluated on the same modern scenarios without heuristic / threat intelligence layer.",
            "scams_detected": historical_ml_stats["scams_detected"],
            "missed_scams": historical_ml_stats["missed_scams"],
            "detection_rate": round(historical_ml_stats["scams_detected"] / total_scams, 4) if total_scams else 0.0,
            "false_warnings": historical_ml_stats["false_warnings"],
            "why_different": (
                "Historical spam classifiers trained on 2000s Enron/SpamAssassin datasets look for bulk marketing keywords. "
                "Modern scams (targeted spear phishing, payment redirection, advance fee recruitment) often lack spam keywords "
                "and are frequently missed by classical ML alone."
            )
        },
        "false_warnings": false_warnings_list,
        "missed_scams": missed_scams_list,
    }
