"""
Model training and comparative evaluation module for Spam Email Classifier.
Trains Multinomial Naive Bayes and Support Vector Machine (LinearSVC with calibration).
Evaluates accuracy, precision, recall, F1-score, confusion matrix, and feature importances.
Saves models and metrics to the models/ directory.
"""

import os
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


def load_and_preprocess_data():
    """
    Discovers, loads, and combines all available datasets in the dataset/ directory:
    - spam.csv (standard SMS/email labeled benchmark)
    - emails.csv (Kaggle raw email dataset with 'text' and 'spam' columns)
    - emails-2.csv (Kaggle email word-count frequency matrix)
    - ham_diverse.csv (curated diverse ham to dilute Enron-corpus bias)

    After combining, Enron-heavy ham examples are capped at 35% of total ham so
    corpus-specific proper nouns (enron, kaminski, vince…) cannot dominate TF-IDF
    ham feature weights.
    """
    dfs = []

    # 1. Base dataset/spam.csv
    spam_path = os.path.join(DATASET_DIR, "spam.csv")
    if os.path.exists(spam_path):
        try:
            df_s = pd.read_csv(spam_path)
            df_s.columns = [c.strip().lower() for c in df_s.columns]
            if "label" in df_s.columns and "text" in df_s.columns:
                df_s = df_s.dropna(subset=['text', 'label'])
                df_s['label'] = df_s['label'].astype(str).str.lower().str.strip()
                df_s = df_s[df_s['label'].isin(['ham', 'spam'])]
                dfs.append(df_s[['label', 'text']])
                print(f"Loaded {len(df_s)} rows from spam.csv")
        except Exception as e:
            print(f"Warning: Failed to load spam.csv: {e}")

    # 2. dataset/emails.csv (raw emails)
    emails_path = os.path.join(DATASET_DIR, "emails.csv")
    if os.path.exists(emails_path):
        try:
            df_e = pd.read_csv(emails_path)
            df_e.columns = [c.strip().lower() for c in df_e.columns]
            if "text" in df_e.columns:
                label_col = "spam" if "spam" in df_e.columns else ("label" if "label" in df_e.columns else None)
                if label_col:
                    df_e['label'] = df_e[label_col].map({1: 'spam', 0: 'ham', '1': 'spam', '0': 'ham', 'spam': 'spam', 'ham': 'ham'})
                    df_e = df_e.dropna(subset=['text', 'label'])
                    dfs.append(df_e[['label', 'text']])
                    print(f"Loaded {len(df_e)} rows from emails.csv")
        except Exception as e:
            print(f"Warning: Failed to load emails.csv: {e}")

    # 3. dataset/emails-2.csv (word-count matrix)
    emails2_path = os.path.join(DATASET_DIR, "emails-2.csv")
    if os.path.exists(emails2_path):
        try:
            df_2 = pd.read_csv(emails2_path)
            if "Prediction" in df_2.columns:
                word_cols = [c for c in df_2.columns if c not in ['Email No.', 'Prediction', 'email no.']]
                vals = df_2[word_cols].values
                cols = list(word_cols)
                texts = []
                for row in vals:
                    words = []
                    for idx in row.nonzero()[0]:
                        words.extend([cols[idx]] * int(row[idx]))
                    texts.append(' '.join(words))
                df_rec = pd.DataFrame({
                    'text': texts,
                    'label': df_2['Prediction'].map({0: 'ham', 1: 'spam', '0': 'ham', '1': 'spam'})
                }).dropna(subset=['text', 'label'])
                dfs.append(df_rec[['label', 'text']])
                print(f"Loaded and reconstructed {len(df_rec)} rows from emails-2.csv")
        except Exception as e:
            print(f"Warning: Failed to load emails-2.csv: {e}")

    # 4. dataset/ham_diverse.csv — curated diverse ham to dilute corpus-specific signals
    diverse_path = os.path.join(DATASET_DIR, "ham_diverse.csv")
    if os.path.exists(diverse_path):
        try:
            df_d = pd.read_csv(diverse_path)
            df_d.columns = [c.strip().lower() for c in df_d.columns]
            if "label" in df_d.columns and "text" in df_d.columns:
                df_d = df_d.dropna(subset=['text', 'label'])
                df_d['label'] = df_d['label'].astype(str).str.lower().str.strip()
                df_d = df_d[df_d['label'] == 'ham']
                dfs.append(df_d[['label', 'text']])
                print(f"Loaded {len(df_d)} rows from ham_diverse.csv")
        except Exception as e:
            print(f"Warning: Failed to load ham_diverse.csv: {e}")

    if not dfs:
        raise FileNotFoundError(f"No valid dataset found in {DATASET_DIR}.")

    df_combined = pd.concat(dfs, ignore_index=True)
    df_combined = df_combined.dropna(subset=['text', 'label']).drop_duplicates(subset=['text']).reset_index(drop=True)
    print(f"Combined unique dataset size: {len(df_combined)} samples")

    # Cap Enron-heavy ham so corpus-specific proper nouns don't dominate features.
    df_combined = balance_ham_sources(df_combined)

    # Preprocess text
    df_combined['cleaned_text'] = df_combined['text'].apply(clean_text)
    # Filter out empty texts after cleaning
    df_combined = df_combined[df_combined['cleaned_text'].str.strip() != ""].drop_duplicates(subset=["cleaned_text"]).reset_index(drop=True)

    # Encode label: ham -> 0, spam -> 1
    df_combined['label_binary'] = df_combined['label'].map({'ham': 0, 'spam': 1})
    return df_combined


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

    # Stratified split: 80% train, 20% test
    if test_data is None:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y
        )
    else:
        X_train, y_train = X, y
        X_test, y_test = test_data["cleaned_text"], test_data["label_binary"]

    print(f"Training set: {len(X_train)} samples, Test set: {len(X_test)} samples.")

    # Feature extraction with TF-IDF.
    # Corpus-specific proper nouns (Enron names, abbreviations) are excluded from the
    # vocabulary so they cannot appear as strong ham features at train or inference time.
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=6000,
        sublinear_tf=True,
        stop_words=list(_ENRON_STOPWORDS),
    )

    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)

    # 1. Train Multinomial Naive Bayes
    print("\nTraining Multinomial Naive Bayes Classifier...")
    nb_clf = MultinomialNB(alpha=0.1)
    nb_clf.fit(X_train_tfidf, y_train)

    # 2. Train Calibrated Linear SVM (yields well-calibrated probabilities via sigmoid)
    print("Training Support Vector Machine (LinearSVC with probability calibration)...")
    base_svm = LinearSVC(C=1.0, class_weight='balanced', random_state=42, max_iter=3000)
    svm_clf = CalibratedClassifierCV(estimator=base_svm, method='sigmoid', cv=3)
    svm_clf.fit(X_train_tfidf, y_train)

    # Evaluate both models
    models = {
        "naive_bayes": (nb_clf, "Multinomial Naive Bayes"),
        "svm": (svm_clf, "Support Vector Machine (Linear)")
    }

    all_metrics = {}

    for key, (model, display_name) in models.items():
        y_pred = model.predict(X_test_tfidf)
        y_proba = model.predict_proba(X_test_tfidf)[:, 1]

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
            "top_features": top_words
        }

        print(f"\n--- {display_name} Performance ---")
        print(f"Accuracy:  {acc * 100:.2f}%")
        print(f"Precision: {prec_spam * 100:.2f}% (Spam)")
        print(f"Recall:    {rec_spam * 100:.2f}% (Spam)")
        print(f"F1-Score:  {f1_spam * 100:.2f}% (Spam)")
        print(f"ROC-AUC:   {roc_auc:.4f}")
        print(f"Confusion Matrix (TN={cm[0][0]}, FP={cm[0][1]}, FN={cm[1][0]}, TP={cm[1][1]})")
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
