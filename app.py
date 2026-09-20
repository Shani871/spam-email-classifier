"""
SpamGuard AI - Streamlit Web Application
Interactive Spam Email Classifier comparing Naive Bayes and Support Vector Machine.
Features live inference, keyword attribution, model analytics, NLP pipeline inspector, and batch testing.
"""

import os
import sys
import json
import re
import warnings
warnings.filterwarnings("ignore")

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
from src.gmail_scanner import scan_gmail_inbox
from src.gmail_api import scan_gmail_with_oauth
import streamlit.components.v1 as components

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
tab_live, tab_gmail, tab_compare, tab_nlp, tab_batch = st.tabs([
    "✉️ Live Classifier",
    "📬 Live Gmail Scanner",
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
        classify_btn = st.button("🚀 Classify Email", type="primary", width="stretch")

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
                st.dataframe(df_feat, width="stretch", hide_index=True)
            else:
                st.info("No strong vocabulary triggers found from the model dictionary.")


# -------------------------------------------------------------
# TAB: Live Gmail Scanner
# -------------------------------------------------------------
# TAB: Live Gmail Scanner
# -------------------------------------------------------------
with tab_gmail:
    st.subheader("📬 Scan Your Real Gmail Inbox for Spam")
    st.write("Connect your Gmail account to scan, analyze, and detect spam messages directly from your inbox.")

    # Check for Firebase OAuth token passed in query parameters
    if "google_token" in st.query_params:
        st.session_state["google_token"] = st.query_params.get("google_token")
        st.session_state["user_email"] = st.query_params.get("user_email", "")
        st.session_state["user_name"] = st.query_params.get("user_name", "")
        st.query_params.clear()

    st.info(
        "💡 **Two ways to connect Gmail:**\n"
        "- **Method A (Works Instantly):** Use your 16-character Google App Password below. No Google Cloud approvals needed!\n"
        "- **Method B (1-Click Google OAuth):** Requires adding your email to **Test Users** in Google Cloud Console."
    )

    # SECTION 1: App Password (IMAP) - Works Instantly
    with st.expander("🔑 Method A: Connect with 16-Character App Password (Instant & Reliable)", expanded=True):
        st.write("Connect securely via IMAP SSL. This bypasses Google's restricted OAuth scope verification.")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            gmail_user = st.text_input("Gmail Address:", placeholder="yourname@gmail.com", key="gmail_user")
        with col_g2:
            gmail_pwd = st.text_input("16-character App Password:", type="password", placeholder="abcd efgh ijkl mnop", key="gmail_pwd")

        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            gmail_folder = st.selectbox("Gmail Folder:", ["INBOX", "[Gmail]/Spam", "[Gmail]/All Mail"], index=0)
        with col_f2:
            gmail_count = st.slider("Number of emails to fetch:", min_value=5, max_value=25, value=10, step=5)
        with col_f3:
            only_unread = st.checkbox("Only unread emails", value=False)

        if st.button("🚀 Connect & Scan Inbox", type="primary", width="stretch", key="imap_scan_btn"):
            clean_usr = str(gmail_user or "").strip().replace('\xa0', '')
            clean_pwd = re.sub(r'[^a-zA-Z0-9]', '', str(gmail_pwd or '')).strip()
            if not clean_usr or not clean_pwd:
                st.error("Please enter both your Gmail address and your 16-character App Password.")
            else:
                with st.spinner(f"Connecting to imap.gmail.com and fetching latest {gmail_count} emails..."):
                    try:
                        scanned_emails = scan_gmail_inbox(
                            email_address=clean_usr,
                            app_password=clean_pwd,
                            folder=gmail_folder,
                            max_emails=gmail_count,
                            only_unread=only_unread,
                            model_type=model_code
                        )

                        if not scanned_emails:
                            st.info("No emails found matching your selection criteria in this folder.")
                        else:
                            st.success(f"Successfully retrieved and classified {len(scanned_emails)} emails!")
                            total_s = len(scanned_emails)
                            spam_s = sum(1 for e in scanned_emails if e["is_spam"])
                            ham_s = total_s - spam_s

                            gm1, gm2, gm3 = st.columns(3)
                            gm1.metric("Total Emails Scanned", total_s)
                            gm2.metric("Spam Detected 🚨", spam_s, delta=f"{spam_s/total_s*100:.1f}%" if spam_s > 0 else "0%", delta_color="inverse")
                            gm3.metric("Legitimate Emails ✅", ham_s, delta=f"{ham_s/total_s*100:.1f}%")

                            st.markdown("---")
                            st.subheader("📋 Scanned Emails")

                            for idx, item in enumerate(scanned_emails, start=1):
                                status_title = "SPAM" if item["is_spam"] else "HAM (CLEAN)"
                                icon = "🚨" if item["is_spam"] else "✅"

                                with st.expander(f"{icon} #{idx} | [{status_title}] {item['subject']} — {item['sender']}", expanded=item["is_spam"]):
                                    st.write(f"**From:** `{item['sender']}`")
                                    st.write(f"**Date:** `{item['date']}`")
                                    st.write(f"**Prediction:** `{item['prediction']}` (Confidence: **{item['confidence']*100:.2f}%** | Spam Probability: **{item['prob_spam']*100:.2f}%**)")
                                    st.write("**Body Preview:**")
                                    st.text(item["body_preview"] if item["body_preview"] else "(Empty body)")

                                    if item["key_features"]:
                                        st.write("**Trigger Vocabulary Identified:**")
                                        chips = ""
                                        for feat in item["key_features"]:
                                            c_name = "token-spam" if feat["indicative_of"] == "Spam" else "token-ham"
                                            chips += f'<span class="token-chip {c_name}">{feat["word"]} ({feat["importance"]:+.2f})</span>'
                                        st.markdown(chips, unsafe_allow_html=True)
                    except Exception as err:
                        st.error(f"Error scanning Gmail: {err}")

    st.markdown("---")

    # SECTION 2: 1-Click Sign in with Google (Firebase)
    with st.expander("🔴 Method B: 1-Click Google Sign-In (Firebase OAuth)", expanded=False):
        st.markdown("""
        > **⚠️ Note on Google Error ("The requested action is invalid"):**  
        > Because our app requests permission to scan inbox contents (`gmail.readonly`), Google marks it as a **Restricted Scope**.  
        > To allow login, open **[Google Cloud OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent?project=spamguard-ai-21bd8)** $\rightarrow$ scroll to **Test Users** $\rightarrow$ click **+ Add Users** and add your email.
        """)

        google_token = st.session_state.get("google_token")
        user_email = st.session_state.get("user_email", "")
        user_name = st.session_state.get("user_name", "")

        if google_token:
            st.success(f"✅ Signed in as **{user_name}** ({user_email})")
            col_oauth1, col_oauth2, col_oauth3 = st.columns([2, 2, 1])
            with col_oauth1:
                oauth_count = st.slider("Number of emails to scan:", min_value=5, max_value=25, value=10, step=5, key="oauth_count")
            with col_oauth2:
                oauth_unread = st.checkbox("Only unread emails", value=False, key="oauth_unread")
            with col_oauth3:
                if st.button("🚪 Sign out", key="signout_btn"):
                    st.session_state.pop("google_token", None)
                    st.session_state.pop("user_email", None)
                    st.session_state.pop("user_name", None)
                    st.rerun()

            if st.button("🚀 Scan Gmail Inbox via Google Account", type="primary", key="oauth_scan_btn", width="stretch"):
                with st.spinner(f"Fetching and analyzing latest {oauth_count} emails from your Gmail inbox..."):
                    try:
                        scanned_emails = scan_gmail_with_oauth(
                            access_token=google_token,
                            max_emails=oauth_count,
                            only_unread=oauth_unread,
                            model_type=model_code
                        )

                        if not scanned_emails:
                            st.info("No matching emails found in your inbox.")
                        else:
                            st.success(f"Successfully retrieved and classified {len(scanned_emails)} emails from Gmail!")
                            total_s = len(scanned_emails)
                            spam_s = sum(1 for e in scanned_emails if e["is_spam"])
                            ham_s = total_s - spam_s

                            gm1, gm2, gm3 = st.columns(3)
                            gm1.metric("Total Emails Scanned", total_s)
                            gm2.metric("Spam Detected 🚨", spam_s, delta=f"{spam_s/total_s*100:.1f}%" if spam_s > 0 else "0%", delta_color="inverse")
                            gm3.metric("Legitimate Emails ✅", ham_s, delta=f"{ham_s/total_s*100:.1f}%")

                            st.markdown("---")
                            st.subheader("📋 Scanned Gmail Messages")

                            for idx, item in enumerate(scanned_emails, start=1):
                                status_title = "SPAM" if item["is_spam"] else "HAM (CLEAN)"
                                icon = "🚨" if item["is_spam"] else "✅"

                                with st.expander(f"{icon} #{idx} | [{status_title}] {item['subject']} — {item['sender']}", expanded=item["is_spam"]):
                                    st.write(f"**From:** `{item['sender']}`")
                                    st.write(f"**Date:** `{item['date']}`")
                                    st.write(f"**Prediction:** `{item['prediction']}` (Confidence: **{item['confidence']*100:.2f}%** | Spam Probability: **{item['prob_spam']*100:.2f}%**)")
                                    st.write("**Body Preview:**")
                                    st.text(item["body_preview"] if item["body_preview"] else "(Empty body)")

                                    if item["key_features"]:
                                        st.write("**Trigger Vocabulary Identified:**")
                                        chips = ""
                                        for feat in item["key_features"]:
                                            c_name = "token-spam" if feat["indicative_of"] == "Spam" else "token-ham"
                                            chips += f'<span class="token-chip {c_name}">{feat["word"]} ({feat["importance"]:+.2f})</span>'
                                        st.markdown(chips, unsafe_allow_html=True)
                    except PermissionError:
                        st.error("Google session expired. Please sign in again.")
                        st.session_state.pop("google_token", None)
                        st.rerun()
                    except Exception as err:
                        st.error(f"Error scanning Gmail via OAuth: {err}")
        else:
            FIREBASE_AUTH_HTML = """
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 22px; border-radius: 14px; border: 1px solid #334155; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                <h4 style="color: #f8fafc; margin-top: 0; margin-bottom: 8px; font-size: 1.15rem;">Sign In with Google via Firebase</h4>
                <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 16px;">
                    Authenticate with 1 click. Zero passwords required. Read-only access to scan your inbox for spam.
                </p>
                <button id="google-login-btn" style="background: #ffffff; color: #1e293b; border: 1px solid #e2e8f0; padding: 11px 22px; font-size: 15px; font-weight: 600; border-radius: 8px; cursor: pointer; display: inline-flex; align-items: center; gap: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.25); transition: all 0.2s ease;">
                    <svg width="18" height="18" viewBox="0 0 18 18">
                        <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.616z"/>
                        <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
                        <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707 0-.59.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.55 0 9s.347 2.825.957 4.039l3.007-2.332z"/>
                        <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z"/>
                    </svg>
                    Sign in with Google
                </button>
                <div id="auth-status" style="margin-top: 12px; font-size: 13px; color: #38bdf8; min-height: 20px;"></div>
            </div>

            <script type="module">
                import { initializeApp } from "https://www.gstatic.com/firebasejs/10.9.0/firebase-app.js";
                import { getAuth, signInWithPopup, GoogleAuthProvider } from "https://www.gstatic.com/firebasejs/10.9.0/firebase-auth.js";

                const firebaseConfig = {
                  apiKey: "AIzaSyDNhwoiC3CxkdrlvgKaUoUwKZvhkq2x1i8",
                  authDomain: "spamguard-ai-21bd8.firebaseapp.com",
                  projectId: "spamguard-ai-21bd8",
                  storageBucket: "spamguard-ai-21bd8.firebasestorage.app",
                  messagingSenderId: "607207854512",
                  appId: "1:607207854512:web:31cc67ea31bd0e8af48675",
                  measurementId: "G-9DZRTJHZR2"
                };

                const app = initializeApp(firebaseConfig);
                const auth = getAuth(app);
                const provider = new GoogleAuthProvider();
                provider.addScope('https://www.googleapis.com/auth/gmail.readonly');

                const btn = document.getElementById('google-login-btn');
                const status = document.getElementById('auth-status');

                btn.addEventListener('click', async () => {
                    status.innerText = "Opening Google Sign-In popup...";
                    try {
                        const result = await signInWithPopup(auth, provider);
                        const credential = GoogleAuthProvider.credentialFromResult(result);
                        const token = credential.accessToken;
                        const email = result.user.email;
                        const name = result.user.displayName || "";
                        status.innerText = `Connected as ${email}! Redirecting...`;

                        const currentUrl = new URL(window.location.href);
                        currentUrl.searchParams.set("google_token", token);
                        currentUrl.searchParams.set("user_email", email);
                        if (name) currentUrl.searchParams.set("user_name", name);
                        window.location.href = currentUrl.toString();
                    } catch (error) {
                        console.error("Firebase auth error:", error);
                        status.innerHTML = `<span style="color: #ef4444;">Login Error: ${error.message}</span>`;
                    }
                });
            </script>
            """
            st.html(FIREBASE_AUTH_HTML, unsafe_allow_javascript=True)


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

        st.dataframe(comp_df, width="stretch", hide_index=True)

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
            st.dataframe(nb_spam_words, width="stretch", hide_index=True)

        with col_w2:
            st.write("**Linear SVM: Top Spam Signals**")
            svm_spam_words = pd.DataFrame(m_svm["top_features"]["spam_keywords"][:10])
            st.dataframe(svm_spam_words, width="stretch", hide_index=True)


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
                st.dataframe(batch_df.head(5), width="stretch")

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

                    st.dataframe(batch_df[[text_col, "Prediction", "Confidence"]], width="stretch")

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
