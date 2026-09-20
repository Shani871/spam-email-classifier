"""
Unit tests for text preprocessing functions.
"""

from src.preprocessing import clean_text, inspect_preprocessing_steps, STOPWORDS


def test_clean_text_basic():
    raw = "Hello World! This is a test email."
    cleaned = clean_text(raw)
    assert "hello" in cleaned
    assert "world" in cleaned
    assert "test" in cleaned
    assert "email" in cleaned
    # Stopwords like 'this', 'is', 'a' should be removed
    assert "this" not in cleaned.split()
    assert "is" not in cleaned.split()


def test_clean_text_url_and_email_normalization():
    raw = "Click https://phishing-site.com/verify or email support@bank.com immediately!"
    cleaned = clean_text(raw)
    assert "urladdr" in cleaned
    assert "emailaddr" in cleaned
    assert "immediately" in cleaned


def test_clean_text_currency_symbols():
    raw = "Win $1000 cash or £500 or €250 prize right now!"
    cleaned = clean_text(raw)
    assert "currency" in cleaned
    assert "prize" in cleaned
    assert "win" in cleaned


def test_clean_text_empty_and_special_cases():
    assert clean_text("") == ""
    assert clean_text("   \n\t  ") == ""
    assert clean_text("!!!???....") == ""
    assert clean_text(None) == ""


def test_inspect_preprocessing_steps():
    raw = "WIN $500 cash now at http://win.com!"
    steps = inspect_preprocessing_steps(raw)
    assert "raw" in steps
    assert "step_1_lowercase" in steps
    assert "step_2_normalized_entities" in steps
    assert "step_3_punctuation_removed" in steps
    assert "step_4_all_tokens" in steps
    assert "step_5_stopwords_removed" in steps
    assert "final_cleaned" in steps
    assert "[URL]" in steps["step_2_normalized_entities"]
    assert "[CURRENCY]" in steps["step_2_normalized_entities"]
