"""SpamGuard AI: check, understand, and act. No inbox content is sent to an LLM by default."""
import time
import uuid
import streamlit as st
from src.user_storage import user_scope, purge_expired_records

st.set_page_config(page_title="SpamGuard AI · Check before you trust", page_icon=":material/shield:", layout="centered")

st.markdown("""
<style>
/* Tighter, more modern page header */
h1 { font-size: 2rem !important; font-weight: 700 !important; letter-spacing: -0.02em; }
/* Softer form container */
[data-testid="stForm"] { border-radius: 12px !important; }
/* Example chip buttons — pill shaped, lighter weight */
div[data-testid="stHorizontalBlock"] > div > div > [data-testid="stBaseButton-secondary"] button {
    border-radius: 20px !important;
    font-size: 13px !important;
    padding: 6px 14px !important;
    border-color: #CBD5E1 !important;
    color: #374151 !important;
    background: #F8FAFC !important;
}
div[data-testid="stHorizontalBlock"] > div > div > [data-testid="stBaseButton-secondary"] button:hover {
    border-color: #2563EB !important;
    color: #2563EB !important;
    background: #EFF6FF !important;
}
/* Segmented control tabs — slightly more prominent */
[data-testid="stSegmentedControl"] { margin-bottom: 2px; }
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
    st.markdown("### :material/shield: SpamGuard AI")
    st.caption("Check before you trust.")
    st.markdown("---")
    st.markdown("**How it works**")
    st.markdown(
        "**1. Paste or upload** any suspicious message — email, SMS, job offer, or payment request.\n\n"
        "**2. We check** for scam patterns, fake links, urgency pressure, and impersonated brands.\n\n"
        "**3. You get** step-by-step recovery guidance and report links if needed."
    )
    st.markdown("---")
    st.selectbox("Explanation language", ["English", "Hindi", "Hinglish"], key="language")
    st.markdown("---")
    st.caption("🔒 **Privacy:** All checks run on this server only. Nothing is sent to any external AI service unless you choose it.")

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
