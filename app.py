"""SpamGuard AI: check, understand, and act. No inbox content is sent to an LLM by default."""
import time
import uuid
import streamlit as st
from src.user_storage import user_scope, purge_expired_records

st.set_page_config(page_title="SpamGuard AI · Check before you trust", page_icon=":material/shield:", layout="centered")

st.markdown("""
<style>
/* Modern typography and font smoothing */
* { -webkit-font-smoothing: antialiased; }
h1 { font-size: 1.9rem !important; font-weight: 750 !important; letter-spacing: -0.03em; color: #0F172A; }
h2 { font-size: 1.4rem !important; font-weight: 650 !important; letter-spacing: -0.02em; color: #1E293B; }
h3 { font-size: 1.15rem !important; font-weight: 600 !important; color: #334155; }

/* Enhanced Form & Card containers */
[data-testid="stForm"] {
    border-radius: 14px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    background: #FFFFFF;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border-color: #E2E8F0 !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
}

/* Example chip buttons — sleek pill design */
div[data-testid="stHorizontalBlock"] > div > div > [data-testid="stBaseButton-secondary"] button {
    border-radius: 24px !important;
    font-size: 13px !important;
    font-weight: 550 !important;
    padding: 6px 16px !important;
    border-color: #E2E8F0 !important;
    color: #334155 !important;
    background: #F8FAFC !important;
    transition: all 0.15s ease-in-out !important;
}
div[data-testid="stHorizontalBlock"] > div > div > [data-testid="stBaseButton-secondary"] button:hover {
    border-color: #2563EB !important;
    color: #2563EB !important;
    background: #EFF6FF !important;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(37, 99, 235, 0.12);
}

/* Segmented control tabs styling */
[data-testid="stSegmentedControl"] {
    margin-bottom: 6px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# Reject the old credential-bearing redirect rather than consuming it as identity.
if "google_token" in st.query_params:
    st.query_params.clear()
    st.warning("The previous sign-in link is no longer supported. Reconnect securely in Settings.")

purge_expired_records()

logged_in = st.user.get("is_logged_in", False)
if logged_in and st.user.get("exp", time.time() + 1) <= time.time():
    st.logout()
    st.stop()
identity = f"{st.user.get('iss')}:{st.user.get('sub')}" if logged_in else st.session_state.setdefault("guest_id", uuid.uuid4().hex)
if st.session_state.get("identity") not in (None, identity):
    old_worker = st.session_state.get("worker")
    if old_worker:
        old_worker.stop()
    st.session_state.clear()
st.session_state["identity"] = identity
for key, default in {"language": "English", "result": None, "checked_text": "", "save_history": False, "retention_days": 7,
                     "messages": [], "selected_message": None, "actions": [], "worker": None, "gmail_disconnected": False}.items():
    st.session_state.setdefault(key, default)

with st.sidebar:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">'
        '<div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg, #2563EB, #1D4ED8);'
        'display:flex;align-items:center;justify-content:center;color:#FFFFFF;font-size:20px;font-weight:700;">🛡️</div>'
        '<div><div style="font-weight:750;font-size:17px;color:#0F172A;line-height:1.2;">SpamGuard AI</div>'
        '<div style="font-size:11px;color:#64748B;">Defense Intelligence v2.0</div></div>'
        '</div>',
        unsafe_allow_html=True
    )
    st.caption("Check before you trust. Zero external telemetry.")
    st.markdown(
        '<div style="padding:10px 12px;background:#F0FDF4;border:1px solid #BBF7D0;'
        'border-radius:8px;margin:8px 0 14px;font-size:12px;color:#15803D;display:flex;align-items:center;gap:6px;">'
        '<span>●</span><strong>Local Threat Engine Online</strong>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown("**🛡️ Protection Journey**")
    st.markdown(
        "- **1. Check:** Paste text, upload `.eml`, screenshot, or scan inbox.\n"
        "- **2. Understand:** Deep forensic evidence & deception analysis.\n"
        "- **3. Act:** Step-by-step incident containment & safety links."
    )
    st.markdown("---")
    st.selectbox("Language / भाषा", ["English", "Hindi", "Hinglish"], key="language")
    st.markdown("---")
    st.markdown(
        '<div style="padding:10px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;font-size:11.5px;color:#64748B;line-height:1.4;">'
        '🔒 <strong>Privacy Assured:</strong> All heuristics & models run strictly in this local environment. No inbox contents or uploaded images are sent to any third-party cloud AI.'
        '</div>',
        unsafe_allow_html=True
    )

navigation = st.navigation({
    "Your message": [
        st.Page("app_pages/check.py", title="Check a message", icon=":material/search:", default=True),
        st.Page("app_pages/understand.py", title="Understand the warning", icon=":material/lightbulb:", url_path="understand"),
        st.Page("app_pages/action.py", title="Take action", icon=":material/task_alt:", url_path="action")],
    "More": [
        st.Page("app_pages/advanced.py", title="Advanced", icon=":material/tune:", url_path="advanced"),
        st.Page("app_pages/settings.py", title="Settings", icon=":material/settings:", url_path="settings")]
})
with user_scope(identity):
    navigation.run()
