"""
Model training and comparative evaluation module for Spam Email Classifier.
Trains Multinomial Naive Bayes and Support Vector Machine (LinearSVC with calibration).
Evaluates accuracy, precision, recall, F1-score, confusion matrix, and feature importances.
Saves models and metrics to the models/ directory.
"""

import os
import re
import json
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    roc_auc_score
)

import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.preprocessing import clean_text

DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")
DATASET_PATH = os.path.join(DATASET_DIR, "spam.csv")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

# Tokens that are corpus-specific proper nouns from the Enron email corpus.
# They should not dominate ham feature weights in a general-purpose classifier.
# Unigram tokens to exclude from the TF-IDF vocabulary at both train and inference time.
# These are corpus-specific proper nouns / abbreviations that should not drive
# general-purpose spam/ham classification.
_ENRON_STOPWORDS = frozenset({
    "enron", "vince", "kaminski", "hou", "ect", "hpl", "cc",
    "daren", "shirley", "crenshaw", "stinson", "pjm", "houston",
    "lor", "wat", "gt",
})

# Full set (unigrams + bigrams) used only by the bias audit string-matching check.
_ENRON_MARKERS = _ENRON_STOPWORDS | frozenset({
    "vince kaminski", "ect cc", "ect ect", "hou ect",
    "kaminski hou", "enron enron", "enron com",
    "cc subject", "ect number", "hpl hpl",
})

# Max fraction of total ham examples allowed to be Enron-heavy before downsampling.
_MAX_ENRON_HAM_RATIO = 0.25

# TF-IDF and classifier settings chosen by 5-fold cross-validation on the training
# partition only (scripts/model_selection.py; results in docs/MODEL_CARD.md).
TFIDF_MAX_FEATURES = 300000
TFIDF_MIN_DF = 2
SVM_C = 1.0
NB_ALPHA = 0.1
RANDOM_SEED = 42
# The spam threshold is raised above 0.5 until at most this share of legitimate training
# mail (scored out-of-fold) would be called spam. Missing some spam is preferred to
# flagging normal mail; the app's link, header and rule checks catch much of the rest.
TARGET_HAM_FALSE_POSITIVE_RATE = 0.005


def choose_threshold(y_true, spam_probability, target_fpr: float = TARGET_HAM_FALSE_POSITIVE_RATE) -> float:
    """Lowest threshold (never below 0.5) whose false positive rate on legitimate mail is <= target_fpr."""
    y_true = np.asarray(y_true)
    ham_scores = np.sort(np.asarray(spam_probability)[y_true == 0])
    if len(ham_scores) == 0:
        return 0.5
    allowed = int(np.floor(target_fpr * len(ham_scores)))
    cutoff = ham_scores[len(ham_scores) - allowed - 1]
    return float(min(0.99, max(0.5, np.nextafter(cutoff, 1.0))))


def is_bow_reconstruction(text: str) -> bool:
    """True for pseudo-text rebuilt from a word-count matrix (dataset/emails-2.csv).

    Those rows are a vocabulary-ordered list of repeated words ("the the the to to ect ..."),
    not messages: word order is lost and several columns are substring counts. They are
    excluded from training and evaluation because they lowered accuracy on real text.
    """
    if re.search(r"[^a-z ]", text):
        return False
    tokens = text.split()
    if len(tokens) < 5:
        return False
    repeats = sum(a == b for a, b in zip(tokens, tokens[1:])) / (len(tokens) - 1)
    single_letters = sum(len(t) == 1 for t in tokens) / len(tokens)
    return (len(tokens) >= 12 and repeats >= 0.25) or single_letters >= 0.4


def _is_enron_heavy(text: str) -> bool:
    """
    Returns True when the text is clearly from the Enron email corpus.
    A single unambiguous bigram (hou ect, ect cc, vince kaminski) is enough;
    otherwise two or more medium-strength markers are required.
    """
    lower = text.lower()
    strong_bigrams = ("hou ect", "ect cc", "vince kaminski", "kaminski hou")
    if any(b in lower for b in strong_bigrams):
        return True
    medium = ("enron", "kaminski", "vince", "ect ect", "enron enron")
    hits = sum(1 for m in medium if m in lower)
    return hits >= 2


def balance_ham_sources(df: pd.DataFrame, max_enron_ratio: float = _MAX_ENRON_HAM_RATIO, seed: int = 42) -> pd.DataFrame:
    """
    Caps the proportion of Enron-heavy ham examples so corpus-specific proper nouns
    cannot dominate TF-IDF ham features. Spam examples are never touched.
    """
    ham_mask = df["label"] == "ham"
    ham_df = df[ham_mask].copy()
    spam_df = df[~ham_mask]

    enron_mask = ham_df["text"].apply(_is_enron_heavy)
    enron_ham = ham_df[enron_mask]
    other_ham = ham_df[~enron_mask]

    total_ham = len(ham_df)
    max_enron = int(total_ham * max_enron_ratio)

    if len(enron_ham) > max_enron:
        enron_ham = enron_ham.sample(n=max_enron, random_state=seed)
        print(
            f"Source balance: downsampled Enron-heavy ham from {enron_mask.sum()} "
            f"to {max_enron} ({max_enron_ratio*100:.0f}% cap). "
            f"Non-Enron ham kept: {len(other_ham)}."
        )
    else:
        print(
            f"Source balance: Enron-heavy ham ({enron_mask.sum()}) within "
            f"{max_enron_ratio*100:.0f}% cap — no downsampling needed."
        )

    balanced = pd.concat([other_ham, enron_ham, spam_df], ignore_index=True)
    return balanced.sample(frac=1, random_state=seed).reset_index(drop=True)


def audit_feature_bias(top_features: dict, model_name: str) -> None:
    """
    Warns when known corpus-specific tokens appear in the top ham features,
    indicating residual dataset leakage after balancing.
    Uses whole-word matching so substrings like 'ect' inside 'subject' are not flagged.
    """
    ham_words = [entry["word"].lower() for entry in top_features.get("ham_keywords", [])]

    def _whole_word_match(feature: str, marker: str) -> bool:
        feature_tokens = set(feature.split())
        marker_tokens = set(marker.split())
        return bool(feature_tokens & marker_tokens) and (marker == feature or marker in feature_tokens)

    leaking = [w for w in ham_words if any(_whole_word_match(w, m) for m in _ENRON_MARKERS)]
    if leaking:
        print(
            f"  [bias-audit] {model_name}: corpus-specific tokens still in top ham features: "
            + ", ".join(leaking)
        )
    else:
        print(f"  [bias-audit] {model_name}: no corpus-specific tokens in top ham features.")


EXTERNAL_DIR = os.path.join(DATASET_DIR, "external", "zenodo_8339691")
# Corpora from the Zenodo "Phishing Email Curated Datasets" (record 8339691, CC BY 4.0).
# Nazario_5 / Nigerian_5 are skipped: their legitimate rows are copies from the other sets.
EXTERNAL_CORPORA = ("CEAS_08", "SpamAssasin", "Enron", "Ling", "Nazario", "Nigerian_Fraud", "TREC_05", "TREC_06", "TREC_07")
# Cap per (corpus, label) so no single corpus or era dominates, and training stays fast.
MAX_ROWS_PER_SOURCE_LABEL = 12000
MAX_BODY_CHARS = 6000


def load_external_corpora(max_rows_per_source_label: int = MAX_ROWS_PER_SOURCE_LABEL, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Loads the downloaded public corpora (scripts/fetch_public_corpora.sh) as label/text/source rows.

    Each file has subject, body and label (1 = spam or phishing, 0 = legitimate). Text is
    "Subject: <subject>\n\n<body>" with the body cut to MAX_BODY_CHARS. Missing files are skipped,
    so training still works without the download.
    """
    import csv
    import sys as _sys
    csv.field_size_limit(_sys.maxsize)
    frames = []
    for name in EXTERNAL_CORPORA:
        path = os.path.join(EXTERNAL_DIR, f"{name}.csv")
        if not os.path.exists(path):
            continue
        frame = pd.read_csv(path, engine="python", on_bad_lines="skip")
        frame.columns = [c.strip().lower() for c in frame.columns]
        if "label" not in frame.columns or "body" not in frame.columns:
            print(f"Skipping {name}: unexpected columns {list(frame.columns)}")
            continue
        frame["label"] = pd.to_numeric(frame["label"], errors="coerce")
        frame = frame[frame["label"].isin([0, 1])]
        subject = frame["subject"].fillna("").astype(str) if "subject" in frame.columns else ""
        body = frame["body"].fillna("").astype(str).str.slice(0, MAX_BODY_CHARS)
        out = pd.DataFrame({
            "label": np.where(frame["label"] == 1, "spam", "ham"),
            "text": ("Subject: " + subject + "\n\n" + body).str.strip(),
            "source": name.lower(),
        })
        out = out[out["text"].str.len() > 20]
        parts = []
        for _, group in out.groupby("label"):
            parts.append(group.sample(n=min(len(group), max_rows_per_source_label), random_state=seed))
        out = pd.concat(parts, ignore_index=True)
        print(f"Loaded {len(out)} rows from {name}.csv ({(out['label'] == 'spam').sum()} spam)")
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=["label", "text", "source"])
    return pd.concat(frames, ignore_index=True)


def load_and_preprocess_data(include_bow_reconstructions: bool = False, include_external: bool = True):
    """
    Loads and combines the labelled text in dataset/:
    - spam.csv: merged SMS and email benchmark rows (label, text)
    - emails.csv: raw emails with 'text' and 'spam' columns (already contained in spam.csv;
      loaded so the pipeline still works if spam.csv is regenerated without it)
    - ham_diverse.csv: curated modern legitimate messages

    Each row gets a 'source' (sms, email, modern_ham, bow) used for stratified splitting
    and per-source reporting. Rows rebuilt from the emails-2.csv word-count matrix are
    dropped unless include_bow_reconstructions is True (kept only for the ablation in
    scripts/model_selection.py). Exact duplicates are removed on raw and cleaned text
    before any split, so the same message cannot be in both train and test.
    """
    dfs = []

    spam_path = os.path.join(DATASET_DIR, "spam.csv")
    if os.path.exists(spam_path):
        df_s = pd.read_csv(spam_path)
        df_s.columns = [c.strip().lower() for c in df_s.columns]
        if "label" in df_s.columns and "text" in df_s.columns:
            df_s = df_s.dropna(subset=["text", "label"])
            df_s["label"] = df_s["label"].astype(str).str.lower().str.strip()
            df_s = df_s[df_s["label"].isin(["ham", "spam"])]
            dfs.append(df_s[["label", "text"]].assign(source="benchmark"))
            print(f"Loaded {len(df_s)} rows from spam.csv")

    emails_path = os.path.join(DATASET_DIR, "emails.csv")
    if os.path.exists(emails_path):
        df_e = pd.read_csv(emails_path)
        df_e.columns = [c.strip().lower() for c in df_e.columns]
        label_col = "spam" if "spam" in df_e.columns else ("label" if "label" in df_e.columns else None)
        if "text" in df_e.columns and label_col:
            df_e["label"] = df_e[label_col].map({1: "spam", 0: "ham", "1": "spam", "0": "ham", "spam": "spam", "ham": "ham"})
            df_e = df_e.dropna(subset=["text", "label"])
            dfs.append(df_e[["label", "text"]].assign(source="benchmark"))
            print(f"Loaded {len(df_e)} rows from emails.csv")

    diverse_path = os.path.join(DATASET_DIR, "ham_diverse.csv")
    if os.path.exists(diverse_path):
        df_d = pd.read_csv(diverse_path)
        df_d.columns = [c.strip().lower() for c in df_d.columns]
        if "label" in df_d.columns and "text" in df_d.columns:
            df_d = df_d.dropna(subset=["text", "label"])
            df_d["label"] = df_d["label"].astype(str).str.lower().str.strip()
            df_d = df_d[df_d["label"] == "ham"]
            dfs.append(df_d[["label", "text"]].assign(source="modern_ham"))
            print(f"Loaded {len(df_d)} rows from ham_diverse.csv")

    if include_external:
        external = load_external_corpora()
        if len(external):
            dfs.append(external)

    if not dfs:
        raise FileNotFoundError(f"No valid dataset found in {DATASET_DIR}.")

    df_combined = pd.concat(dfs, ignore_index=True)
    df_combined["text"] = df_combined["text"].astype(str)
    df_combined = df_combined.drop_duplicates(subset=["text"]).reset_index(drop=True)

    benchmark = df_combined["source"] == "benchmark"
    is_bow = df_combined["text"].map(is_bow_reconstruction)
    is_email = df_combined["text"].str.lower().str.lstrip().str.startswith("subject")
    df_combined.loc[benchmark, "source"] = np.where(is_bow[benchmark], "bow", np.where(is_email[benchmark], "email", "sms"))
    dropped = int((df_combined["source"] == "bow").sum())
    if not include_bow_reconstructions:
        df_combined = df_combined[df_combined["source"] != "bow"].reset_index(drop=True)
        print(f"Excluded {dropped} word-count reconstructions that are not real message text.")
    print(f"Combined unique dataset size: {len(df_combined)} samples")

    # Cap Enron-heavy ham so corpus-specific proper nouns don't dominate features.
    df_combined = balance_ham_sources(df_combined)

    df_combined["cleaned_text"] = df_combined["text"].apply(clean_text)
    df_combined = df_combined[df_combined["cleaned_text"].str.strip() != ""].drop_duplicates(subset=["cleaned_text"]).reset_index(drop=True)

    df_combined["label_binary"] = df_combined["label"].map({"ham": 0, "spam": 1})
    return df_combined


def build_vectorizer() -> TfidfVectorizer:
    """Word 1-2 gram TF-IDF. Corpus-specific Enron names are excluded from the vocabulary."""
    return TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=TFIDF_MAX_FEATURES,
        min_df=TFIDF_MIN_DF,
        sublinear_tf=True,
        stop_words=list(_ENRON_STOPWORDS),
    )


def near_duplicate_audit(X_train_tfidf, X_test_tfidf, y_test, y_pred, threshold: float = 0.9) -> dict:
    """Measures train/test near-duplication (TF-IDF cosine >= threshold) and accuracy without it.

    Exact duplicates are removed before splitting, but templated spam campaigns can still
    put near-copies on both sides. Reporting accuracy on the remaining "novel" test rows
    shows how much the headline number depends on them.
    """
    y_test = np.asarray(y_test)
    y_pred = np.asarray(y_pred)
    best = np.zeros(X_test_tfidf.shape[0])
    for start in range(0, X_test_tfidf.shape[0], 500):
        block = X_test_tfidf[start:start + 500] @ X_train_tfidf.T
        best[start:start + 500] = block.max(axis=1).toarray().ravel()
    near = best >= threshold
    novel = ~near
    out = {"cosine_threshold": threshold, "test_rows_with_near_duplicate_in_train": int(near.sum()),
           "share_of_test": round(float(near.mean()), 4), "novel_test_rows": int(novel.sum())}
    if novel.sum() and len(set(y_test[novel])) == 2:
        out["novel_accuracy"] = round(float(accuracy_score(y_test[novel], y_pred[novel])), 4)
        out["novel_precision_spam"] = round(float(precision_score(y_test[novel], y_pred[novel], zero_division=0)), 4)
        out["novel_recall_spam"] = round(float(recall_score(y_test[novel], y_pred[novel], zero_division=0)), 4)
        out["novel_f1_spam"] = round(float(f1_score(y_test[novel], y_pred[novel], zero_division=0)), 4)
    return out


def extract_top_features(vectorizer, classifier, n_features: int = 20):
    """
    Extracts top words associated with Spam and Ham.
    """
    feature_names = np.array(vectorizer.get_feature_names_out())

    # For Naive Bayes
    if hasattr(classifier, "feature_log_prob_"):
        # Log ratio: log(P(w|spam)) - log(P(w|ham))
        log_diff = classifier.feature_log_prob_[1] - classifier.feature_log_prob_[0]
        top_spam_indices = log_diff.argsort()[-n_features:][::-1]
        top_ham_indices = log_diff.argsort()[:n_features]
        return {
            "spam_keywords": [
                {"word": feature_names[idx], "score": float(round(log_diff[idx], 4))}
                for idx in top_spam_indices
            ],
            "ham_keywords": [
                {"word": feature_names[idx], "score": float(round(-log_diff[idx], 4))}
                for idx in top_ham_indices
            ]
        }

    # For Calibrated Linear SVM or base estimator
    base = classifier
    if hasattr(classifier, "calibrated_classifiers_"):
        base = classifier.calibrated_classifiers_[0].estimator

    if hasattr(base, "coef_"):
        coefs = base.coef_[0]
        top_spam_indices = coefs.argsort()[-n_features:][::-1]
        top_ham_indices = coefs.argsort()[:n_features]
        return {
            "spam_keywords": [
                {"word": feature_names[idx], "score": float(round(coefs[idx], 4))}
                for idx in top_spam_indices
            ],
            "ham_keywords": [
                {"word": feature_names[idx], "score": float(round(-coefs[idx], 4))}
                for idx in top_ham_indices
            ]
        }

    return {"spam_keywords": [], "ham_keywords": []}


def train_models(dataframe=None, output_dir=None, test_data=None):
    """
    Executes complete training, evaluation, and serialization workflow.
    """
    artifact_dir = output_dir or MODELS_DIR
    os.makedirs(artifact_dir, exist_ok=True)

    print("Loading and preprocessing dataset...")
    df = load_and_preprocess_data() if dataframe is None else dataframe.copy()
    print(f"Dataset ready. Total samples: {len(df)} (Ham: {(df['label'] == 'ham').sum()}, Spam: {(df['label'] == 'spam').sum()})")

    X = df['cleaned_text']
    y = df['label_binary']

    # Stratified split: 80% train, 20% test, stratified by class and (when known) source,
    # so SMS, email and modern-ham rows are represented in both partitions.
    test_sources = None
    if test_data is None:
        strata = y.astype(str)
        if "source" in df.columns:
            candidate = df["source"].astype(str) + ":" + y.astype(str)
            if candidate.value_counts().min() >= 5:
                strata = candidate
        train_idx, test_idx = train_test_split(df.index, test_size=0.20, random_state=RANDOM_SEED, stratify=strata)
        X_train, X_test, y_train, y_test = X.loc[train_idx], X.loc[test_idx], y.loc[train_idx], y.loc[test_idx]
        if "source" in df.columns:
            test_sources = df.loc[test_idx, "source"].to_numpy()
    else:
        X_train, y_train = X, y
        X_test, y_test = test_data["cleaned_text"], test_data["label_binary"]
        if "source" in test_data.columns:
            test_sources = test_data["source"].to_numpy()

    print(f"Training set: {len(X_train)} samples, Test set: {len(X_test)} samples.")

    # Feature extraction with TF-IDF.
    # Corpus-specific proper nouns (Enron names, abbreviations) are excluded from the
    # vocabulary so they cannot appear as strong ham features at train or inference time.
    # The vectorizer is fitted on the training partition only (no test leakage).
    vectorizer = build_vectorizer()
    if len(X_train) < 200:
        # Tiny corpora (unit tests, first feedback rounds): keep every term.
        vectorizer.set_params(min_df=1)

    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)
    if hasattr(vectorizer, "stop_words_"):
        # Every term cut by max_features/min_df; only used for inspection, and very large when pickled.
        vectorizer.stop_words_ = None

    # 1. Train Multinomial Naive Bayes
    print("\nTraining Multinomial Naive Bayes Classifier...")
    nb_clf = MultinomialNB(alpha=NB_ALPHA)
    nb_clf.fit(X_train_tfidf, y_train)

    # 2. Train Calibrated Linear SVM (yields well-calibrated probabilities via sigmoid)
    print("Training Support Vector Machine (LinearSVC with probability calibration)...")
    base_svm = LinearSVC(C=SVM_C, class_weight='balanced', random_state=RANDOM_SEED, max_iter=5000)
    svm_clf = CalibratedClassifierCV(estimator=base_svm, method='sigmoid', cv=3)
    svm_clf.fit(X_train_tfidf, y_train)

    # Decision thresholds from out-of-fold probabilities on the training partition only.
    thresholds = {"naive_bayes": 0.5, "svm": 0.5}
    if len(X_train) >= 200:
        from sklearn.base import clone
        from sklearn.model_selection import cross_val_predict
        print("Choosing decision thresholds from out-of-fold training predictions...")
        for key, model in (("naive_bayes", nb_clf), ("svm", svm_clf)):
            oof = cross_val_predict(clone(model), X_train_tfidf, y_train, cv=3, method="predict_proba")[:, 1]
            thresholds[key] = choose_threshold(y_train, oof)
            print(f"  {key}: threshold {thresholds[key]:.4f} (target ham false positive rate {TARGET_HAM_FALSE_POSITIVE_RATE:.1%})")

    # Evaluate both models
    models = {
        "naive_bayes": (nb_clf, "Multinomial Naive Bayes"),
        "svm": (svm_clf, "Support Vector Machine (Linear)")
    }

    all_metrics = {}

    for key, (model, display_name) in models.items():
        y_proba = model.predict_proba(X_test_tfidf)[:, 1]
        threshold = thresholds[key]
        y_pred = (y_proba >= threshold).astype(int)
        y_pred_default = (y_proba >= 0.5).astype(int)

        acc = accuracy_score(y_test, y_pred)
        prec_spam = precision_score(y_test, y_pred, pos_label=1, zero_division=0)
        rec_spam = recall_score(y_test, y_pred, pos_label=1, zero_division=0)
        f1_spam = f1_score(y_test, y_pred, pos_label=1, zero_division=0)
        roc_auc = roc_auc_score(y_test, y_proba)
        cm = confusion_matrix(y_test, y_pred).tolist()  # [[TN, FP], [FN, TP]]

        rep = classification_report(y_test, y_pred, target_names=['ham', 'spam'], output_dict=True)
        top_words = extract_top_features(vectorizer, model)

        all_metrics[key] = {
            "display_name": display_name,
            "accuracy": round(float(acc), 4),
            "precision_spam": round(float(prec_spam), 4),
            "recall_spam": round(float(rec_spam), 4),
            "f1_spam": round(float(f1_spam), 4),
            "roc_auc": round(float(roc_auc), 4),
            "confusion_matrix": {
                "true_negative": cm[0][0],
                "false_positive": cm[0][1],
                "false_negative": cm[1][0],
                "true_positive": cm[1][1]
            },
            "classification_report": rep,
            "top_features": top_words,
            "decision_threshold": round(float(threshold), 6),
            "at_threshold_0_5": {
                "precision_spam": round(float(precision_score(y_test, y_pred_default, zero_division=0)), 4),
                "recall_spam": round(float(recall_score(y_test, y_pred_default, zero_division=0)), 4),
                "false_positives": int(((y_pred_default == 1) & (np.asarray(y_test) == 0)).sum()),
            },
        }
        if test_sources is not None:
            by_source = {}
            y_true_arr = np.asarray(y_test)
            for source in sorted(set(test_sources)):
                mask = test_sources == source
                by_source[source] = {
                    "test_rows": int(mask.sum()),
                    "false_positives": int(((y_pred == 1) & (y_true_arr == 0) & mask).sum()),
                    "false_negatives": int(((y_pred == 0) & (y_true_arr == 1) & mask).sum()),
                    "ham_rows": int(((y_true_arr == 0) & mask).sum()),
                    "spam_rows": int(((y_true_arr == 1) & mask).sum()),
                }
            all_metrics[key]["by_source"] = by_source
        audit_rows = np.arange(X_test_tfidf.shape[0])
        if len(audit_rows) > 6000:
            audit_rows = np.random.default_rng(RANDOM_SEED).choice(audit_rows, 6000, replace=False)
        all_metrics[key]["near_duplicate_audit"] = near_duplicate_audit(
            X_train_tfidf, X_test_tfidf[audit_rows], np.asarray(y_test)[audit_rows], y_pred[audit_rows])
        if len(audit_rows) < X_test_tfidf.shape[0]:
            all_metrics[key]["near_duplicate_audit"]["sampled_test_rows"] = int(len(audit_rows))

        print(f"\n--- {display_name} Performance ---")
        print(f"Accuracy:  {acc * 100:.2f}%")
        print(f"Precision: {prec_spam * 100:.2f}% (Spam)")
        print(f"Recall:    {rec_spam * 100:.2f}% (Spam)")
        print(f"F1-Score:  {f1_spam * 100:.2f}% (Spam)")
        print(f"ROC-AUC:   {roc_auc:.4f}")
        print(f"Confusion Matrix (TN={cm[0][0]}, FP={cm[0][1]}, FN={cm[1][0]}, TP={cm[1][1]}) at threshold {threshold:.4f}")
        audit_feature_bias(top_words, display_name)

    # Create end-to-end inference pipelines (taking raw cleaned strings directly)
    nb_pipeline = Pipeline([
        ('vectorizer', vectorizer),
        ('classifier', nb_clf)
    ])
    svm_pipeline = Pipeline([
        ('vectorizer', vectorizer),
        ('classifier', svm_clf)
    ])

    # Save artifacts
    nb_path = os.path.join(artifact_dir, "spam_classifier_nb.pkl")
    svm_path = os.path.join(artifact_dir, "spam_classifier_svm.pkl")
    vec_path = os.path.join(artifact_dir, "tfidf_vectorizer.pkl")
    metrics_path = os.path.join(artifact_dir, "metrics.json")

    joblib.dump(nb_pipeline, nb_path)
    joblib.dump(svm_pipeline, svm_path)
    joblib.dump(vectorizer, vec_path)

    summary_info = {
        "dataset_size": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "ham_count": int((df['label'] == 'ham').sum()),
        "spam_count": int((df['label'] == 'spam').sum()),
        "source_counts": {k: int(v) for k, v in df["source"].value_counts().items()} if "source" in df.columns else {},
        "training_config": {
            "tfidf": {"ngram_range": [1, 2], "max_features": TFIDF_MAX_FEATURES, "min_df": int(vectorizer.min_df), "sublinear_tf": True,
                      "vocabulary_size": len(vectorizer.vocabulary_)},
            "svm": {"C": SVM_C, "class_weight": "balanced", "calibration": "sigmoid, 3-fold"},
            "naive_bayes": {"alpha": NB_ALPHA},
            "seed": RANDOM_SEED,
            "split": "holdout supplied by caller" if test_data is not None else "80/20 stratified by source and label after exact-duplicate removal",
            "scikit_learn": __import__("sklearn").__version__,
        },
        "models": all_metrics
    }

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(summary_info, f, indent=2)

    print(f"\nSaved models and pipelines:")
    print(f" - Naive Bayes: {nb_path}")
    print(f" - SVM:         {svm_path}")
    print(f" - Vectorizer:  {vec_path}")
    print(f" - Metrics:     {metrics_path}")
    print("Training finished successfully!")
    return summary_info


if __name__ == "__main__":
    train_models()
