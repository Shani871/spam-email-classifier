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
import streamlit.components.v1 as components

# Configure sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.preprocessing import clean_text, inspect_preprocessing_steps
from src.predict import predict_email, load_model, explain_prediction
from src.gmail_scanner import scan_gmail_inbox
from src.gmail_api import scan_gmail_with_oauth
from src.security_analyzer import inspect_email_security, extract_urls, analyze_domain
from src.ai_threat_intelligence import compute_threat_intelligence
from src.automation_worker import get_global_worker
from src.active_learning import record_feedback, get_feedback_records, get_feedback_stats, retrain_model_with_feedback
from src.attachment_analyzer import analyze_attachment_metadata, inspect_email_attachments
from src.gmail_actions import add_to_whitelist, add_to_blacklist, remove_sender_rule, get_sender_rules, check_sender_reputation, execute_quarantine_imap
from src.llm_threat_reasoning import explain_threat_with_llm

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

# Top-level handler for Google OAuth redirect query parameters
if "google_token" in st.query_params:
    st.session_state["google_token"] = st.query_params.get("google_token")
    st.session_state["user_email"] = st.query_params.get("user_email", "")
    st.session_state["user_name"] = st.query_params.get("user_name", "")
    st.session_state["just_logged_in"] = True
    st.query_params.clear()


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
    .badge-critical {
        background: #ef4444;
        color: #ffffff;
    }
    .badge-high {
        background: #f97316;
        color: #ffffff;
    }
    .badge-suspicious {
        background: #eab308;
        color: #1e293b;
    }
    .badge-clean {
        background: #22c55e;
        color: #ffffff;
    }
    .status-critical {
        background: linear-gradient(135deg, #450a0a 0%, #2a0808 100%);
        border-color: #ef4444;
        color: #fecaca;
    }
    .status-high {
        background: linear-gradient(135deg, #431407 0%, #270b04 100%);
        border-color: #f97316;
        color: #fed7aa;
    }
    .soc-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .url-tag-danger {
        background-color: rgba(239, 68, 68, 0.2);
        border: 1px solid #ef4444;
        color: #fca5a5;
        padding: 2px 8px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85rem;
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

if st.session_state.get("just_logged_in"):
    u_name = st.session_state.get("user_name") or "User"
    u_mail = st.session_state.get("user_email") or ""
    st.success(
        f"🎉 **Signed in with Google as {u_name} ({u_mail})!** "
        f"Switch to the **'📬 Live Gmail Scanner'** tab to inspect and triage your inbox messages.",
        icon="✅"
    )

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

    if st.session_state.get("google_token"):
        st.markdown("---")
        st.subheader("👤 Connected Google Account")
        u_name = st.session_state.get("user_name") or "Google User"
        u_mail = st.session_state.get("user_email") or ""
        st.success(f"**{u_name}**\n\n`{u_mail}`")
        if st.button("🚪 Sign out of Google", key="sidebar_signout_btn", width="stretch"):
            st.session_state.pop("google_token", None)
            st.session_state.pop("user_email", None)
            st.session_state.pop("user_name", None)
            st.session_state.pop("just_logged_in", None)
            st.rerun()


# Tabs Layout
tab_soc, tab_forensics, tab_learning, tab_live, tab_gmail, tab_compare, tab_nlp, tab_batch = st.tabs([
    "🤖 Autonomous Inbox Monitor (SOC)",
    "🛡️ AI Threat Intelligence & Forensics",
    "🧠 Active Learning & Policy Studio",
    "✉️ Live Classifier",
    "📬 Live Gmail Scanner",
    "📊 Model Comparison & Metrics",
    "🔍 Preprocessing Inspector",
    "📁 Batch CSV Processing"
])

# -------------------------------------------------------------
# TAB: Autonomous Inbox Monitor (SOC)
# -------------------------------------------------------------
with tab_soc:
    st.subheader("🤖 Autonomous AI Inbox Surveillance & Security Operations Center (SOC)")
    st.write(
        "Continuous 24/7 background email triage, heuristic threat hunting, and automated quarantine. "
        "The autonomous daemon inspects candidate emails, evaluates multi-tier risk scores, and logs threats in real time."
    )

    worker = get_global_worker()
    worker_stats = worker.get_stats()
    is_active = worker.is_running()

    # Control Panel Container
    with st.container(border=True):
        st.markdown("#### ⚙️ Autonomous Daemon Controls")

        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 2])

        with col_ctrl1:
            status_badge = "🟢 ACTIVE — CONTINUOUS SURVEILLANCE" if is_active else "🔴 INACTIVE — STANDBY MODE"
            st.write(f"**Daemon Status:** `{status_badge}`")
            if is_active:
                if st.button("⏹️ Stop Background Monitor", type="secondary", width="stretch", key="soc_stop_btn"):
                    worker.stop()
                    st.rerun()
            else:
                if st.button("▶️ Start Background Monitor", type="primary", width="stretch", key="soc_start_btn"):
                    worker.model_type = model_code
                    worker.start()
                    st.rerun()

        with col_ctrl2:
            poll_interval = st.slider(
                "Polling Interval (seconds):",
                min_value=5,
                max_value=120,
                value=worker.interval_seconds,
                step=5,
                key="soc_interval_slider"
            )
            worker.set_interval(poll_interval)

        with col_ctrl3:
            st.write("**Manual / Fast Actions:**")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("⚡ Scan Pass Now", width="stretch", key="soc_scan_once"):
                    with st.spinner("Executing immediate threat evaluation pass..."):
                        worker.model_type = model_code
                        new_items = worker.scan_once()
                    if new_items:
                        st.success(f"Processed {len(new_items)} new message(s)!")
                    else:
                        st.info("No unread or pending emails in queue.")
                    st.rerun()
            with col_b2:
                if st.button("🗑️ Clear Logs", width="stretch", key="soc_clear_logs"):
                    worker.clear_audit_logs()
                    st.success("Audit trail cleared.")
                    st.rerun()

        # Surveillance Data Source
        st.markdown("---")
        source_mode = st.radio(
            "Surveillance Ingestion Source:",
            options=["Simulated Threat Stream (Autonomous Sandbox)", "Live Gmail Account (IMAP / App Password)"],
            index=0 if not (worker.email_address and worker.app_password) else 1,
            horizontal=True,
            key="soc_source_mode"
        )

        if "Live Gmail" in source_mode:
            c_gm1, c_gm2 = st.columns(2)
            with c_gm1:
                soc_email = st.text_input("Gmail Address:", value=worker.email_address, key="soc_email_input")
            with c_gm2:
                soc_pwd = st.text_input("16-character App Password:", value=worker.app_password, type="password", key="soc_pwd_input")
            if st.button("Save Credentials for Background Daemon", key="soc_save_creds"):
                worker.configure_credentials(soc_email, soc_pwd)
                st.success("Credentials saved to background worker!")
        else:
            worker.configure_credentials("", "")
            st.caption("ℹ️ Operating in Autonomous Sandbox mode: periodically ingests simulated high-threat lures and benign emails to demonstrate real-time quarantine.")

    # SOC Telemetry Metrics
    st.markdown("#### 📊 Security Operations Center Telemetry")
    t1, t2, t3, t4 = st.columns(4)
    total_scanned = worker_stats["total_scanned"]
    quarantined = worker_stats["threats_quarantined"]
    spam_flagged = worker_stats["spam_flagged"]
    clean_passed = worker_stats["clean_passed"]

    t1.metric("Total Emails Processed", total_scanned)
    t2.metric("Threats Quarantined 🚨", quarantined, delta=f"{quarantined/total_scanned*100:.1f}%" if total_scanned > 0 else "0%", delta_color="inverse")
    t3.metric("Spam Blocked 🚫", spam_flagged, delta=f"{spam_flagged/total_scanned*100:.1f}%" if total_scanned > 0 else "0%", delta_color="inverse")
    t4.metric("Legitimate Emails Passed ✅", clean_passed, delta=f"{clean_passed/total_scanned*100:.1f}%" if total_scanned > 0 else "0%")

    if worker_stats["last_scan_time"]:
        st.caption(f"🕒 Last automated sweep timestamp: **{worker_stats['last_scan_time']}**")

    # Real-Time Threat Audit Trail
    st.markdown("---")
    st.subheader("📋 Real-Time Threat Audit Stream")
    logs = worker.get_recent_audit_logs(limit=25)

    if not logs:
        st.info("No audit logs recorded yet. Start the background monitor or click 'Scan Pass Now' above.")
    else:
        for idx, entry in enumerate(logs):
            score = entry.get("threat_score", 0)
            level = entry.get("threat_level", "UNKNOWN")
            action = entry.get("action", "PROCESSED")

            action_icon = "🚨" if action == "QUARANTINED" else ("🚫" if action == "FLAGGED_SPAM" else "✅")
            header_str = f"{action_icon} [{action}] {entry.get('subject', 'No Subject')} — Score: {score}/100 ({level})"

            with st.expander(header_str, expanded=(idx == 0 and score >= 70)):
                c_e1, c_e2, c_e3 = st.columns(3)
                with c_e1:
                    st.write(f"**From:** `{entry.get('sender', 'Unknown')}`")
                    st.write(f"**Logged At:** `{entry.get('timestamp')}`")
                with c_e2:
                    st.write(f"**Attack Vector:** `{entry.get('attack_vector', 'N/A')}`")
                    st.write(f"**Threat Level:** `{level}`")
                with c_e3:
                    st.write(f"**Automated Action:** `{action}`")
                    st.progress(min(1.0, score / 100.0), text=f"Threat Score: {score}/100")

                if entry.get("tactics_detected"):
                    st.write("**Detected Threat Tactics:**")
                    for t in entry["tactics_detected"]:
                        st.markdown(f"- ⚠️ {t}")

                if entry.get("advisories"):
                    st.write("**Remediation Advisory:**")
                    for adv in entry["advisories"]:
                        st.markdown(f"- {adv}")

                # Remediation Action Buttons
                st.markdown("---")
                col_act1, col_act2, col_act3 = st.columns(3)
                with col_act1:
                    if st.button("🛡️ Whitelist Sender", key=f"white_{idx}_{entry.get('id')}", width="stretch"):
                        add_to_whitelist(entry.get("sender", ""))
                        st.success(f"Added '{entry.get('sender')}' to whitelist!")
                with col_act2:
                    if st.button("🚫 Blacklist Sender", key=f"black_{idx}_{entry.get('id')}", width="stretch"):
                        add_to_blacklist(entry.get("sender", ""))
                        st.warning(f"Added '{entry.get('sender')}' to blacklist!")
                with col_act3:
                    if st.button("🗑️ Quarantine Email", key=f"quar_{idx}_{entry.get('id')}", width="stretch"):
                        res = execute_quarantine_imap(worker.email_address, worker.app_password, str(entry.get('id')))
                        if res["success"]:
                            st.success(res["message"])
                        else:
                            st.info(res["message"])


# -------------------------------------------------------------
# TAB: AI Threat Intelligence & Forensics
# -------------------------------------------------------------
with tab_forensics:
    st.subheader("🛡️ Deep AI Threat Intelligence & Security Forensics")
    st.write(
        "Inspect any email with multi-tier threat forensics: combines machine learning classification "
        "with URL typosquatting detection, deceptive routing analysis, psychological coercion extraction, and actionable remediation advisories."
    )

    f_col_preset, _ = st.columns([2, 1])
    with f_col_preset:
        f_preset = st.selectbox(
            "Load High-Threat Scenario / Phishing Sample:",
            [
                "Select scenario...",
                "🚨 PayPal Account Suspension & Credential Harvesting",
                "💳 Chase Wire Fraud & IP Redirection Lure",
                "🎁 International Lottery & Cash Prize Bait",
                "💼 Legitimate Corporate Strategy & Sync Notes"
            ],
            key="forensic_preset_select"
        )

    f_presets_map = {
        "🚨 PayPal Account Suspension & Credential Harvesting": (
            "Subject: URGENT: Your PayPal Account Has Been Suspended!\n\n"
            "Dear customer, unauthorized login detected from Russia. To prevent permanent lock, "
            "verify your bank credentials immediately: http://paypa1-security-verify-account-now.xyz\n\n"
            "Failure to act within 24 hours will result in permanent account termination."
        ),
        "💳 Chase Wire Fraud & IP Redirection Lure": (
            "Subject: Security Alert: Unauthorized wire transfer of $2,850 initiated\n\n"
            "A wire transfer of $2,850.00 was requested from your checking account. "
            "If you did not authorize this, click cancel immediately: http://192.168.1.105/chase/cancel\n"
            "Otherwise funds will be wired promptly."
        ),
        "🎁 International Lottery & Cash Prize Bait": (
            "Subject: Congratulations! You Have Won $5,000,000 Cash Prize!\n\n"
            "Dear Winner, your email was randomly selected in our international lottery promotion. "
            "Claim your $5,000,000 reward immediately by sending your full name and bank wire details to claim-bonus@reward-fund.ru."
        ),
        "💼 Legitimate Corporate Strategy & Sync Notes": (
            "Subject: Team Sprint Sync Agenda - Monday 10:00 AM\n\n"
            "Hi team, please review the sprint backlog before our sync tomorrow at 10 AM. "
            "We will discuss pull requests, test coverage reports, and production deployment timelines. "
            "Attached is the slide deck for discussion."
        )
    }

    initial_f_text = f_presets_map.get(f_preset, "")
    forensic_text_input = st.text_area(
        "Paste email body or full message headers:",
        value=initial_f_text,
        height=180,
        placeholder="Paste an email message or suspicious content with links...",
        key="forensic_email_input"
    )

    col_att, col_key = st.columns([2, 2])
    with col_att:
        sim_att = st.selectbox(
            "Simulate Attachment (Payload Testing):",
            [
                "None (No Attachment)",
                "invoice_overdue.pdf.exe (Double Extension Trojan)",
                "quarterly_bonus_schedule.xlsm (Macro-Enabled Office Document)",
                "system_security_patch.vbs (VBScript Payload)",
                "project_proposal.pdf (Benign Document)"
            ],
            key="forensic_att_select"
        )
    with col_key:
        llm_api_key = st.text_input("Gemini API Key (Optional for live LLM):", type="password", key="gemini_key_forensic", help="Leave blank to use built-in offline threat reasoner.")

    active_attachments = []
    if "None" not in sim_att:
        att_filename = sim_att.split(" ")[0]
        active_attachments.append({"filename": att_filename, "size": 240000})

    f_btn_col, _ = st.columns([1, 5])
    with f_btn_col:
        run_forensics = st.button("🛡️ Run Deep Threat Inspection", type="primary", width="stretch", key="run_forensics_btn")

    if run_forensics or (forensic_text_input.strip() and f_preset != "Select scenario..."):
        if not forensic_text_input.strip():
            st.warning("Please enter email text to inspect.")
        else:
            with st.spinner("Executing multi-tier AI threat analysis & forensic dissection..."):
                t_report = compute_threat_intelligence(
                    forensic_text_input,
                    model_type=model_code,
                    attachments=active_attachments
                )

            t_score = t_report["threat_score"]
            t_level = t_report["threat_level"]
            t_vector = t_report["attack_vector"]
            u_info = t_report["url_forensics"]
            p_info = t_report["psychological_forensics"]
            att_info = t_report.get("attachment_forensics", {})

            # Hero Threat Card
            card_cls = "status-critical" if t_score >= 75 else ("status-high" if t_score >= 50 else "status-ham")
            badge_cls = "badge-critical" if t_score >= 75 else ("badge-high" if t_score >= 50 else "badge-ham")

            action_desc = "🚨 Immediate quarantine and containment recommended." if t_report["is_action_required"] else "✅ Message evaluated as clean with no critical security indicators."

            st.markdown(f"""
            <div class="status-card {card_cls}">
                <span class="badge-pill {badge_cls}">THREAT SCORE: {t_score}/100 — {t_level}</span>
                <h2 style="margin: 10px 0 6px 0;">{t_vector}</h2>
                <p style="margin: 0; font-size: 1.05rem;">
                    <b>Action Required:</b> {action_desc}
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Forensic Inspection Containers
            fc1, fc2 = st.columns(2)

            with fc1:
                with st.container(border=True):
                    st.markdown("#### 🔗 URL & Link Forensics")
                    st.write(f"Total Extracted URLs: **{u_info['url_count']}**")

                    if u_info["has_deceptive_link"]:
                        st.error("🚨 **Deceptive Link Detected:** Anchor text displays a trusted destination while underlying URL targets another domain.")
                    if u_info["has_suspicious_domain"]:
                        st.warning("⚠️ **Suspicious TLD / Domain:** Destination uses a high-risk TLD or unverified infrastructure.")
                    if u_info["has_ip_link"]:
                        st.error("🚨 **Direct IP Link:** Embedded URL targets a raw IP address, bypassing standard DNS reputation.")

                    if u_info["urls"]:
                        for idx_u, u_data in enumerate(u_info["urls"], start=1):
                            d_meta = u_data.get("domain_analysis", {})
                            brand_spoof = d_meta.get("impersonated_brand")
                            with st.container():
                                st.markdown(f"**Link #{idx_u}:** `{u_data['url']}`")
                                if brand_spoof:
                                    st.markdown(f"- 🚨 **Brand Impersonation:** Mimicking official `{brand_spoof}` domain!")
                                if u_data.get("is_deceptive"):
                                    st.markdown(f"- ⚠️ **Deceptive Routing:** {u_data.get('deceptive_reason')}")
                                if d_meta.get("is_suspicious_tld"):
                                    st.markdown(f"- ⚠️ **High-Risk TLD:** `.{d_meta.get('tld')}`")
                                st.markdown("---")
                    else:
                        st.info("No external links or URLs detected in the message.")

            with fc2:
                with st.container(border=True):
                    st.markdown("#### 🧠 Psychological Coercion Tactics")
                    st.write(f"Psychological Urgency Score: **{p_info['urgency_score'] * 100:.0f}%**")
                    st.progress(p_info["urgency_score"])

                    coercion = p_info["coercion_tactics"]
                    if coercion:
                        for tactic, triggers in coercion.items():
                            tactic_name = tactic.replace("_", " ").title()
                            st.markdown(f"**{tactic_name}:**")
                            for trig in triggers:
                                st.markdown(f"- 🚩 Found trigger: `\"{trig}\"`")
                    else:
                        st.success("No aggressive psychological manipulation or artificial urgency detected.")

            # Attachment Forensics Card if attachments present
            if att_info.get("attachment_count", 0) > 0:
                with st.container(border=True):
                    st.markdown("#### 📎 Attachment & Payload Forensics")
                    st.write(f"Attachments Inspected: **{att_info['attachment_count']}** | Highest Risk: **{att_info['highest_risk_level']}**")
                    for rep in att_info["attachment_reports"]:
                        is_crit = rep["risk_level"] in ["CRITICAL", "HIGH"]
                        box_fn = st.error if is_crit else st.success
                        box_fn(f"**File:** `{rep['filename']}` — Risk: **{rep['risk_level']}**")
                        for r in rep["risk_reasons"]:
                            st.markdown(f"- ⚠️ {r}")

            # LLM Deep Threat Reasoner
            with st.expander("🧠 LLM Attacker Motive & Deep Threat Reasoning Breakdown", expanded=t_score >= 70):
                with st.spinner("Synthesizing natural language threat narrative..."):
                    llm_expl = explain_threat_with_llm(
                        forensic_text_input,
                        subject="Security Inspection",
                        sender="investigated-sender@external.com",
                        api_key=llm_api_key.strip() if llm_api_key else None
                    )

                st.caption(f"Engine: `{llm_expl.get('mode', 'OFFLINE_SEMANTIC_REASONER')}`")
                st.markdown(f"**Executive Cyber Threat Summary:**\n{llm_expl.get('executive_summary', '')}")

                st.markdown("**Psychological Attack Vector:**")
                for p_tactic in llm_expl.get("psychological_breakdown", []):
                    st.markdown(p_tactic)

                st.markdown("**Technical Evasion Techniques:**")
                for t_tactic in llm_expl.get("technical_breakdown", []):
                    st.markdown(t_tactic)

                st.markdown(f"**Blast Radius & Organizational Impact:**\n{llm_expl.get('blast_radius_assessment', '')}")

            # Full Width Remediation Advisory Container
            with st.container(border=True):
                st.markdown("#### 🛡️ AI Security Remediation & Advisory Guidance")
                for adv in t_report["security_advisories"]:
                    st.markdown(f"- {adv}")
                if t_score >= 70:
                    st.caption("🔒 Recommended SOC Policy: Automatically blacklist sender domain and quarantine message.")


# -------------------------------------------------------------
# TAB: Active Learning & Policy Studio
# -------------------------------------------------------------
with tab_learning:
    st.subheader("🧠 Active Learning & Security Policy Studio")
    st.write(
        "Empower continuous self-improvement through Human-in-the-Loop feedback. "
        "Correct misclassified emails to fine-tune model parameters and manage persistent sender whitelist/blacklist policies."
    )

    fb_stats = get_feedback_stats()

    # Feedback KPIs
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Total Feedback Logged", fb_stats["total_feedback"])
    f2.metric("False Positives Corrected", fb_stats["false_positives_corrected"])
    f3.metric("False Negatives Corrected", fb_stats["false_negatives_corrected"])
    f4.metric("Agreement Confirmations", fb_stats["confirmed_correct"])

    # Section 1: Retraining Engine
    with st.container(border=True):
        st.markdown("#### ⚡ Supervised Model Retraining on Feedback")
        st.write(
            "Trigger an automated supervised retraining pass that synthesizes the baseline dataset with all verified user feedback. "
            "New models are evaluated against validation thresholds before updating active weights."
        )

        col_retrain, col_feedback_clear = st.columns([2, 2])
        with col_retrain:
            if st.button("🚀 Retrain Models on User Feedback", type="primary", width="stretch", key="retrain_models_btn"):
                with st.spinner("Retraining TF-IDF vectorizer and recalibrating Naive Bayes & Linear SVM..."):
                    retrain_res = retrain_model_with_feedback(min_feedback_required=1)
                if retrain_res["success"]:
                    st.success(retrain_res["message"])
                    st.rerun()
                else:
                    st.warning(retrain_res["message"])

        with col_feedback_clear:
            if st.button("🗑️ Clear Feedback Data", width="stretch", key="clear_fb_btn"):
                from src.active_learning import clear_feedback_data
                clear_feedback_data()
                st.success("Feedback log cleared.")
                st.rerun()

    # Section 2: Feedback Log Table
    with st.container(border=True):
        st.markdown("#### 📋 User Corrections & Active Learning Queue")
        fb_records = get_feedback_records(limit=25)
        if not fb_records:
            st.info("No user feedback logged yet. You can report false positives/negatives in the 'Live Classifier' tab.")
        else:
            df_fb = pd.DataFrame(fb_records)
            st.dataframe(df_fb, width="stretch", hide_index=True)

    # Section 3: Sender Reputation Policies
    with st.container(border=True):
        st.markdown("#### 🛡️ Sender Whitelist & Blacklist Policy Manager")
        rules = get_sender_rules()

        col_w_list, col_b_list = st.columns(2)

        with col_w_list:
            st.markdown("**🟢 Whitelisted Senders (Always Safe)**")
            st.caption("Emails from these domains bypass spam quarantining.")
            for s in rules.get("whitelist", []):
                cw1, cw2 = st.columns([4, 1])
                cw1.write(f"- `{s}`")
                if cw2.button("❌", key=f"del_w_{s}"):
                    remove_sender_rule(s)
                    st.rerun()

            new_white = st.text_input("Add Sender / Domain to Whitelist:", placeholder="e.g. partner-domain.com", key="add_white_input")
            if st.button("➕ Add to Whitelist", key="btn_add_white"):
                if new_white.strip():
                    add_to_whitelist(new_white.strip())
                    st.success(f"Added '{new_white.strip()}' to whitelist!")
                    st.rerun()

        with col_b_list:
            st.markdown("**🔴 Blacklisted Senders (Always Quarantine)**")
            st.caption("Emails from these domains are immediately isolated.")
            for b in rules.get("blacklist", []):
                cb1, cb2 = st.columns([4, 1])
                cb1.write(f"- `{b}`")
                if cb2.button("❌", key=f"del_b_{b}"):
                    remove_sender_rule(b)
                    st.rerun()

            new_black = st.text_input("Add Sender / Domain to Blacklist:", placeholder="e.g. phish-site.ru", key="add_black_input")
            if st.button("➕ Add to Blacklist", key="btn_add_black"):
                if new_black.strip():
                    add_to_blacklist(new_black.strip())
                    st.warning(f"Added '{new_black.strip()}' to blacklist!")
                    st.rerun()


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

            # Human-in-the-Loop Feedback Controls
            with st.container(border=True):
                st.markdown("#### 🙋 Human-in-the-Loop Feedback (Active Learning)")
                st.write("Disagree with this prediction? Submit your correction to train the system.")

                fb_col1, fb_col2 = st.columns([3, 2])
                with fb_col1:
                    fb_comment = st.text_input("Correction Note (Optional):", placeholder="e.g. Legitimate vendor invoice, or subtle phishing scam", key="live_fb_comment")

                with fb_col2:
                    st.write("")
                    st.write("")
                    if is_spam:
                        if st.button("✅ Mark as False Positive (It's Ham)", type="secondary", width="stretch", key="fb_fp_btn"):
                            record_feedback(email_input, predicted_label="Spam", user_label="Ham", user_comment=fb_comment)
                            st.success("Logged as False Positive! Head to 'Active Learning & Policy Studio' tab to retrain.")
                    else:
                        if st.button("🚨 Mark as False Negative (It's Spam)", type="secondary", width="stretch", key="fb_fn_btn"):
                            record_feedback(email_input, predicted_label="Ham", user_label="Spam", user_comment=fb_comment)
                            st.warning("Logged as Missed Spam! Head to 'Active Learning & Policy Studio' tab to retrain.")


# -------------------------------------------------------------
# TAB: Live Gmail Scanner
# -------------------------------------------------------------
with tab_gmail:
    st.subheader("📬 Scan Your Real Gmail Inbox for Spam")
    st.write("Connect your Gmail account to scan, analyze, and detect spam messages directly from your inbox.")

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
    google_token = st.session_state.get("google_token")
    user_email = st.session_state.get("user_email", "")
    user_name = st.session_state.get("user_name", "")

    with st.expander("🔴 Method B: 1-Click Google Sign-In (Firebase OAuth)", expanded=bool(google_token)):
        st.markdown("""
        > **ℹ️ How Google OAuth works in SpamGuard AI:**  
        > - Standard Google Sign-In connects your account identity with 1 click.  
        > - Scanning your live Gmail inbox requires Google's `gmail.readonly` permission. If Google restricts this scope for your account, you can either add your email to **[Google Cloud Test Users](https://console.cloud.google.com/apis/credentials/consent?project=spamguard-ai-21bd8)**, or connect instantly via **Method A (App Password)** above.
        """)

        if google_token:
            st.success(f"✅ Signed in as **{user_name}** ({user_email})")
            if google_token == "signed_in":
                st.warning(
                    "⚠️ **Authentication Note:** You are authenticated with your Google profile, but live Gmail reading permission (`gmail.readonly`) was not granted or was restricted. "
                    "To scan live Gmail messages, please **Sign out** below and reconnect with *'Request Gmail scan permission'* enabled (ensuring your email is registered in Google Cloud Test Users), or connect instantly via **Method A (App Password)** above."
                )

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
                    st.session_state.pop("just_logged_in", None)
                    st.rerun()

            if st.button("🚀 Scan Gmail Inbox via Google Account", type="primary", key="oauth_scan_btn", width="stretch"):
                if google_token == "signed_in":
                    st.error("❌ Cannot scan live Gmail: No OAuth access token for Gmail reading was granted. Please use **Method A (App Password)** above or sign out and re-authenticate with Gmail permissions.")
                else:
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
                        except PermissionError as p_err:
                            st.error(f"⚠️ {p_err}")
                            if "expired" in str(p_err).lower():
                                st.session_state.pop("google_token", None)
                                st.info("ℹ️ Your Google session has expired. Please sign out and sign in again.")
                        except ValueError as v_err:
                            st.warning(f"⚠️ {v_err}")
                        except Exception as err:
                            st.error(f"Error scanning Gmail via OAuth: {err}")
        else:
            FIREBASE_AUTH_HTML = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8" />
                <style>
                    * { box-sizing: border-box; }
                    body {
                        margin: 0;
                        padding: 0;
                        background: transparent;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    }
                    .auth-card {
                        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                        padding: 20px 24px;
                        border-radius: 14px;
                        border: 1px solid #334155;
                        text-align: center;
                    }
                    .auth-title {
                        color: #f8fafc;
                        margin: 0 0 6px 0;
                        font-size: 1.15rem;
                        font-weight: 700;
                    }
                    .auth-subtitle {
                        color: #94a3b8;
                        font-size: 0.88rem;
                        margin: 0 0 14px 0;
                    }
                    .google-btn {
                        background: #ffffff;
                        color: #1e293b;
                        border: 1px solid #e2e8f0;
                        padding: 11px 22px;
                        font-size: 15px;
                        font-weight: 600;
                        border-radius: 8px;
                        cursor: pointer;
                        display: inline-flex;
                        align-items: center;
                        gap: 10px;
                        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
                        transition: all 0.2s ease;
                    }
                    .google-btn:hover {
                        background: #f8fafc;
                        box-shadow: 0 6px 18px rgba(0,0,0,0.35);
                    }
                    .google-btn:disabled {
                        opacity: 0.6;
                        cursor: not-allowed;
                    }
                </style>
            </head>
            <body>
                <div class="auth-card">
                    <h4 class="auth-title">Sign In with Google via Firebase</h4>
                    <p class="auth-subtitle">Fast authentication with Google. Zero passwords required.</p>
                    
                    <div id="domain-warning" style="display: none; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 8px; padding: 10px; margin-bottom: 14px; color: #fca5a5; font-size: 13px; text-align: left;">
                        ⚠️ <b>Domain Notice:</b> You are accessing this app via <code>127.0.0.1</code>. Firebase OAuth requires <code>localhost</code>.<br/>
                        👉 <a href="http://localhost:8501" target="_top" style="color: #38bdf8; text-decoration: underline; font-weight: 600;">Click here to open on http://localhost:8501</a> before signing in.
                    </div>

                    <div style="margin-bottom: 14px;">
                        <label style="color: #cbd5e1; font-size: 13px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;">
                            <input type="checkbox" id="request-gmail-scope" checked style="cursor: pointer;" />
                            <span>Request Gmail scan permission (<code>gmail.readonly</code>) to fetch inbox emails</span>
                        </label>
                    </div>

                    <button id="google-login-btn" class="google-btn" onclick="startGoogleLogin()">
                        <svg width="18" height="18" viewBox="0 0 18 18">
                            <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.616z"/>
                            <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
                            <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707 0-.59.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.55 0 9s.347 2.825.957 4.039l3.007-2.332z"/>
                            <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z"/>
                        </svg>
                        Sign in with Google
                    </button>
                    <div id="auth-status" style="margin-top: 14px; font-size: 13px; color: #38bdf8; min-height: 20px; line-height: 1.5; text-align: left;"></div>
                </div>

                <script type="module">
                    import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/10.9.0/firebase-app.js";
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

                    let auth = null;
                    try {
                        const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
                        auth = getAuth(app);
                    } catch (e) {
                        console.error("Firebase init error:", e);
                    }

                    // Check domain mismatch (127.0.0.1 vs localhost)
                    try {
                        let parentHost = "";
                        try {
                            parentHost = window.parent.location.hostname;
                        } catch (e1) {
                            if (document.referrer) {
                                parentHost = new URL(document.referrer).hostname;
                            }
                        }
                        if (parentHost === "127.0.0.1") {
                            const warnBox = document.getElementById('domain-warning');
                            if (warnBox) warnBox.style.display = "block";
                        }
                    } catch (e) {}

                    window.startGoogleLogin = async function() {
                        const btn = document.getElementById('google-login-btn');
                        const status = document.getElementById('auth-status');
                        const scopeCheckbox = document.getElementById('request-gmail-scope');
                        const wantGmail = scopeCheckbox ? scopeCheckbox.checked : true;

                        status.innerHTML = '<span style="color: #38bdf8;">⏳ Opening Google Sign-In popup...</span>';
                        if (btn) btn.disabled = true;

                        if (!auth) {
                            try {
                                const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
                                auth = getAuth(app);
                            } catch (e) {
                                status.innerHTML = `<div style="color: #ef4444;">Firebase connection error: ${e.message}</div>`;
                                if (btn) btn.disabled = false;
                                return;
                            }
                        }

                        try {
                            const provider = new GoogleAuthProvider();
                            if (wantGmail) {
                                provider.addScope('https://www.googleapis.com/auth/gmail.readonly');
                            }
                            provider.setCustomParameters({ prompt: 'select_account' });

                            const result = await signInWithPopup(auth, provider);
                            const credential = GoogleAuthProvider.credentialFromResult(result);
                            const token = credential ? credential.accessToken : (result._tokenResponse ? result._tokenResponse.oauthAccessToken : "");
                            const email = result.user.email;
                            const name = result.user.displayName || "";
                            status.innerHTML = `<span style="color: #22c55e;">✅ Connected as <b>${email}</b>! Syncing session...</span>`;

                            let targetUrl;
                            try {
                                targetUrl = new URL(window.parent.location.href);
                            } catch (err) {
                                targetUrl = new URL(document.referrer || window.location.href);
                            }

                            targetUrl.searchParams.set("google_token", token || "signed_in");
                            targetUrl.searchParams.set("user_email", email);
                            if (name) targetUrl.searchParams.set("user_name", name);

                            try {
                                window.parent.location.href = targetUrl.toString();
                            } catch (err) {
                                window.top.location.href = targetUrl.toString();
                            }
                        } catch (error) {
                            console.error("Firebase auth error:", error);
                            if (btn) btn.disabled = false;

                            let errHtml = `<div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 8px; padding: 12px; margin-top: 10px; color: #fecaca;">`;
                            if (error.code === 'auth/unauthorized-domain') {
                                errHtml += `<b>⚠️ Unauthorized Domain:</b> This domain is not authorized in Firebase.<br/>👉 Please open the app at <a href="http://localhost:8501" target="_top" style="color: #38bdf8; text-decoration: underline;"><b>http://localhost:8501</b></a>.`;
                            } else if (error.code === 'auth/popup-blocked') {
                                errHtml += `<b>⚠️ Popup Blocked:</b> The Google sign-in popup was blocked by your browser.<br/>👉 Please allow popups for localhost in your browser's address bar and try again.`;
                            } else if (error.code === 'auth/popup-closed-by-user') {
                                errHtml += `<b>ℹ️ Popup Closed:</b> The Google sign-in window was closed before completing authentication. Click the button to try again.`;
                            } else if (error.message && (error.message.includes("action is invalid") || error.message.includes("403") || error.message.includes("access_denied") || error.code === 'auth/internal-error')) {
                                errHtml += `<b>⚠️ Google Restricted Scope Notice:</b><br/>Google blocked <code>gmail.readonly</code> because this app is currently in test mode.<br/>`
                                         + `👉 <b>Option 1:</b> Uncheck <i>"Request Gmail scan permission"</i> above and sign in again with your Google account, OR<br/>`
                                         + `👉 <b>Option 2:</b> Use <b>Method A (App Password)</b> above which bypasses Google Cloud restrictions completely, OR<br/>`
                                         + `👉 <b>Option 3:</b> Add your email to <a href="https://console.cloud.google.com/apis/credentials/consent?project=spamguard-ai-21bd8" target="_blank" style="color: #38bdf8; text-decoration: underline;">Google Cloud Console &gt; Test Users</a>.`;
                            } else {
                                errHtml += `<b>Login Error (${error.code || 'UNKNOWN'}):</b> ${error.message}`;
                            }
                            errHtml += `</div>`;
                            status.innerHTML = errHtml;
                        }
                    };

                    const btnElem = document.getElementById('google-login-btn');
                    if (btnElem) {
                        btnElem.addEventListener('click', window.startGoogleLogin);
                    }
                </script>
            </body>
            </html>
            """
            components.html(FIREBASE_AUTH_HTML, height=290)


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
