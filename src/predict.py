"""
Inference module and CLI for Spam Email Classifier.
Loads trained models, predicts Spam/Ham status, calculates calibrated confidence scores,
and identifies key influential keywords present in the input text.
"""

import os
import argparse
import joblib
import numpy as np

import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.preprocessing import clean_text

MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

_LOADED_MODELS = {}


def load_model(model_type: str = "nb"):
    """
    Loads and caches trained pipeline.
    model_type: 'nb' (Naive Bayes) or 'svm' (Support Vector Machine)
    """
    model_type = model_type.lower()
    if model_type in ["nb", "naive_bayes", "naivebayes"]:
        filename = "spam_classifier_nb.pkl"
        key = "nb"
    elif model_type in ["svm", "linear_svm"]:
        filename = "spam_classifier_svm.pkl"
        key = "svm"
    else:
        raise ValueError(f"Unknown model_type '{model_type}'. Choose 'nb' or 'svm'.")

    if key not in _LOADED_MODELS:
        model_path = os.path.join(MODELS_DIR, filename)
        if not os.path.exists(model_path):
            from src.train import train_models
            train_models()
        try:
            _LOADED_MODELS[key] = joblib.load(model_path)
        except Exception:
            from src.train import train_models
            train_models()
            _LOADED_MODELS[key] = joblib.load(model_path)

    return _LOADED_MODELS[key]


def explain_prediction(text_cleaned: str, pipeline, top_k: int = 5):
    """
    Finds the most influential tokens in the specific input text according to TF-IDF weights
    and model parameters.
    """
    vectorizer = pipeline.named_steps['vectorizer']
    classifier = pipeline.named_steps['classifier']

    feature_names = np.array(vectorizer.get_feature_names_out())
    text_vector = vectorizer.transform([text_cleaned])
    nonzero_indices = text_vector.nonzero()[1]

    if len(nonzero_indices) == 0:
        return []

    words_info = []
    # If Naive Bayes
    if hasattr(classifier, "feature_log_prob_"):
        log_diff = classifier.feature_log_prob_[1] - classifier.feature_log_prob_[0]
        for idx in nonzero_indices:
            word = feature_names[idx]
            tfidf_val = text_vector[0, idx]
            importance = log_diff[idx] * tfidf_val
            words_info.append({
                "word": word,
                "importance": float(importance),
                "indicative_of": "Spam" if importance > 0 else "Ham"
            })

    # If SVM (or calibrated SVM)
    else:
        base = classifier
        if hasattr(classifier, "calibrated_classifiers_"):
            base = classifier.calibrated_classifiers_[0].estimator
        if hasattr(base, "coef_"):
            coef = base.coef_[0]
            for idx in nonzero_indices:
                word = feature_names[idx]
                tfidf_val = text_vector[0, idx]
                importance = coef[idx] * tfidf_val
                words_info.append({
                    "word": word,
                    "importance": float(importance),
                    "indicative_of": "Spam" if importance > 0 else "Ham"
                })

    # Sort by absolute impact
    words_info.sort(key=lambda x: abs(x["importance"]), reverse=True)
    return words_info[:top_k]


def predict_email(raw_text: str, model_type: str = "nb") -> dict:
    """
    Predicts whether an email is Spam or Ham.

    Returns:
    {
        "label": "Spam" | "Ham",
        "is_spam": bool,
        "confidence": float (0.0 to 1.0),
        "prob_spam": float,
        "prob_ham": float,
        "model_type": str,
        "cleaned_text": str,
        "key_features": list
    }
    """
    cleaned = clean_text(raw_text)
    if not cleaned.strip():
        return {
            "label": "Ham",
            "is_spam": False,
            "confidence": 0.50,
            "prob_spam": 0.50,
            "prob_ham": 0.50,
            "model_type": model_type,
            "cleaned_text": "",
            "key_features": [],
            "note": "Empty text provided"
        }

    pipeline = load_model(model_type)
    probabilities = pipeline.predict_proba([cleaned])[0]
    prob_ham = float(probabilities[0])
    prob_spam = float(probabilities[1])

    is_spam = prob_spam >= 0.50
    label = "Spam" if is_spam else "Ham"
    confidence = prob_spam if is_spam else prob_ham

    key_features = explain_prediction(cleaned, pipeline)

    return {
        "label": label,
        "is_spam": is_spam,
        "confidence": round(confidence, 4),
        "prob_spam": round(prob_spam, 4),
        "prob_ham": round(prob_ham, 4),
        "model_type": model_type,
        "cleaned_text": cleaned,
        "key_features": key_features
    }


def main():
    parser = argparse.ArgumentParser(description="Predict Spam or Ham for an email text")
    parser.add_argument("text", nargs="?", default=None, help="Email subject/body text")
    parser.add_argument("--text", "-t", dest="flag_text", help="Email subject/body text")
    parser.add_argument("--model", "-m", default="nb", choices=["nb", "svm"], help="Model to use: 'nb' or 'svm'")
    args = parser.parse_args()

    input_text = args.text or args.flag_text
    if not input_text:
        input_text = "Congratulations! You won a $1,000 Walmart gift card. Click here to claim your reward immediately!"
        print(f"No input text passed. Using default test sample:\n\"{input_text}\"\n")

    result = predict_email(input_text, model_type=args.model)

    print("=" * 45)
    print("        EMAIL CLASSIFICATION RESULT        ")
    print("=" * 45)
    print(f" Model Used:   {'Multinomial Naive Bayes' if args.model == 'nb' else 'Support Vector Machine (Linear)'}")
    print(f" Prediction:   {result['label'].upper()}")
    print(f" Confidence:   {result['confidence'] * 100:.2f}%")
    print(f" Probabilities: Spam={result['prob_spam'] * 100:.2f}%, Ham={result['prob_ham'] * 100:.2f}%")
    print("-" * 45)
    print(" Top Influential Words Detected:")
    for feat in result["key_features"]:
        print(f"  • {feat['word']:<12} -> Indicative of {feat['indicative_of']} (weight: {feat['importance']:+.3f})")
    print("=" * 45)


if __name__ == "__main__":
    main()
