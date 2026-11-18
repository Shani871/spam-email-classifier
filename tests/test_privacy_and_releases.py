from datetime import datetime, timedelta, timezone
import json
import numpy as np
from unittest.mock import Mock
import pandas as pd
from src.user_storage import user_scope, delete_account_data
from src import user_storage
from src.active_learning import record_feedback, get_feedback_records, approve_feedback
from src.automation_worker import InboxAutomationWorker


def test_two_users_never_share_corrections_or_rules():
    with user_scope("alice"):
        record_feedback("An ordinary project message", "spam", "ham")
        user_storage.set_sender_rule("alice@example.com", "trust")
    with user_scope("bob"):
        assert get_feedback_records() == []
        assert user_storage.get_sender_rules() == {"whitelist": [], "blacklist": []}
        record_feedback("Another project message", "spam", "ham")
    with user_scope("alice"):
        assert get_feedback_records()[0]["text"] == "An ordinary project message"
        delete_account_data()
        assert get_feedback_records() == []
    with user_scope("bob"):
        assert len(get_feedback_records()) == 1


def test_expired_content_removed():
    user_storage.add_history("High risk", 90, "General message", retention_days=0)
    assert user_storage.list_history() == []


def test_workers_have_separate_credentials_and_actual_actions(monkeypatch):
    a, b = InboxAutomationWorker(user_id="alice"), InboxAutomationWorker(user_id="bob")
    a.configure_credentials("alice@gmail.com", "alice-password")
    assert b.app_password == "" and b.email_address == ""
    monkeypatch.setattr(a, "_fetch_candidate_emails", lambda: [{"id": "11", "full_text": "URGENT verify immediately http://paypa1-security.xyz", "sender": "fraud@example.com"}])
    records = a.scan_once()
    assert records[0]["action"] == "QUARANTINE_RECOMMENDED"
    assert a.stats["threats_quarantined"] == 0
    assert b.audit_log == []


def test_feedback_reaches_training_and_releases_atomically(tmp_path, monkeypatch):
    import src.active_learning as learning
    import src.train as training
    import src.predict as predict
    directory = tmp_path / "models"
    directory.mkdir()
    monkeypatch.setattr(learning, "MODELS_DIR", directory)
    baseline = pd.DataFrame({"text": [f"baseline message {i}" for i in range(100)],
                             "cleaned_text": [f"unique example {i}" for i in range(100)],
                             "label": ["ham", "spam"] * 50, "label_binary": [0, 1] * 50})
    monkeypatch.setattr(training, "load_and_preprocess_data", lambda: baseline)
    classifier = Mock()
    classifier.predict.side_effect = lambda texts: baseline.set_index("cleaned_text").loc[list(texts), "label_binary"].to_numpy()
    classifier.predict_proba.side_effect = lambda texts: np.column_stack([1 - classifier.predict(texts), classifier.predict(texts)]).astype(float)
    monkeypatch.setattr(predict, "load_model", lambda name: classifier)
    monkeypatch.setattr(predict, "decision_threshold", lambda name: 0.5)
    seen = {}
    def candidate(dataframe, output_dir, test_data):
        seen["training"] = dataframe
        seen["holdout"] = test_data
        from pathlib import Path
        Path(output_dir).mkdir(parents=True)
        return {"models": {name: {"precision_spam": 1., "recall_spam": 1.} for name in ["naive_bayes", "svm"]}}
    monkeypatch.setattr(training, "train_models", candidate)
    entry = record_feedback("A corrected recruitment warning with specialword", "ham", "spam", consent_given=True)
    approve_feedback(entry["id"], admin_user={"is_admin": True})
    result = learning.retrain_model_with_feedback(min_feedback_required=1, admin_user={"is_admin": True})
    assert result["success"]
    assert entry["text"] in seen["training"].text.tolist()
    assert not set(seen["training"].cleaned_text) & set(seen["holdout"].cleaned_text)
    assert json.loads((directory / "active.json").read_text())["feedback_count"] == 1
    assert learning.rollback_model(admin_user={"is_admin": True})
    assert not (directory / "active.json").exists()


def test_unapproved_feedback_cannot_trigger_release():
    from src.active_learning import retrain_model_with_feedback
    record_feedback("A correction not yet reviewed", "ham", "spam", consent_given=True)
    assert not retrain_model_with_feedback(1, admin_user={"is_admin": True})["success"]


def test_real_candidate_training_and_rollback(tmp_path, monkeypatch):
    import string
    import src.active_learning as learning
    import src.train as training
    import src.predict as predict
    from src.preprocessing import clean_text
    records = []
    for index in range(120):
        identifier = "token" + string.ascii_lowercase[index // 26] + string.ascii_lowercase[index % 26]
        spam = index % 2
        text = ("claim cash reward lottery prize " if spam else "project meeting notes review team ") + identifier
        records.append({"text": text, "cleaned_text": clean_text(text), "label": "spam" if spam else "ham", "label_binary": spam})
    baseline = pd.DataFrame(records)
    directory = tmp_path / "models"
    training.train_models(baseline, output_dir=str(directory))
    monkeypatch.setattr(learning, "MODELS_DIR", directory)
    monkeypatch.setattr(predict, "MODELS_DIR", str(directory))
    monkeypatch.setattr(training, "load_and_preprocess_data", lambda: baseline)
    predict._LOADED_MODELS.clear()
    baseline_bytes = (directory / "spam_classifier_svm.pkl").read_bytes()
    correction = record_feedback("claim cash reward lottery prize correctedtoken", "ham", "spam", consent_given=True)
    approve_feedback(correction["id"], admin_user={"is_admin": True})
    outcome = learning.retrain_model_with_feedback(1, admin_user={"is_admin": True})
    assert outcome["success"], outcome
    manifest = json.loads((directory / "active.json").read_text())
    assert (directory / "versions" / manifest["version"] / "spam_classifier_svm.pkl").exists()
    assert (directory / "spam_classifier_svm.pkl").read_bytes() == baseline_bytes
    assert predict.predict_email("claim cash reward lottery prize", "svm")["is_spam"]
    assert learning.rollback_model(admin_user={"is_admin": True})
    assert predict.load_model("svm") is not None
    predict._LOADED_MODELS.clear()


def test_regressing_candidate_never_replaces_current_model(tmp_path, monkeypatch):
    import src.active_learning as learning
    import src.train as training
    import src.predict as predict
    directory = tmp_path / "models"
    directory.mkdir()
    monkeypatch.setattr(learning, "MODELS_DIR", directory)
    baseline = pd.DataFrame({"text": [f"baseline {i}" for i in range(100)], "cleaned_text": [f"normalized {i}" for i in range(100)],
                             "label": ["ham", "spam"] * 50, "label_binary": [0, 1] * 50})
    monkeypatch.setattr(training, "load_and_preprocess_data", lambda: baseline)
    classifier = Mock()
    classifier.predict.side_effect = lambda texts: baseline.set_index("cleaned_text").loc[list(texts), "label_binary"].to_numpy()
    classifier.predict_proba.side_effect = lambda texts: np.column_stack([1 - classifier.predict(texts), classifier.predict(texts)]).astype(float)
    monkeypatch.setattr(predict, "load_model", lambda name: classifier)
    monkeypatch.setattr(predict, "decision_threshold", lambda name: 0.5)
    def bad_candidate(dataframe, output_dir, test_data):
        from pathlib import Path
        Path(output_dir).mkdir(parents=True)
        return {"models": {name: {"precision_spam": .4, "recall_spam": .3} for name in ["naive_bayes", "svm"]}}
    monkeypatch.setattr(training, "train_models", bad_candidate)
    correction = record_feedback("unique corrected example for recruitment", "ham", "spam", consent_given=True)
    approve_feedback(correction["id"], admin_user={"is_admin": True})
    assert not learning.retrain_model_with_feedback(1, admin_user={"is_admin": True})["success"]
    assert not (directory / "active.json").exists()
