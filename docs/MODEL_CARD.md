# Model card: spam text classifier

Trained and evaluated on 18 November 2026 with `python src/train.py` (scikit-learn 1.9.1, Python 3.12). Numbers below are copied from that run's `models/metrics.json` and from `output/model_selection/report.json`.

## What the model is and is not

A TF-IDF (word 1–2 grams) text classifier with two heads: a calibrated linear SVM (used by the app) and Multinomial Naive Bayes (shown for comparison). It answers "does this text look like spam or phishing seen in public corpora?". It is one input to the app's assessment, worth at most 45 of 100 risk points, and fewer when the person's mail provider has authenticated the sender (see "How the app uses the score").

It is not a fraud detector, it is English only, and nearly all of its training data is from 1997–2008.

## Data

| Source | Rows used | Period | Notes |
|---|---|---|---|
| TREC 2007 | 23,085 | 2007 | Public spam track corpus |
| TREC 2005 | 22,609 | 2001–2002 | Ham is largely Enron |
| CEAS 2008 | 20,757 | 2008 | Spam challenge corpus; ham is mostly mailing lists |
| Enron (spam/ham) | 20,697 | ~2000–2005 | |
| TREC 2006 | 15,662 | 1997–2006 | |
| SpamAssassin | 5,725 | 2002 | Includes "hard ham" (legitimate bulk mail) |
| SMS spam collection | 5,090 | ~2011 | SMS, kept because people also paste SMS/WhatsApp messages |
| Older project email set | 3,368 | Enron era | Already in the repository |
| Nigerian fraud | 3,235 | 2003–2007 | Advance-fee scams, spam only |
| Ling-Spam | 2,854 | ~2000 | |
| Nazario phishing | 1,520 | 2016–2022 | Phishing only; the newest data |
| Modern legitimate mail (written) | 140 | — | `dataset/ham_diverse.csv` |
| **Total** | **124,742** | | 69,470 legitimate, 55,272 spam |

The public corpora come from "Phishing Email Curated Datasets" by Champa, Rabbi and Zibran (Zenodo record 8339691, CC BY 4.0). They are downloaded with `scripts/fetch_public_corpora.sh` into `dataset/external/` (git-ignored, about 450 MB, checksums in `SHA256SUMS`). The `Nazario_5` and `Nigerian_5` files are not used because their legitimate rows are copies from the other sets.

Cleaning, in order:
- Keep rows labelled 0 or 1; text is subject plus the first 6,000 characters of the body.
- Cap each corpus at 12,000 rows per label so no single corpus or era dominates.
- Remove exact duplicates on raw text.
- Drop 4,631 word-count reconstructions from `dataset/emails-2.csv` (not real messages; see the previous ablation in git history).
- Cap Enron-heavy legitimate mail at 25% (not triggered this time) and normalise text (`src/preprocessing.py`).
- Remove empty and duplicate normalised texts.

All deduplication happens before the train/test split.

## Model selection

`scripts/model_selection.py` ran 3-fold cross-validation on the 99,793 training rows only (the test set was not used), over 9 settings: vocabulary size, `min_df`, whether number/currency/URL placeholder tokens are kept, and classifier.

| Setting | CV spam F1 | CV precision | CV recall |
|---|---|---|---|
| LinearSVC C=1, 300k features, min_df 2 (**chosen**) | 0.9774 | 0.9759 | 0.9789 |
| Same, min_df 5 | 0.9773 | 0.9760 | 0.9786 |
| Same, placeholder tokens removed | 0.9764 | 0.9752 | 0.9775 |
| LinearSVC C=1, 100k features | 0.9753 | 0.9744 | 0.9761 |
| Logistic Regression C=30 | 0.9661 | 0.9612 | 0.9711 |
| Multinomial NB alpha=0.1 | 0.9603 | 0.9719 | 0.9490 |

## Decision threshold

The goal is to flag only spam, so the threshold is not 0.5. It is set to the lowest value at which at most 0.5% of legitimate training mail would be called spam, using out-of-fold predictions on the training partition only. The SVM threshold is 0.887 and the Naive Bayes threshold is 0.858. Both are stored in `metrics.json` and read by `src/predict.py`.

## Held-out test results

24,949 rows (20%), stratified by source and class.

| Model | Accuracy | Spam precision | Spam recall | Spam F1 | ROC AUC | Legitimate mail flagged | Spam missed |
|---|---|---|---|---|---|---|---|
| Linear SVM, threshold 0.887 | 96.93% | 99.52% | 93.52% | 96.43% | 0.9980 | 50 of 13,895 (0.36%) | 716 of 11,054 |
| Linear SVM at 0.5, for comparison | — | 98.00% | 98.09% | — | — | 221 (1.6%) | — |
| Naive Bayes, threshold 0.858 | 94.95% | 99.26% | 89.27% | 94.00% | 0.9947 | 74 | 1,186 |

The higher threshold trades about 4.6 points of spam recall for 77% fewer false alarms.

SVM errors on modern phishing (Nazario, 2016–2022): 38 of 304 missed (87.5% caught). By corpus, legitimate mail flagged ranges from 0 (Ling, modern written ham) to 19 of 2,194 (TREC 2005) and 6 of 896 (SMS).

Leakage checks:
- The vectorizer, classifiers and threshold are fitted on the training partition only.
- 15.7% of a 6,000-row test sample has a training row with TF-IDF cosine similarity of 0.9 or more (templated campaigns). On the rest, SVM accuracy is 96.46% and spam F1 95.44%, close to the headline.

## Test on real present-day email

The question that matters is whether normal mail is flagged. 93 messages from the project owner's own Gmail inbox were used as a private test set, with their permission. Only the subject and first ~200 characters were used; they are not stored and were not used for training. They were scored as text only, without sender headers, which is harder than a real inbox scan.

| | Classifier says spam | App shows "Needs verification" | App shows "High risk" |
|---|---|---|---|
| Previous model (15 Nov) | 20 of 93 | 14 | 0 |
| New model, previous scoring | 14 | 23 | 0 |
| New model and new scoring (current) | 14 | 12 | 0 |

The larger public dataset alone did not fix the complaint: old corpora associate money and account wording with spam, so present-day bank and UPI alerts still score near 1.0. The scoring changes below did most of the work. This sample was looked at three times while making these changes, so it is not a fully independent test.

## How the app uses the score

`src/ai_threat_intelligence.py`, `classifier_points`:
- **Below the threshold:** the classifier adds at most 20 points, so wording alone cannot reach "Needs verification" (40).
- **From the threshold to 1.0:** points rise from 20 to 45.
- **Verified sender:** for messages read from the person's own mailbox, the provider's DMARC result for the From domain is read from the topmost `Authentication-Results` header (`provider_sender_verification`). When it is a pass, classifier points are multiplied by 0.4 and automatic job-keyword checks no longer force "Needs verification". Links, attachments, scam rules and the person's chosen category still count fully.
  - Two of the flagged bank and lead-generation senders in the sample were confirmed to carry `dmarc=pass`. In a simulation, the four bank alerts still flagged as text drop to "No strong warning" when marked as verified.
  - DMARC proves which domain sent a message, not that the mail is wanted: bulk senders and some spammers pass it too.
  - Headers in pasted text and uploaded `.eml` files are never treated as verified.

Modern scam benchmark (29 written scenarios): all 14 scams are still flagged; legitimate messages given a warning fell from 3 to 2; none are High risk. The classifier alone now catches 7 of 14 scams (it was 10 of 14), because of the higher threshold; the rule checks catch the rest.

## Known limits

- Public corpora are old; present-day transactional mail is represented only by 140 written examples. Expect pasted bank alerts and receipts to still get "Needs verification" when there is no sender verification.
- The 93-message inbox sample is small, from one person, and not fully independent of the tuning.
- No non-English training data.
- Model files are pickles tied to scikit-learn 1.9.1 (`requirements-lock.txt`) and are about 54 MB together.
- Admin retraining from feedback refuses to run on a server without the public corpora, because the candidate would be trained on far less data.

## Reproduce

```sh
sh scripts/fetch_public_corpora.sh             # about 450 MB into dataset/external/
.venv/bin/python scripts/model_selection.py    # about 8 minutes
.venv/bin/python src/train.py                  # about 5 minutes
```
