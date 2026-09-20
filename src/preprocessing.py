"""
Preprocessing module for Spam Email Classifier.
Contains text normalization, tokenization, stopword removal, and inspection utilities.
"""

import re
import string

# Standard English stopwords list (built-in, self-contained without requiring heavy external downloads)
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

def clean_text(text: str) -> str:
    """
    Standard text cleaning pipeline for email/SMS messages:
    1. Lowercase text
    2. Normalize URLs to 'urladdr'
    3. Normalize emails to 'emailaddr'
    4. Normalize currency symbols to 'currency'
    5. Remove punctuation and special characters
    6. Remove excess numbers and whitespaces
    7. Remove stopwords
    """
    if not isinstance(text, str):
        return ""

    # 1. Lowercase
    text = text.lower()

    # 2. Normalize URLs
    text = re.sub(r'https?://\S+|www\.\S+', ' urladdr ', text)

    # 3. Normalize email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', ' emailaddr ', text)

    # 4. Normalize currency symbols
    text = re.sub(r'[\$£€₹]', ' currency ', text)

    # 5. Remove punctuation
    text = text.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))

    # 6. Normalize digits/numbers
    text = re.sub(r'\b\d+\b', ' number ', text)

    # 7. Tokenize and filter stopwords & short tokens
    tokens = text.split()
    filtered_tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]

    return " ".join(filtered_tokens)


def inspect_preprocessing_steps(raw_text: str) -> dict:
    """
    Returns step-by-step transformations of the input text for educational UI inspection.
    """
    if not isinstance(raw_text, str):
        raw_text = ""

    s1_lower = raw_text.lower()
    s2_norm = re.sub(r'https?://\S+|www\.\S+', ' [URL] ', s1_lower)
    s2_norm = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', ' [EMAIL] ', s2_norm)
    s2_norm = re.sub(r'[\$£€₹]', ' [CURRENCY] ', s2_norm)

    s3_nopunct = s2_norm.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))
    s4_tokens = [w for w in s3_nopunct.split() if w]
    s5_filtered = [w for w in s4_tokens if w.lower() not in STOPWORDS and len(w) > 1]
    cleaned = " ".join(s5_filtered)

    return {
        "raw": raw_text,
        "step_1_lowercase": s1_lower,
        "step_2_normalized_entities": s2_norm,
        "step_3_punctuation_removed": s3_nopunct,
        "step_4_all_tokens": s4_tokens,
        "step_5_stopwords_removed": s5_filtered,
        "final_cleaned": cleaned
    }
