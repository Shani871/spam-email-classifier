# 🛡️ Spam Email Classifier — Machine Learning & NLP System

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://shani-spam-classifier.streamlit.app)
**Live Demo:** [https://shani-spam-classifier.streamlit.app](https://shani-spam-classifier.streamlit.app)

A production-grade, end-to-end Machine Learning system that classifies email and SMS messages as **Spam** or **Legitimate (Ham)** based on natural language text content. Built as a complete MCA major/minor academic project with comparative algorithm evaluation (**Multinomial Naive Bayes** vs. **Support Vector Machine**) and a modern interactive **Streamlit** web application.

---

## 📌 Project Architecture

```
Email / SMS Input Text
          ↓
  Text Preprocessing
  (Lowercasing, Regex Entity Normalization [URL, EMAIL, CURRENCY], Punctuation/Digit Stripping, Stopwords)
          ↓
  Feature Extraction (TF-IDF Vectorizer with Sublinear Term Frequency & N-grams (1,2))
          ↓
  ┌─────────────────────────────────┴─────────────────────────────────┐
  ↓                                                                   ↓
Multinomial Naive Bayes                                     Support Vector Machine (Linear)
  ↓                                                                   ↓
Calibrated Probability Output                               Calibrated Probability Output (Platt Sigmoid)
  └─────────────────────────────────┬─────────────────────────────────┘
                                    ↓
                  Spam / Ham Decision & Confidence Score
                                    ↓
       Influential Vocabulary Attribution & Interactive Visualization
```

---

## 📂 Project Structure

```text
AI Project/
│
├── dataset/
│   └── spam.csv                     # Curated dataset (5,183 samples: Ham & Spam)
│
├── notebooks/
│   └── model_training.ipynb         # Academic walkthrough notebook with EDA & visual plots
│
├── src/
│   ├── __init__.py
│   ├── preprocessing.py             # NLP text cleaning, normalization, and tokenization
│   ├── train.py                     # ML pipeline training, evaluation, and model serialization
│   ├── predict.py                   # High-level inference engine with CLI and word attribution
│   ├── security_analyzer.py         # URL forensics, typosquatting, & psychological coercion analyzer
│   ├── ai_threat_intelligence.py    # Multi-tier threat scoring (0-100) & attack vector classifier
│   ├── automation_worker.py         # Autonomous 24/7 background inbox monitor & triage daemon
│   ├── active_learning.py           # Human-in-the-loop feedback logging & model retraining
│   ├── attachment_analyzer.py       # Email attachment & payload security forensics
│   ├── gmail_actions.py             # Inbox remediation policies & sender whitelist/blacklist
│   ├── llm_threat_reasoning.py      # LLM & offline deep threat reasoning engine
│   ├── gmail_scanner.py             # IMAP SSL inbox scanner
│   └── gmail_api.py                 # REST OAuth 2.0 inbox scanner
│
├── models/
│   ├── spam_classifier_nb.pkl       # Serialized Multinomial Naive Bayes pipeline
│   ├── spam_classifier_svm.pkl      # Serialized Calibrated Linear SVM pipeline
│   ├── tfidf_vectorizer.pkl         # Fitted TF-IDF vectorizer
│   └── metrics.json                 # Pre-computed evaluation metrics and confusion matrices
│
├── tests/
│   ├── __init__.py
│   ├── test_preprocessing.py        # 5 unit tests for text cleaning edge cases
│   ├── test_model.py                # 6 unit tests for model predictions, bounds, and pipelines
│   ├── test_security_analyzer.py    # 6 unit tests for URL forensics and urgency analysis
│   ├── test_automation.py           # 3 unit tests for threat intelligence and background worker
│   ├── test_active_learning.py      # 2 unit tests for feedback logging and validation
│   ├── test_attachment_analyzer.py  # 6 unit tests for double extensions and payload risks
│   └── test_gmail_actions.py        # 2 unit tests for whitelist/blacklist and remediation
│
├── scripts/
│   └── prepare_dataset.py           # Dataset acquisition and modern sample enrichment script
│
├── app.py                           # Modern Streamlit SOC & Email Classifier dashboard
├── requirements.txt                 # Project dependencies
└── README.md                        # Project documentation and Viva preparation guide
```

---

## 🔬 Algorithms & Comparative Evaluation

The system was evaluated on a stratified **80% train / 20% test** split across **15,501 unique emails** ($12,400$ training samples, $3,101$ test samples: $2,404$ Ham, $697$ Spam):

| Metric | Multinomial Naive Bayes | Support Vector Machine (Linear SVM) ⭐ | Optimal Application |
|---|---|---|---|
| **Accuracy** | **94.84%** | **97.81%** | Overall correctness |
| **Precision (Spam)** | **86.83%** | **94.99%** | Minimizing False Positives |
| **Recall (Spam)** | **90.82%** | **95.27%** | Catching elusive spam |
| **F1-Score (Spam)** | **88.78%** | **95.13%** | Harmonic mean balance |
| **ROC-AUC** | **0.9820** | **0.9965** | Discriminative power |
| **False Positives (FP)** | 96 | **35** (out of 2,404 legitimate emails) | **Lower is better** |
| **False Negatives (FN)** | 64 | **33** (out of 697 spam emails) | Missed spam emails |

### Why False Positives Matter Most in Spam Filtering
In real-world email filtering, **a False Positive is significantly worse than a False Negative**:
- A **False Negative** leaves a spam message in the inbox (mild annoyance).
- A **False Positive** sends a critical business email, job offer, or university alert directly to the junk folder (potentially catastrophic).
- **Multinomial Naive Bayes** achieved an outstanding precision of **97.58%** with only 3 false positives out of 904 legitimate emails.

---

## 🚀 Quickstart Guide

### 1. Environment Setup

```bash
# Clone or navigate to the repository
cd "/Users/shanichauhan/Developer/AI Project"

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Dataset Preparation & Model Training

```bash
# Prepare dataset (if dataset/spam.csv is missing)
python scripts/prepare_dataset.py

# Train models and generate serialized pipelines & evaluation metrics
python src/train.py
```

### 3. Run Predictions from CLI

```bash
# Predict spam sample with Naive Bayes
python src/predict.py "Congratulations! You won a $1,000 gift card. Click here to claim your reward immediately!" --model nb

# Predict corporate meeting email with Linear SVM
python src/predict.py "Meeting scheduled for tomorrow at 10 AM to discuss sprint backlog." --model svm
```

### 4. Launch Streamlit Web Application

```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### 5. Run Automated Tests

```bash
pytest tests/ -v
```

---

## 🌐 Web Interface Features (`app.py`)

1. **Autonomous AI Inbox Monitor (SOC)**:
   - 24/7 background worker daemon with configurable polling intervals.
   - Continuous triage telemetry: Total Scanned, Threats Quarantined, Spam Blocked, Clean Passed.
   - Real-time threat audit stream with attack vector classification and deduplication.
2. **AI Threat Intelligence & Security Forensics**:
   - Multi-tier Phishing Threat Score (0–100) combining ML with forensic heuristics.
   - URL & Link inspection: Deceptive anchor mismatch, direct IP addresses, high-risk TLDs, and brand typosquatting (mimicking PayPal, Chase, Apple, Amazon, etc.).
   - Psychological Coercion breakdown: Urgency, Fear, Financial coercion, and Greed bait triggers.
   - Actionable remediation advisories for SOC analysts and users.
3. **Live Email Classifier**:
   - Paste any email subject and body or choose from 5 one-click scenario presets (*Lottery Scam, PayPal Phishing, Corporate Sprint Sync, Project Report Submission, Bank Wire Fraud*).
   - Adjustable sensitivity threshold slider ($0.10$ to $0.90$).
   - Real-time prediction badges (*🚨 SPAM* vs *✅ LEGITIMATE*).
   - Calibrated confidence percentage bar.
   - **Explainability**: Highlights detected keywords with positive/negative TF-IDF feature attribution.
4. **Live Gmail Scanner**:
   - Connect via 16-character App Password (IMAP SSL) or 1-click Google OAuth 2.0 to scan real inboxes.
5. **Model Comparison & Metrics**:
   - Side-by-side performance table.
   - Heatmap confusion matrices for Naive Bayes and SVM.
   - Global top 10 spam trigger vocabulary ranking.
6. **NLP Preprocessing Inspector**:
   - Step-by-step visual dissection: Raw Text $\rightarrow$ Lowercasing $\rightarrow$ Entity normalization $\rightarrow$ Punctuation removal $\rightarrow$ Stopword filtering $\rightarrow$ Cleaned representation.
7. **Batch CSV Processing**:
   - Upload any CSV file with email texts $\rightarrow$ Classify all rows $\rightarrow$ Download classified CSV with predictions and confidence scores.

---

## 🎓 MCA Project Viva / Defense FAQ

### Q1: What is TF-IDF and why is it preferred over Bag-of-Words?
**A:** Bag-of-Words (BoW) only counts frequency. Common words (e.g., "the", "hello") receive high counts even if they carry little discriminative information. **TF-IDF (Term Frequency-Inverse Document Frequency)** offsets this by penalizing words that appear frequently across all documents, highlighting words uniquely characteristic of specific categories (e.g., "lottery", "urgent", "prize").

### Q2: Why does Naive Bayes perform well on text classification?
**A:** Naive Bayes applies Bayes' Theorem with the assumption that features (words) are conditionally independent given the class label. Even though language features are not strictly independent in reality, this assumption simplifies calculation, prevents overfitting in high-dimensional text spaces ($6,000+$ features), and converges with very fast training times.

### Q3: What is Laplace Smoothing in Naive Bayes?
**A:** If an email contains a word that was never seen in the spam training set, the maximum likelihood estimate for $P(\text{word}|\text{spam})$ would be $0$, which would cause the entire posterior probability to collapse to $0$. Laplace smoothing adds $\alpha$ (typically $0.1$ or $1.0$) to the numerator and denominator to ensure non-zero probabilities for unseen terms.

### Q4: How does Linear SVM work for text classification?
**A:** Support Vector Machine maps text vectors into high-dimensional TF-IDF space and seeks the optimal hyperplane with the maximum margin separating the two classes. Linear SVM works exceptionally well on text classification because high-dimensional word representations are almost always linearly separable.

---

## 📜 License
Developed for academic, research, and portfolio demonstration purposes.
