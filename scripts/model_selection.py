"""Reproducible model selection for the spam classifier.

Everything here uses the TRAINING partition only (the same 80% that src/train.py fits on),
so the held-out test set stays untouched by tuning:

1. Hyperparameter comparison: 3-fold CV over TF-IDF vocabulary size, min_df, whether the
   number/currency/URL placeholder tokens are kept, and classifier.
2. Optional (--ablation): CV with and without the word-count reconstructions
   (dataset/emails-2.csv rows) added to the training folds.

Includes the public corpora in dataset/external/ when they have been downloaded
(scripts/fetch_public_corpora.sh).

Usage:  python scripts/model_selection.py [--out output/model_selection] [--ablation]
"""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from src.train import RANDOM_SEED, _ENRON_STOPWORDS, load_and_preprocess_data


def training_partition(df):
    """Mirrors the split in src.train.train_models and returns only the training rows."""
    strata = df["source"].astype(str) + ":" + df["label_binary"].astype(str)
    train_idx, _ = train_test_split(df.index, test_size=0.20, random_state=RANDOM_SEED, stratify=strata)
    return df.loc[train_idx]


PLACEHOLDER_TOKENS = ("number", "currency", "urladdr", "emailaddr")


def pipeline(max_features, min_df, classifier, drop_placeholders=False):
    stop_words = set(_ENRON_STOPWORDS) | (set(PLACEHOLDER_TOKENS) if drop_placeholders else set())
    return Pipeline([
        ("vectorizer", TfidfVectorizer(ngram_range=(1, 2), max_features=max_features, min_df=min_df,
                                       sublinear_tf=True, stop_words=sorted(stop_words))),
        ("classifier", classifier),
    ])


def cross_validate(make_pipeline, train, extra_train=None, folds=3):
    """Out-of-fold predictions on `train`; `extra_train` rows are added to every training fold only."""
    X, y = train["cleaned_text"].to_numpy(), train["label_binary"].to_numpy()
    predictions = np.zeros(len(y), dtype=int)
    splitter = StratifiedKFold(folds, shuffle=True, random_state=RANDOM_SEED)
    for fit_idx, val_idx in splitter.split(X, y):
        X_fit, y_fit = X[fit_idx], y[fit_idx]
        if extra_train is not None:
            X_fit = np.concatenate([X_fit, extra_train["cleaned_text"].to_numpy()])
            y_fit = np.concatenate([y_fit, extra_train["label_binary"].to_numpy()])
        model = make_pipeline()
        model.fit(X_fit, y_fit)
        predictions[val_idx] = model.predict(X[val_idx])
    return {
        "cv_f1_spam": round(float(f1_score(y, predictions)), 4),
        "cv_precision_spam": round(float(precision_score(y, predictions)), 4),
        "cv_recall_spam": round(float(recall_score(y, predictions)), 4),
        "cv_false_positives": int(((predictions == 1) & (y == 0)).sum()),
        "cv_false_negatives": int(((predictions == 0) & (y == 1)).sum()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "output" / "model_selection"))
    parser.add_argument("--ablation", action="store_true", help="also re-run the word-count reconstruction ablation")
    args = parser.parse_args()
    warnings.filterwarnings("ignore")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    real = load_and_preprocess_data()
    train = training_partition(real)
    svm = lambda C: LinearSVC(C=C, class_weight="balanced", random_state=RANDOM_SEED, max_iter=5000)
    report = {"training_rows": int(len(train)), "folds": 3, "seed": RANDOM_SEED,
              "training_sources": {k: int(v) for k, v in train["source"].value_counts().items()}}

    if args.ablation:
        with_bow = load_and_preprocess_data(include_bow_reconstructions=True)
        bow = with_bow[with_bow["source"] == "bow"]
        report["data_source_ablation"] = {
            "real_text_only": cross_validate(lambda: pipeline(6000, 1, svm(1.0)), train),
            "real_text_plus_word_count_reconstructions": cross_validate(lambda: pipeline(6000, 1, svm(1.0)), train, extra_train=bow),
        }

    configs = [
        (100000, 2, False, "LinearSVC C=1", lambda: svm(1.0)),
        (100000, 2, False, "LinearSVC C=3", lambda: svm(3.0)),
        (300000, 2, False, "LinearSVC C=1", lambda: svm(1.0)),
        (300000, 2, False, "LinearSVC C=0.3", lambda: svm(0.3)),
        (300000, 5, False, "LinearSVC C=1", lambda: svm(1.0)),
        (300000, 2, True, "LinearSVC C=1", lambda: svm(1.0)),
        (300000, 2, False, "LogisticRegression C=30", lambda: LogisticRegression(C=30, class_weight="balanced", max_iter=3000)),
        (300000, 2, False, "MultinomialNB alpha=0.1", lambda: MultinomialNB(alpha=0.1)),
        (300000, 2, False, "MultinomialNB alpha=0.03", lambda: MultinomialNB(alpha=0.03)),
    ]
    grid = []
    for max_features, min_df, drop, name, make in configs:
        started = time.time()
        row = {"max_features": max_features, "min_df": min_df, "drop_placeholder_tokens": drop, "classifier": name}
        row.update(cross_validate(lambda: pipeline(max_features, min_df, make(), drop), train))
        row["seconds"] = round(time.time() - started, 1)
        grid.append(row)
        print(row, flush=True)
    grid.sort(key=lambda r: r["cv_f1_spam"], reverse=True)
    report["grid"] = grid
    report["best"] = grid[0]
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Best:", grid[0])
    print("Report written to", out / "report.json")


if __name__ == "__main__":
    main()
