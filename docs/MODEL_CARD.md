# Model card: spam text classifier

Trained and evaluated on 15 November 2026 with `python src/train.py` (scikit-learn 1.9.1, Python 3.12). The numbers below are copied from that run's output in `models/metrics.json` and from `output/model_selection/report.json`.

## What the model is and is not

A TF-IDF (word 1–2 grams) text classifier with two heads: a calibrated linear SVM (used by the app) and Multinomial Naive Bayes (shown for comparison). It answers "does this text look like historical spam?". It is one input to the app's assessment, contributing at most 45 of 100 risk points; links, sender headers, attachments and scam rules provide the rest.

It is not a fraud detector, it is English only, and it has not been validated on real present-day inboxes.

## Data

| Source | Rows used | Notes |
|---|---|---|
| Email benchmark (`dataset/spam.csv`, `dataset/emails.csv`) | 5,435 | Enron-era ham and spam; Enron-heavy ham capped at 25% of ham |
| SMS benchmark (`dataset/spam.csv`) | 5,090 | UCI-style SMS spam collection |
| Modern legitimate mail (`dataset/ham_diverse.csv`) | 140 | Curated, written examples; ham only |
| **Total after cleaning** | **10,665** | 8,686 ham, 1,979 spam |

Cleaning steps, in order: drop rows with missing text or label; remove exact duplicates on raw text; exclude 4,631 word-count reconstructions (below); cap Enron-heavy ham; normalise text (`src/preprocessing.py`); remove empty and duplicate normalised texts. Deduplication happens before the split, so one message cannot be on both sides.

### Excluded: word-count reconstructions

About a third of the previous training set was not message text. `dataset/emails-2.csv` is a word-count matrix, and earlier training rebuilt "messages" from it as vocabulary-ordered repeated words (`the the the to to ect ...`). Word order is lost and several columns count substrings. Five-fold cross-validation on the training partition, with validation folds containing real text only and the previous settings:

| Training data | CV spam F1 | CV false positives | CV false negatives |
|---|---|---|---|
| Real text only | 0.9448 | 89 | 86 |
| Real text + reconstructions | 0.9311 | 123 | 97 |

They are now excluded from training and evaluation. `dataset/emails-2.csv` stays in the repository but is no longer read.

## Model selection

`scripts/model_selection.py` ran 5-fold cross-validation on the 8,532 training rows only, over 56 combinations: vocabulary size (6,000 / 20,000 / 50,000 / 100,000), `min_df` (1 / 2), and LinearSVC (C 0.3 / 1 / 3), Logistic Regression (C 10 / 30) and Multinomial NB (alpha 0.1 / 0.5).

| Classifier (best setting) | CV spam F1 | CV precision | CV recall |
|---|---|---|---|
| LinearSVC, C=3, 100k features, min_df=2 (**chosen**) | 0.9599 | 0.9685 | 0.9514 |
| Logistic Regression, C=30, 50k features | 0.9558 | 0.9564 | 0.9552 |
| Multinomial NB, alpha=0.1, 50k features | 0.9337 | 0.9720 | 0.8984 |
| Previous settings: LinearSVC, C=1, 6k features | 0.9448 | 0.9439 | 0.9457 |

The top few SVM settings are within about 0.002 F1 of each other, which is inside fold-to-fold noise; the practical gain is from the larger vocabulary.

## Held-out test results

2,133 rows (20%), stratified by source and class, never used for fitting or for the grid above.

| Model | Accuracy | Spam precision | Spam recall | Spam F1 | ROC AUC | False positives | False negatives |
|---|---|---|---|---|---|---|---|
| Linear SVM (calibrated) | 98.73% | 96.46% | 96.71% | 96.59% | 0.9960 | 14 of 1,738 ham | 13 of 395 spam |
| Multinomial Naive Bayes | 97.42% | 98.02% | 87.85% | 92.66% | 0.9910 | 7 | 48 |

SVM errors by source: email 11 false positives and 5 false negatives (1,087 rows); SMS 3 and 8 (1,018 rows); modern legitimate mail 0 false positives (28 rows, too few to conclude anything).

### Leakage checks

- The vectorizer and both classifiers are fitted on the training partition only.
- Exact duplicates are removed before splitting.
- Near duplicates: 225 test rows (10.5%) have a training row with TF-IDF cosine similarity of 0.9 or more, typical of templated spam campaigns. On the other 1,908 rows the SVM scores 98.58% accuracy and 95.75% spam F1, so the headline figure does not depend on those near copies.
- One caveat: an exploratory run earlier the same day compared data sources against a held-out split before the cross-validated ablation above was written. The final decision is supported by the cross-validation table, but the test set was not strictly untouched by that one choice.

### Not comparable with the previous figure

The earlier README figure (97.21% on 2,977 rows) was measured on a test set that included the reconstructed rows, so the two numbers describe different test sets. The cross-validation table is the like-for-like comparison.

## Modern scam benchmark (29 written scenarios)

`data/detection_evaluation_set.json`: 14 scams and 15 legitimate messages in English, Hindi and Hinglish. All are synthetic, and 29 is far too few for a rate.

| | Scams flagged | Legitimate messages given a warning | Legitimate flagged High risk |
|---|---|---|---|
| Full assessment, before this work | 14 of 14 | 5 of 15 | 0 |
| Full assessment, now | 14 of 14 | 3 of 15 | 0 |
| Classifier alone (old and new) | 10 of 14 | 5 of 15 | n/a |

Retraining did not improve the classifier on these modern messages: it still misses 4 scams and flags 5 legitimate messages on its own. The drop from 5 to 3 false warnings comes from a rule change (one weak wording cue such as "urgent", with a score under 20, no longer raises the assessment), and that rule was adjusted with this benchmark in view. The 3 remaining false warnings are a job-interview follow-up and an invoice (both categories always ask for verification by design) and a utility statement the classifier scores as spam.

## Known limits

- Training text is mostly from the early 2000s (Enron email, SMS). Present-day notification, support and billing email is represented by 140 written examples. Expect false positives on that kind of mail; the app therefore never shows the classifier verdict alone as a warning.
- No real phishing corpus, no non-English data, no evaluation on a live inbox.
- Probabilities are sigmoid-calibrated on this corpus and should be read as a score, not a likelihood of fraud.
- The model files are pickles tied to scikit-learn 1.9.1 (`requirements-lock.txt`).

## Reproduce

```sh
.venv/bin/python scripts/model_selection.py   # about 6 minutes; writes output/model_selection/report.json
.venv/bin/python src/train.py                 # writes models/*.pkl and models/metrics.json
```
