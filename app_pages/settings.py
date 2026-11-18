import streamlit as st
from src.ui_shared import auth_configured, gmail_token, connect_inbox, md_escape
from src.user_storage import delete_account_data, read_json, update_json
from src.gmail_actions import get_sender_rules, add_to_whitelist, add_to_blacklist, remove_sender_rule
from src.gmail_scanner import resolve_imap_settings

st.title("Settings")
st.caption("Your inbox connection, privacy and saved data, and trusted or blocked senders.")

st.subheader(":material/inbox: Inbox connection", anchor=False)

is_oauth_connected = bool(st.user.get("is_logged_in", False) and not st.session_state.get("gmail_disconnected"))
imap_creds = st.session_state.get("imap_credentials")
is_imap_connected = bool(imap_creds and imap_creds.get("email_address") and not st.session_state.get("gmail_disconnected"))


def reset_inbox_session():
    if st.session_state.worker:
        st.session_state.worker.stop()
    st.session_state.worker = None
    st.session_state.messages = []
    st.session_state.selected_message = None
    st.session_state.actions = []


if is_oauth_connected or is_imap_connected:
    connected_email = st.user.get("email") if is_oauth_connected else imap_creds.get("email_address")
    provider_label = "Gmail (Google sign-in)" if is_oauth_connected else imap_creds.get("provider", "IMAP")
    with st.container(border=True):
        st.markdown(f":green[:material/check_circle:] **Connected:** {md_escape(connected_email)}")
        st.caption(f"Provider: {md_escape(provider_label)}. We only read emails when you scan; nothing is stored.")
        with st.container(horizontal=True):
            if is_imap_connected and st.button("Test connection", icon=":material/refresh:"):
                with st.spinner("Checking the connection…"):
                    diag = connect_inbox(imap_creds.get("email_address", ""), imap_creds.get("app_password", ""),
                                         imap_host=imap_creds.get("imap_host", ""), imap_port=imap_creds.get("imap_port", 993),
                                         folder=imap_creds.get("folder", "INBOX"))
                if diag["success"]:
                    st.toast(diag["message"], icon=":material/check_circle:")
                else:
                    st.error(diag["message"], icon=":material/error:")
                    if diag.get("troubleshooting"):
                        st.caption(diag["troubleshooting"])
            if st.button("Disconnect", icon=":material/link_off:"):
                reset_inbox_session()
                st.session_state.pop("imap_credentials", None)
                st.session_state.gmail_disconnected = True
                if is_oauth_connected:
                    st.logout()
                st.rerun()
else:
    conn_tabs = st.tabs([":material/key: App password", ":material/login: Sign in with Google", ":material/science: Demo inbox"])

    with conn_tabs[0]:
        st.caption("Works with Gmail, Outlook, Yahoo, iCloud, Zoho and most other email services. You need an app password, not your normal password.")
        PROVIDERS = ["Detect from my email address", "Gmail", "Outlook / Office 365", "Yahoo Mail", "iCloud", "Zoho Mail", "Other (enter server)"]
        provider_choice = st.selectbox("Email service", PROVIDERS)
        with st.form("universal_imap_form", border=False):
            inbox_email = st.text_input("Email address", placeholder="name@gmail.com")
            custom_host, custom_port = "", 993
            if provider_choice == "Other (enter server)":
                ch_col1, ch_col2 = st.columns([3, 1])
                with ch_col1:
                    custom_host = st.text_input("IMAP server", placeholder="mail.yourdomain.com")
                with ch_col2:
                    custom_port = st.number_input("Port", min_value=1, max_value=65535, value=993)
            inbox_password = st.text_input("App password", type="password", placeholder="16 characters; spaces are fine")
            with st.expander("Folder (optional)", icon=":material/folder:"):
                folder_choice = st.text_input("Folder to read", value="INBOX", help="For example INBOX, [Gmail]/Spam or Junk.")
            submit_imap = st.form_submit_button("Connect", type="primary", width="stretch", icon=":material/link:")
        if submit_imap:
            if not inbox_email.strip() or not inbox_password.strip():
                st.warning("Enter your email address and app password.")
            else:
                host_to_use, port_to_use = custom_host, custom_port
                if provider_choice != "Other (enter server)":
                    host_to_use, port_to_use, _ = resolve_imap_settings(inbox_email.strip())
                with st.spinner("Connecting…"):
                    diag = connect_inbox(inbox_email.strip(), inbox_password.strip(), imap_host=host_to_use,
                                         imap_port=port_to_use, folder=folder_choice.strip() or "INBOX")
                if diag["success"]:
                    reset_inbox_session()
                    st.session_state["imap_credentials"] = {
                        "email_address": inbox_email.strip(), "app_password": inbox_password.strip(), "provider": diag["provider"],
                        "imap_host": diag["host"], "imap_port": diag["port"], "folder": folder_choice.strip() or "INBOX"}
                    st.session_state.gmail_disconnected = False
                    st.rerun()
                else:
                    st.error(diag["message"], icon=":material/error:")
                    if diag.get("troubleshooting"):
                        st.caption(diag["troubleshooting"])
        with st.expander("How do I get an app password?", icon=":material/help:"):
            st.markdown(
                "An app password is a separate password just for apps like this one. You need 2-step verification turned on first.\n\n"
                "- **Gmail:** [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)\n"
                "- **Outlook / Hotmail:** [account.live.com/proofs/manage/additional](https://account.live.com/proofs/manage/additional), then *App passwords*\n"
                "- **Yahoo:** [login.yahoo.com/account/security](https://login.yahoo.com/account/security), then *Generate app password*\n"
                "- **iCloud:** [appleid.apple.com](https://appleid.apple.com), *Sign-In and Security*, then *App-Specific Passwords*"
            )

    with conn_tabs[1]:
        if auth_configured():
            st.caption("Sign in with Google to let the app read your Gmail. You can disconnect at any time.")
            if st.button("Sign in with Google", icon=":material/login:", type="primary", width="stretch"):
                st.login("google" if "google" in st.secrets["auth"] else None)
        else:
            st.caption(":material/info: Google sign-in isn't set up on this server yet. Use an app password instead, or ask the administrator. "
                       "Setup steps are in docs/DEPLOYMENT.md.")

    with conn_tabs[2]:
        st.caption("Five sample emails, including two scams, so you can try scanning without connecting your own inbox.")
        if st.button("Open demo inbox", type="primary", icon=":material/play_circle:", width="stretch"):
            reset_inbox_session()
            st.session_state["imap_credentials"] = {"email_address": "demo@spamguard.local", "app_password": "demo",
                                                    "provider": "SpamGuard demo inbox", "folder": "INBOX"}
            st.session_state.gmail_disconnected = False
            st.switch_page("app_pages/check.py")

st.subheader(":material/lock: Privacy and saved data", anchor=False)
st.caption("Checks run on this app's server. Message text and images are not saved or sent to an outside AI service.")
st.session_state["_save_history"] = st.session_state.save_history
st.session_state["_retention_days"] = st.session_state.retention_days


def save_privacy_preferences():
    st.session_state.save_history = st.session_state._save_history
    st.session_state.retention_days = st.session_state._retention_days


st.toggle("Keep a history of my results", key="_save_history", on_change=save_privacy_preferences, help="Saves category, assessment, score and date only. Message bodies and sender details are excluded.")
st.selectbox("Keep history for", [1, 7, 30], key="_retention_days", format_func=lambda d: f"{d} day" + ("s" if d > 1 else ""), on_change=save_privacy_preferences)
if st.session_state.save_history:
    history = read_json("history.json", [])
    if history:
        st.dataframe(history, hide_index=True, column_order=["timestamp", "assessment", "score", "category"])
    else:
        st.caption("No assessment summaries saved yet.")
st.caption("Corrections you send are deleted after 30 days. Deleting below removes everything immediately.")
confirm = st.checkbox("Yes, delete my saved history, corrections and sender rules, and clear this session")
if st.button("Delete my saved data", disabled=not confirm, icon=":material/delete:", type="secondary"):
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

st.subheader(":material/contacts: Trusted and blocked senders", anchor=False)
st.caption("Blocked senders raise the risk score. Trusted senders are still checked: a familiar address can be faked.")
rules = get_sender_rules()
col_trust, col_block = st.columns(2)
with col_trust.container(border=True, height="stretch"):
    st.markdown("**:green[:material/thumb_up:] Trusted**")
    st.markdown("\n".join(f"- {md_escape(x)}" for x in rules.get("whitelist", [])) or "None yet")
with col_block.container(border=True, height="stretch"):
    st.markdown("**:red[:material/block:] Blocked**")
    st.markdown("\n".join(f"- {md_escape(x)}" for x in rules.get("blacklist", [])) or "None yet")
with st.form("sender_rule", border=False):
    with st.container(horizontal=True, vertical_alignment="bottom"):
        sender = st.text_input("Email address or domain", placeholder="news@company.com or company.com")
        rule = st.segmented_control("Rule", ["Trust", "Block", "Remove"], default="Trust")
        submitted = st.form_submit_button("Save", icon=":material/save:")
if submitted:
    if not sender.strip():
        st.warning("Enter an email address or domain.")
    else:
        action = {"Trust": add_to_whitelist, "Block": add_to_blacklist, "Remove": remove_sender_rule}[rule or "Trust"]
        action(sender.strip())
        st.rerun()
