"""SpamGuard AI: check, understand, and act. No inbox content is sent to an LLM by default."""
import time
import uuid
import streamlit as st
from src.user_storage import user_scope, purge_expired_records
from src.i18n import t

st.set_page_config(page_title="SpamGuard AI · Check before you trust", page_icon=":material/shield:", layout="centered",
                   initial_sidebar_state="auto")

st.logo("assets/logo.svg", icon_image="assets/icon.svg", size="large")

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
    # The choice is mirrored into "language" so it survives page changes (widget state alone does not).
    st.session_state["_language_choice"] = st.session_state.language
    st.selectbox("Language / भाषा", ["English", "Hindi", "Hinglish"], key="_language_choice",
                 on_change=lambda: st.session_state.update(language=st.session_state._language_choice))
    st.caption(":material/lock: " + t("Messages are checked on this server. Nothing is sent to an outside AI service, and nothing is saved unless you turn it on in Settings."))

navigation = st.navigation({
    t("Check a message"): [
        st.Page("app_pages/check.py", title=t("Check"), icon=":material/search:", default=True,
                help=t("Paste a message, upload an email or screenshot, or scan your inbox.")),
        st.Page("app_pages/understand.py", title=t("Result"), icon=":material/fact_check:", url_path="understand",
                help=t("The verdict for the last message you checked, and the evidence behind it.")),
        st.Page("app_pages/action.py", title=t("What to do"), icon=":material/task_alt:", url_path="action",
                help=t("Steps to take for your situation, where to report, and how to correct a wrong result."))],
    t("More"): [
        st.Page("app_pages/settings.py", title=t("Settings"), icon=":material/settings:", url_path="settings",
                help=t("Connect your inbox, privacy and saved data, and trusted or blocked senders.")),
        st.Page("app_pages/advanced.py", title=t("Advanced"), icon=":material/tune:", url_path="advanced",
                help=t("Model results, benchmark, batch CSV checks, feedback review and inbox monitor."))]
})
with user_scope(identity):
    navigation.run()
