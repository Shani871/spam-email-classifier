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

DATASET_PATH = os.path.join(PROJECT_ROOT, "dataset", "spam.csv")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")


def load_and_preprocess_data(dataset_path: str = DATASET_PATH):
    """
    Loads dataset and cleans text fields.
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found at {dataset_path}. Run scripts/prepare_dataset.py first.")

    df = pd.read_csv(dataset_path)
    # Ensure columns are normalized
    df.columns = [c.strip().lower() for c in df.columns]
    if "label" not in df.columns or "text" not in df.columns:
        raise ValueError(f"Dataset must contain 'label' and 'text' columns. Found: {df.columns.tolist()}")

    df = df.dropna(subset=['text', 'label']).copy()
    df['label'] = df['label'].astype(str).str.lower().str.strip()
    df = df[df['label'].isin(['ham', 'spam'])].copy()

    # Preprocess text
    df['cleaned_text'] = df['text'].apply(clean_text)
    # Filter out empty texts after cleaning
    df = df[df['cleaned_text'].str.strip() != ""].reset_index(drop=True)

    # Encode label: ham -> 0, spam -> 1
    df['label_binary'] = df['label'].map({'ham': 0, 'spam': 1})
    return df


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


def train_models():
    """
    Executes complete training, evaluation, and serialization workflow.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("Loading and preprocessing dataset...")
    df = load_and_preprocess_data()
    print(f"Dataset ready. Total samples: {len(df)} (Ham: {(df['label'] == 'ham').sum()}, Spam: {(df['label'] == 'spam').sum()})")

    X = df['cleaned_text']
    y = df['label_binary']

    # Stratified split: 80% train, 20% test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"Training set: {len(X_train)} samples, Test set: {len(X_test)} samples.")

    # Feature extraction with TF-IDF
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=6000,
        sublinear_tf=True
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
    nb_path = os.path.join(MODELS_DIR, "spam_classifier_nb.pkl")
    svm_path = os.path.join(MODELS_DIR, "spam_classifier_svm.pkl")
    vec_path = os.path.join(MODELS_DIR, "tfidf_vectorizer.pkl")
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")

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


if __name__ == "__main__":
    train_models()
