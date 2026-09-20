"""
SpamGuard AI - Streamlit Web Application
Interactive Spam Email Classifier comparing Naive Bayes and Support Vector Machine.
Features live inference, keyword attribution, model analytics, NLP pipeline inspector, and batch testing.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# Configure sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.preprocessing import clean_text, inspect_preprocessing_steps
from src.predict import predict_email, load_model, explain_prediction

MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
METRICS_PATH = os.path.join(MODELS_DIR, "metrics.json")
DATASET_PATH = os.path.join(PROJECT_ROOT, "dataset", "spam.csv")

# Set Page Config
st.set_page_config(
    page_title="SpamGuard AI — Email Classifier",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 24px 32px;
        border-radius: 16px;
        color: #ffffff;
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    
    .main-header h1 {
        color: #f8fafc;
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .main-header p {
        color: #94a3b8;
        margin: 8px 0 0 0;
        font-size: 1.05rem;
    }
    
    .status-card {
        padding: 22px;
        border-radius: 14px;
        margin: 16px 0;
        border-left: 6px solid;
        animation: fadeIn 0.4s ease-in-out;
    }
    
    .status-spam {
        background: linear-gradient(135deg, #450a0a 0%, #1c0505 100%);
        border-color: #ef4444;
        color: #fecaca;
    }
    
    .status-ham {
        background: linear-gradient(135deg, #052e16 0%, #021a0c 100%);
        border-color: #22c55e;
        color: #bbf7d0;
    }
    
    .badge-pill {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.5px;
    }
    
    .badge-spam {
        background: #ef4444;
        color: #ffffff;
    }
    
    .badge-ham {
        background: #22c55e;
        color: #ffffff;
    }
    
    .metric-box {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #38bdf8;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .token-chip {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        margin: 3px 4px;
        font-size: 0.88rem;
        font-weight: 600;
    }
    .token-spam {
        background-color: rgba(239, 68, 68, 0.2);
        border: 1px solid #ef4444;
        color: #fca5a5;
    }
    .token-ham {
        background-color: rgba(34, 197, 94, 0.2);
        border: 1px solid #22c55e;
        color: #86efac;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_metrics():
    if not os.path.exists(METRICS_PATH):
        try:
            from src.train import train_models
            train_models()
        except Exception:
            pass
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_dataset_sample():
    if os.path.exists(DATASET_PATH):
        return pd.read_csv(DATASET_PATH)
    return None


metrics_data = load_metrics()
df_dataset = load_dataset_sample()

# Header Banner
st.markdown("""
<div class="main-header">
    <h1>🛡️ SpamGuard AI — Intelligent Email Classifier</h1>
    <p>Production-ready Natural Language Processing pipeline comparing Multinomial Naive Bayes & Linear Support Vector Machine with TF-IDF feature extraction.</p>
</div>
""", unsafe_allow_html=True)

# Preset Email Templates
PRESETS = {
    "Select a preset...": "",
    "🚨 Lottery & Cash Prize Scam": (
        "Subject: Congratulations! You Have Won $5,000,000 Cash Prize!\n\n"
        "Dear Winner, your email was randomly selected in our international lottery promotion. "
        "Claim your $5,000,000 reward immediately by sending your full name and bank details. "
        "Call our agent or click here http://claim-cash-bonus.org now!"
    ),
    "🎣 PayPal Phishing Lure": (
        "Subject: URGENT: Your PayPal Account Has Been Suspended!\n\n"
        "Dear user, unauthorized login attempts were detected from an unknown IP address. "
        "To prevent permanent account lock, verify your bank credentials immediately: "
        "http://secure-paypal-verify-account-now.com"
    ),
    "💼 Corporate Sprint Sync": (
        "Subject: Team Sprint Sync Agenda - Monday 10:00 AM\n\n"
        "Hi team, please review the sprint backlog before our sync tomorrow at 10 AM. "
        "We will discuss pull requests, test coverage reports, and production deployment timelines. "
        "Attached is the slide deck for discussion."
    ),
    "📄 Project Report Submission": (
        "Subject: Final MCA Project Report and Code Submission\n\n"
        "Respected Professor, please find attached my project report, source code repository, "
        "and evaluation results for the Machine Learning Spam Classifier. "
        "Looking forward to the viva presentation."
    ),
    "💳 Bank Wire Fraud": (
        "Subject: Security Alert: Unauthorized wire transfer initiated from your Chase Bank account\n\n"
        "A transfer of $2,400.00 to an overseas account was initiated. If you did not authorize this "
        "transaction, click Cancel Transaction immediately to block the funds: http://chase-security-fraud-alert.ru/cancel"
    )
}

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ Model Configuration")
    model_choice = st.selectbox(
        "Select Classification Model:",
        options=["Multinomial Naive Bayes", "Support Vector Machine (Linear)"],
        index=0
    )
    model_code = "nb" if "Naive" in model_choice else "svm"

    st.markdown("---")
    st.subheader("🎯 Decision Threshold")
    threshold = st.slider(
        "Spam Sensitivity Threshold",
        min_value=0.10,
        max_value=0.90,
        value=0.50,
        step=0.05,
        help="Emails with Spam Probability >= this threshold will be flagged as SPAM. Lowering threshold increases recall but may increase false positives."
    )

    if metrics_data and model_code in metrics_data["models"]:
        st.markdown("---")
        st.subheader("📈 Quick Performance Summary")
        m = metrics_data["models"][model_code]
        c1, c2 = st.columns(2)
        c1.metric("Accuracy", f"{m['accuracy']*100:.1f}%")
        c2.metric("Precision", f"{m['precision_spam']*100:.1f}%")
        c3, c4 = st.columns(2)
        c3.metric("Recall", f"{m['recall_spam']*100:.1f}%")
        c4.metric("F1-Score", f"{m['f1_spam']*100:.1f}%")

    if df_dataset is not None:
        st.markdown("---")
        st.subheader("📂 Dataset Info")
        st.write(f"**Total Samples:** {len(df_dataset):,}")
        st.write(f"**Legitimate (Ham):** {(df_dataset['label'] == 'ham').sum():,}")
        st.write(f"**Spam Messages:** {(df_dataset['label'] == 'spam').sum():,}")


# Tabs Layout
tab_live, tab_compare, tab_nlp, tab_batch = st.tabs([
    "✉️ Live Classifier",
    "📊 Model Comparison & Metrics",
    "🔍 Preprocessing Inspector",
    "📁 Batch CSV Processing"
])

# -------------------------------------------------------------
# TAB 1: Live Email Classifier
# -------------------------------------------------------------
with tab_live:
    st.subheader("Classify Email Subject / Body")
    st.write("Type or paste an email below, or select a pre-configured template to test.")

    col_preset, _ = st.columns([2, 1])
    with col_preset:
        preset_key = st.selectbox("Load Sample Email Template:", list(PRESETS.keys()))

    initial_text = PRESETS[preset_key] if preset_key != "Select a preset..." else ""

    email_input = st.text_area(
        "Email Content:",
        value=initial_text,
        height=180,
        placeholder="e.g. Congratulations! You've won a free gift card. Claim immediately by clicking here..."
    )

    col_btn, col_clear = st.columns([1, 6])
    with col_btn:
        classify_btn = st.button("🚀 Classify Email", type="primary", use_container_width=True)

    if classify_btn or (email_input.strip() and preset_key != "Select a preset..."):
        if not email_input.strip():
            st.warning("Please enter some email text to classify.")
        else:
            with st.spinner("Analyzing text with NLP pipeline..."):
                raw_pred = predict_email(email_input, model_type=model_code)
                
                # Apply custom threshold
                prob_spam = raw_pred["prob_spam"]
                prob_ham = raw_pred["prob_ham"]
                is_spam = prob_spam >= threshold
                label = "Spam" if is_spam else "Ham"
                confidence = prob_spam if is_spam else prob_ham

            # Status Banner
            if is_spam:
                st.markdown(f"""
                <div class="status-card status-spam">
                    <span class="badge-pill badge-spam">🚨 SPAM DETECTED</span>
                    <h2 style="margin: 10px 0 6px 0; color: #f87171;">Flagged as Spam Email</h2>
                    <p style="margin: 0; font-size: 1rem; color: #fca5a5;">
                        This email exhibits strong indicators of unsolicited promotional, fraudulent, or phishing content.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="status-card status-ham">
                    <span class="badge-pill badge-ham">✅ LEGITIMATE EMAIL</span>
                    <h2 style="margin: 10px 0 6px 0; color: #4ade80;">Safe / Ham Email</h2>
                    <p style="margin: 0; font-size: 1rem; color: #86efac;">
                        This email conforms to normal legitimate communication patterns. No spam triggers detected.
                    </p>
                </div>
                """, unsafe_allow_html=True)

            # Metrics Breakdown
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("Predicted Label", label.upper())
            with col_m2:
                st.metric("Classification Confidence", f"{confidence * 100:.2f}%")
            with col_m3:
                st.metric("Spam Probability", f"{prob_spam * 100:.2f}%")

            st.write("**Probability Distribution:**")
            st.progress(prob_spam, text=f"Spam Likelihood: {prob_spam * 100:.1f}% | Ham Likelihood: {prob_ham * 100:.1f}%")

            # Keyword Attribution
            st.markdown("---")
            st.subheader("🔍 Influential Keywords in Input Text")
            st.write("Keywords extracted from your email and their algorithmic contribution to the prediction:")

            if raw_pred["key_features"]:
                chips_html = ""
                for feat in raw_pred["key_features"]:
                    cls_name = "token-spam" if feat["indicative_of"] == "Spam" else "token-ham"
                    sign = "+" if feat["importance"] > 0 else ""
                    chips_html += f'<span class="token-chip {cls_name}">{feat["word"]} ({sign}{feat["importance"]:.2f})</span>'
                st.markdown(chips_html, unsafe_allow_html=True)

                # Feature Table
                df_feat = pd.DataFrame(raw_pred["key_features"])
                df_feat.columns = ["Detected Token", "TF-IDF Weight Impact", "Indicative Of"]
                st.dataframe(df_feat, use_container_width=True, hide_index=True)
            else:
                st.info("No strong vocabulary triggers found from the model dictionary.")


# -------------------------------------------------------------
# TAB 2: Model Comparison & Metrics
# -------------------------------------------------------------
with tab_compare:
    st.subheader("Comparative Evaluation: Naive Bayes vs. Support Vector Machine")
    st.write(
        "Spam filtering systems require high precision to avoid false positives (flagging important emails as spam) "
        "while maintaining high recall to catch nuisance messages."
    )

    if metrics_data:
        m_nb = metrics_data["models"]["naive_bayes"]
        m_svm = metrics_data["models"]["svm"]

        # Comparison Table
        comp_df = pd.DataFrame([
            {
                "Algorithm": "Multinomial Naive Bayes",
                "Accuracy": f"{m_nb['accuracy']*100:.2f}%",
                "Spam Precision": f"{m_nb['precision_spam']*100:.2f}%",
                "Spam Recall": f"{m_nb['recall_spam']*100:.2f}%",
                "Spam F1-Score": f"{m_nb['f1_spam']*100:.2f}%",
                "ROC-AUC": f"{m_nb['roc_auc']:.4f}",
                "False Positives": m_nb["confusion_matrix"]["false_positive"],
                "False Negatives": m_nb["confusion_matrix"]["false_negative"]
            },
            {
                "Algorithm": "Support Vector Machine (Linear)",
                "Accuracy": f"{m_svm['accuracy']*100:.2f}%",
                "Spam Precision": f"{m_svm['precision_spam']*100:.2f}%",
                "Spam Recall": f"{m_svm['recall_spam']*100:.2f}%",
                "Spam F1-Score": f"{m_svm['f1_spam']*100:.2f}%",
                "ROC-AUC": f"{m_svm['roc_auc']:.4f}",
                "False Positives": m_svm["confusion_matrix"]["false_positive"],
                "False Negatives": m_svm["confusion_matrix"]["false_negative"]
            }
        ])

        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Confusion Matrix Comparison")
        col_cm1, col_cm2 = st.columns(2)

        def plot_cm(cm_dict, title):
            cm = np.array([
                [cm_dict["true_negative"], cm_dict["false_positive"]],
                [cm_dict["false_negative"], cm_dict["true_positive"]]
            ])
            fig, ax = plt.subplots(figsize=(4.5, 3.8))
            fig.patch.set_facecolor('#0f172a')
            ax.set_facecolor('#0f172a')
            
            sns.heatmap(
                cm,
                annot=True,
                fmt="d",
                cmap="Blues",
                cbar=False,
                xticklabels=["Pred Ham", "Pred Spam"],
                yticklabels=["Actual Ham", "Actual Spam"],
                ax=ax,
                annot_kws={"size": 13, "weight": "bold", "color": "white"}
            )
            ax.set_title(title, color="white", fontsize=12, pad=12, weight="bold")
            ax.tick_params(colors="white")
            for _, spine in ax.spines.items():
                spine.set_color("#334155")
            return fig

        with col_cm1:
            fig_nb = plot_cm(m_nb["confusion_matrix"], "Naive Bayes Confusion Matrix")
            st.pyplot(fig_nb)
            st.caption(f"False Positives: **{m_nb['confusion_matrix']['false_positive']}** | False Negatives: **{m_nb['confusion_matrix']['false_negative']}**")

        with col_cm2:
            fig_svm = plot_cm(m_svm["confusion_matrix"], "Linear SVM Confusion Matrix")
            st.pyplot(fig_svm)
            st.caption(f"False Positives: **{m_svm['confusion_matrix']['false_positive']}** | False Negatives: **{m_svm['confusion_matrix']['false_negative']}**")

        st.markdown("---")
        st.subheader("Top Global Spam-Indicative Vocabulary")
        col_w1, col_w2 = st.columns(2)

        with col_w1:
            st.write("**Naive Bayes: Top Spam Signals**")
            nb_spam_words = pd.DataFrame(m_nb["top_features"]["spam_keywords"][:10])
            st.dataframe(nb_spam_words, use_container_width=True, hide_index=True)

        with col_w2:
            st.write("**Linear SVM: Top Spam Signals**")
            svm_spam_words = pd.DataFrame(m_svm["top_features"]["spam_keywords"][:10])
            st.dataframe(svm_spam_words, use_container_width=True, hide_index=True)


# -------------------------------------------------------------
# TAB 3: Preprocessing Inspector
# -------------------------------------------------------------
with tab_nlp:
    st.subheader("Interactive NLP Preprocessing Pipeline")
    st.write("Understand each stage in transforming raw natural language text into numerical vectors.")

    demo_text = st.text_input(
        "Enter sentence to inspect preprocessing transformations:",
        value="WIN FREE $1,000 CASH NOW! Click http://win-prizes.com or email bonus@reward.com"
    )

    if demo_text:
        steps = inspect_preprocessing_steps(demo_text)

        st.markdown("#### Pipeline Stages:")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**1. Original Raw Text**")
            st.code(steps["raw"], language="text")

            st.markdown("**2. Case Normalization (Lowercase)**")
            st.code(steps["step_1_lowercase"], language="text")

            st.markdown("**3. Entity Tokenization (URLs, Emails, Currencies)**")
            st.code(steps["step_2_normalized_entities"], language="text")

        with c2:
            st.markdown("**4. Punctuation & Special Character Removal**")
            st.code(steps["step_3_punctuation_removed"], language="text")

            st.markdown("**5. Stopwords Removal & Filtering**")
            st.write("Tokens retained:", steps["step_5_stopwords_removed"])

            st.markdown("**6. Final Normalized Output for TF-IDF**")
            st.success(steps["final_cleaned"])


# -------------------------------------------------------------
# TAB 4: Batch CSV Processing
# -------------------------------------------------------------
with tab_batch:
    st.subheader("Batch Email CSV Classifier")
    st.write("Upload a CSV file containing emails to classify hundreds of messages simultaneously.")

    uploaded_file = st.file_uploader("Upload CSV file (must contain a 'text' or 'message' column):", type=["csv"])

    if uploaded_file is not None:
        try:
            batch_df = pd.read_csv(uploaded_file)
            text_col = None
            for c in ["text", "message", "email", "body", "content"]:
                if c in [col.lower() for col in batch_df.columns]:
                    text_col = [col for col in batch_df.columns if col.lower() == c][0]
                    break

            if not text_col:
                st.error(f"Could not find a text column in CSV. Found columns: {batch_df.columns.tolist()}")
            else:
                st.write(f"Detected text column: **`{text_col}`** ({len(batch_df)} rows)")
                st.dataframe(batch_df.head(5), use_container_width=True)

                if st.button("⚡ Run Batch Classification", type="primary"):
                    with st.spinner("Processing batch emails..."):
                        preds = []
                        confs = []
                        for txt in batch_df[text_col]:
                            res = predict_email(str(txt), model_type=model_code)
                            preds.append(res["label"])
                            confs.append(res["confidence"])

                        batch_df["Prediction"] = preds
                        batch_df["Confidence"] = confs

                    st.success("Batch classification complete!")

                    # Summary
                    sc1, sc2, sc3 = st.columns(3)
                    total_count = len(batch_df)
                    spam_count = (batch_df["Prediction"] == "Spam").sum()
                    ham_count = (batch_df["Prediction"] == "Ham").sum()
                    sc1.metric("Total Emails", total_count)
                    sc2.metric("Spam Count", f"{spam_count} ({spam_count/total_count*100:.1f}%)")
                    sc3.metric("Ham Count", f"{ham_count} ({ham_count/total_count*100:.1f}%)")

                    st.dataframe(batch_df[[text_col, "Prediction", "Confidence"]], use_container_width=True)

                    # Export Download
                    csv_export = batch_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Classified CSV Results",
                        data=csv_export,
                        file_name="classified_emails.csv",
                        mime="text/csv"
                    )
        except Exception as err:
            st.error(f"Error reading CSV: {err}")
