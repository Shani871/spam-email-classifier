"""
Unit tests for model loading and email prediction.
"""

import pytest
from src.predict import predict_email, load_model


def test_load_models():
    nb_pipe = load_model("nb")
    assert nb_pipe is not None
    assert hasattr(nb_pipe, "predict")

    svm_pipe = load_model("svm")
    assert svm_pipe is not None
    assert hasattr(svm_pipe, "predict")


def test_predict_spam_email_nb():
    text = "Congratulations! You won $5,000 cash! Claim your free prize reward immediately at http://claim-prize.ru"
    res = predict_email(text, model_type="nb")
    assert res["label"] == "Spam"
    assert res["is_spam"] is True
    assert res["confidence"] > 0.80
    assert len(res["key_features"]) > 0


def test_predict_ham_email_nb():
    text = "Hi Professor, please find the project report and documentation attached for your review. Thank you!"
    res = predict_email(text, model_type="nb")
    assert res["label"] == "Ham"
    assert res["is_spam"] is False
    assert res["confidence"] > 0.80


def test_predict_spam_email_svm():
    text = "URGENT: Your PayPal account is locked. Verify bank credentials immediately to avoid suspension."
    res = predict_email(text, model_type="svm")
    assert res["label"] == "Spam"
    assert res["is_spam"] is True
    assert res["confidence"] > 0.70


def test_predict_ham_email_svm():
    text = "Hey team, the sprint retro meeting is moved to 3 PM in Conference Room B. See you there."
    res = predict_email(text, model_type="svm")
    assert res["label"] == "Ham"
    assert res["is_spam"] is False
    assert res["confidence"] > 0.80


def test_predict_empty_text():
    res = predict_email("", model_type="nb")
    assert res["label"] == "Ham"
    assert res["cleaned_text"] == ""
