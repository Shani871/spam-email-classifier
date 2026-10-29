import streamlit as st
from src.ui_shared import auth_configured, gmail_token
from src.user_storage import delete_account_data, read_json, update_json
from src.gmail_actions import get_sender_rules, add_to_whitelist, add_to_blacklist, remove_sender_rule

st.title("Settings")
st.caption("Control your connection, privacy, and saved information.")
st.subheader("Account and inbox")
if st.user.get("is_logged_in", False):
    st.text(f"Signed in as {st.user.get('email', 'your Google account')}")
    st.caption("Gmail authorization may expire before your sign-in session. Reconnect if a scan fails.")
    if st.button("Sign out", icon=":material/logout:"):
        if st.session_state.worker:
            st.session_state.worker.stop()
        st.session_state.clear()
        st.logout()
elif auth_configured():
    st.caption("Google sign-in requests permission to read your inbox through a secure callback.")
    if st.button("Connect with Google", icon=":material/login:", type="primary"):
        st.login("google" if "google" in st.secrets["auth"] else None)
else:
    st.info("Live Gmail verification requires an explicitly authorized Google test account with configured credentials. Live verification status: PENDING CREDENTIAL CONFIGURATION. You can still check pasted text, emails, and images privately without connecting an inbox.")

try:
    actions_configured = "googleactions" in st.secrets.get("auth", {})
except FileNotFoundError:
    actions_configured = False
if actions_configured:
    st.caption("Optional inbox actions require broader Gmail permission. Checking pasted messages does not require it.")
    if st.button("Connect Google with inbox action permission"):
        st.session_state.gmail_disconnected = False
        st.login("googleactions")

with st.expander("Alternative: Gmail app password"):
    st.caption("Credentials stay in this session's memory. This connection supports checking only; no automatic email moves.")
    with st.form("imap_connection"):
        email = st.text_input("Gmail address")
        password = st.text_input("Gmail app password", type="password")
        submit = st.form_submit_button("Use this inbox")
    if submit:
        if not email.strip() or not password.strip():
            st.warning("Enter both the Gmail address and app password.")
        else:
            if st.session_state.worker:
                st.session_state.worker.stop()
                st.session_state.worker = None
            st.session_state["imap_credentials"] = {"email_address": email.strip(), "app_password": password.strip()}
            st.session_state.messages = []
            st.session_state.selected_message = None
            st.session_state.actions = []
            st.success("Connection details saved for this session. Scan the inbox to verify access.")
if gmail_token() or st.session_state.get("imap_credentials"):
    if st.button("Disconnect inbox", icon=":material/link_off:"):
        if st.session_state.worker:
            st.session_state.worker.stop()
        st.session_state.worker = None
        st.session_state.pop("imap_credentials", None)
        st.session_state.gmail_disconnected = True
        st.session_state.messages = []
        st.session_state.selected_message = None
        st.session_state.actions = []
        st.rerun()
if st.user.get("is_logged_in", False) and st.session_state.gmail_disconnected:
    if st.button("Reconnect Google inbox"):
        st.session_state.gmail_disconnected = False
        st.login("google" if "google" in st.secrets["auth"] else None)

st.subheader("Privacy")
st.caption("Checks run on this app's server, not entirely on your device. Uploaded images and message text are not saved by default or sent to an external AI service.")
st.session_state["_save_history"] = st.session_state.save_history
st.session_state["_retention_days"] = st.session_state.retention_days

def save_privacy_preferences():
    st.session_state.save_history = st.session_state._save_history
    st.session_state.retention_days = st.session_state._retention_days

st.toggle("Save assessment summaries", key="_save_history", on_change=save_privacy_preferences, help="Saves category, assessment, score and date only. Message bodies and sender details are excluded.")
st.selectbox("Summary retention (days)", [1, 7, 30], key="_retention_days", on_change=save_privacy_preferences)
if st.session_state.save_history:
    history = read_json("history.json", [])
    if history:
        st.dataframe(history, hide_index=True, column_order=["timestamp", "assessment", "score", "category"])
    else:
        st.caption("No assessment summaries saved yet.")
st.caption("Saved corrections expire after 30 days. Retention changes apply to new summaries; use deletion below to remove existing records immediately. Guest records are tied to this browser session and cannot be recovered after it ends.")
confirm = st.checkbox("Delete saved rules, corrections, and summaries, and clear this session")
if st.button("Delete my saved data", disabled=not confirm, icon=":material/delete:"):
    if st.session_state.worker:
        st.session_state.worker.stop()
    delete_account_data()
    identity = st.session_state.identity
    guest = st.session_state.get("guest_id")
    st.session_state.clear()
    st.session_state.identity = identity
    if guest:
        st.session_state.guest_id = guest
    st.session_state.gmail_disconnected = True
    st.rerun()

with st.expander("Sender rules"):
    st.caption("Trusted senders still receive threat checks. A trusted address does not prove the message is authentic.")
    rules = get_sender_rules()
    st.json(rules)
    with st.form("sender_rule"):
        sender = st.text_input("Sender email or domain")
        rule = st.selectbox("Rule", ["Trust", "Block", "Remove"])
        submitted = st.form_submit_button("Save rule")
    if submitted:
        action = {"Trust": add_to_whitelist, "Block": add_to_blacklist, "Remove": remove_sender_rule}[rule]
        action(sender)
        st.rerun()
