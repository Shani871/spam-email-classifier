import streamlit as st
from src.ui_shared import auth_configured, gmail_token
from src.user_storage import delete_account_data, read_json, update_json
from src.gmail_actions import get_sender_rules, add_to_whitelist, add_to_blacklist, remove_sender_rule
from src.gmail_scanner import verify_inbox_connection, resolve_imap_settings

st.title("Settings")
st.caption("Control your inbox connection, security preferences, and saved information.")

st.subheader("Account and inbox")

is_oauth_connected = bool(st.user.get("is_logged_in", False) and not st.session_state.get("gmail_disconnected"))
imap_creds = st.session_state.get("imap_credentials")
is_imap_connected = bool(imap_creds and imap_creds.get("email_address") and not st.session_state.get("gmail_disconnected"))

if is_oauth_connected or is_imap_connected:
    connected_email = st.user.get("email") if is_oauth_connected else imap_creds.get("email_address")
    provider_label = "Google Workspace / Gmail (OAuth)" if is_oauth_connected else imap_creds.get("provider", "IMAP Mailbox")

    st.markdown(
        f'<div style="padding:14px 18px;background:#F0FDF4;border:1px solid #BBF7D0;'
        f'border-radius:10px;margin-bottom:14px;">'
        f'<div style="font-weight:700;color:#15803D;font-size:15px;margin-bottom:4px;">● Connected to Inbox</div>'
        f'<div style="font-size:13px;color:#1F2937;"><strong>Account:</strong> {connected_email} &nbsp;|&nbsp; <strong>Provider:</strong> {provider_label}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        if is_imap_connected and st.button("Test Connection Now", icon=":material/refresh:", width="stretch"):
            with st.spinner("Checking connection with mail server…"):
                diag = verify_inbox_connection(
                    imap_creds.get("email_address", ""),
                    imap_creds.get("app_password", ""),
                    imap_host=imap_creds.get("imap_host", ""),
                    imap_port=imap_creds.get("imap_port", 993),
                    folder=imap_creds.get("folder", "INBOX")
                )
            if diag["success"]:
                st.success(diag["message"])
            else:
                st.error(diag["message"])
                if diag.get("troubleshooting"):
                    st.info(diag["troubleshooting"])
    with btn_col2:
        if st.button("Disconnect inbox", icon=":material/link_off:", width="stretch"):
            if st.session_state.worker:
                st.session_state.worker.stop()
            st.session_state.worker = None
            st.session_state.pop("imap_credentials", None)
            st.session_state.gmail_disconnected = True
            st.session_state.messages = []
            st.session_state.selected_message = None
            st.session_state.actions = []
            if is_oauth_connected:
                st.logout()
            st.rerun()

else:
    # Not connected — present tabs for connection methods
    conn_tabs = st.tabs(["Universal IMAP (Gmail, Outlook, Yahoo…)", "Instant Demo Mailbox", "Google Sign-in (OAuth)"])

    with conn_tabs[0]:
        st.caption("Connect securely using a 16-character App Password. Works with Gmail, Outlook, Yahoo, iCloud, and any standard IMAP server.")
        with st.form("universal_imap_form"):
            inbox_email = st.text_input("Email address", placeholder="e.g. name@gmail.com, user@outlook.com, me@yahoo.com")
            
            provider_choice = st.selectbox(
                "Mail provider",
                [
                    "Auto-detect from email domain",
                    "Google Gmail",
                    "Microsoft Outlook / Office 365",
                    "Yahoo Mail",
                    "Apple iCloud",
                    "Zoho Mail",
                    "Custom IMAP Server"
                ]
            )
            
            custom_host, custom_port = "", 993
            if provider_choice == "Custom IMAP Server":
                ch_col1, ch_col2 = st.columns([3, 1])
                with ch_col1:
                    custom_host = st.text_input("IMAP Host", placeholder="mail.yourdomain.com")
                with ch_col2:
                    custom_port = st.number_input("IMAP Port", min_value=1, max_value=65535, value=993)

            inbox_password = st.text_input(
                "App Password",
                type="password",
                placeholder="Paste generated 16-character App Password (spaces will be auto-formatted)"
            )
            folder_choice = st.text_input("Mailbox Folder", value="INBOX", help="Default is INBOX. You can also specify [Gmail]/Spam or Junk.")
            
            submit_imap = st.form_submit_button("Test & Connect Inbox", type="primary", width="stretch")

        if submit_imap:
            if not inbox_email.strip() or not inbox_password.strip():
                st.warning("Please provide both your email address and App Password.")
            else:
                host_to_use = custom_host
                port_to_use = custom_port
                if provider_choice != "Custom IMAP Server":
                    host_to_use, port_to_use, _ = resolve_imap_settings(inbox_email.strip())
                
                with st.spinner("Connecting and validating credentials…"):
                    diag = verify_inbox_connection(
                        inbox_email.strip(),
                        inbox_password.strip(),
                        imap_host=host_to_use,
                        imap_port=port_to_use,
                        folder=folder_choice.strip() or "INBOX"
                    )

                if diag["success"]:
                    if st.session_state.worker:
                        st.session_state.worker.stop()
                        st.session_state.worker = None
                    st.session_state["imap_credentials"] = {
                        "email_address": inbox_email.strip(),
                        "app_password": inbox_password.strip(),
                        "provider": diag["provider"],
                        "imap_host": diag["host"],
                        "imap_port": diag["port"],
                        "folder": folder_choice.strip() or "INBOX"
                    }
                    st.session_state.gmail_disconnected = False
                    st.session_state.messages = []
                    st.session_state.selected_message = None
                    st.session_state.actions = []
                    st.success(diag["message"])
                    st.rerun()
                else:
                    st.error(diag["message"])
                    if diag.get("troubleshooting"):
                        st.info(diag["troubleshooting"])

        with st.expander("📖 How to generate an App Password in 60 seconds"):
            st.markdown(
                "Modern email providers require an **App Password** instead of your main account password for third-party security:\n\n"
                "- **Google Gmail**: Enable 2-Step Verification at [myaccount.google.com/security](https://myaccount.google.com/security), then visit [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) to generate a 16-character password.\n"
                "- **Microsoft Outlook / Hotmail**: Visit [account.live.com/proofs/manage/additional](https://account.live.com/proofs/manage/additional) and create a new App password under 'Security'.\n"
                "- **Yahoo Mail**: Go to [login.yahoo.com/account/security](https://login.yahoo.com/account/security) and click 'Generate app password'.\n"
                "- **Apple iCloud**: Visit [appleid.apple.com](https://appleid.apple.com) under 'Sign-In and Security' -> 'App-Specific Passwords'."
            )

    with conn_tabs[1]:
        st.markdown("#### Test Live Inbox Scanning Instantly")
        st.caption("Don't have an App Password ready? Connect our pre-loaded demo mailbox with 5 realistic security scenarios including credential phishing, job scams, utility fraud, and legitimate business communications.")
        if st.button("Connect SpamGuard Demo Mailbox", type="primary", icon=":material/play_circle:", width="stretch"):
            if st.session_state.worker:
                st.session_state.worker.stop()
                st.session_state.worker = None
            st.session_state["imap_credentials"] = {
                "email_address": "demo@spamguard.local",
                "app_password": "demo",
                "provider": "SpamGuard Demo Feed",
                "folder": "INBOX"
            }
            st.session_state.gmail_disconnected = False
            st.session_state.messages = []
            st.session_state.selected_message = None
            st.session_state.actions = []
            st.success("Connected to SpamGuard Demo Mailbox! Head over to 'Check a message' to scan recent emails.")
            st.rerun()

    with conn_tabs[2]:
        if auth_configured():
            st.caption("Google sign-in requests permission to read your inbox through a secure OAuth 2.0 callback.")
            if st.button("Connect with Google OAuth", icon=":material/login:", type="primary", width="stretch"):
                st.login("google" if "google" in st.secrets["auth"] else None)
        else:
            st.info(
                "Google OAuth requires an authorized Google Cloud Client ID & Secret configured in `.streamlit/secrets.toml`.\n\n"
                "To configure OAuth:\n"
                "1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`\n"
                "2. Add your Google OAuth `client_id` and `client_secret`\n"
                "3. Enable the Gmail API in Google Cloud Console.\n\n"
                "**Tip:** You can connect immediately without Google Cloud setup using the **Universal IMAP** tab!"
            )

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
