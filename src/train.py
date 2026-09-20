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


def load_and_preprocess_data():
    """
    Discovers, loads, and combines all available datasets in the dataset/ directory:
    - spam.csv (standard SMS/email labeled benchmark)
    - emails.csv (Kaggle raw email dataset with 'text' and 'spam' columns)
    - emails-2.csv (Kaggle email word-count frequency matrix)
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

    if not dfs:
        raise FileNotFoundError(f"No valid dataset found in {DATASET_DIR}.")

    df_combined = pd.concat(dfs, ignore_index=True)
    df_combined = df_combined.dropna(subset=['text', 'label']).drop_duplicates(subset=['text']).reset_index(drop=True)
    print(f"Combined unique dataset size: {len(df_combined)} samples")

    # Update spam.csv with consolidated data
    df_combined[['label', 'text']].to_csv(DATASET_PATH, index=False)
    print(f"Consolidated dataset saved to: {DATASET_PATH}")

    # Preprocess text
    df_combined['cleaned_text'] = df_combined['text'].apply(clean_text)
    # Filter out empty texts after cleaning
    df_combined = df_combined[df_combined['cleaned_text'].str.strip() != ""].reset_index(drop=True)

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
