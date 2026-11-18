import streamlit as st
from src.ui_shared import auth_configured, gmail_token, connect_inbox, md_escape
from src.user_storage import delete_account_data, read_json, update_json
from src.gmail_actions import get_sender_rules, add_to_whitelist, add_to_blacklist, remove_sender_rule
from src.gmail_scanner import resolve_imap_settings
from src.i18n import t

st.title(t("Settings"))
st.caption(t("Your inbox connection, privacy and saved data, and trusted or blocked senders."))

st.subheader(":material/inbox: " + t("Inbox connection"), anchor=False)

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
        st.markdown(f":green[:material/check_circle:] **{t('Connected:')}** {md_escape(connected_email)}")
        st.caption(t("Provider: {provider}. We only read emails when you scan; nothing is stored.", provider=md_escape(provider_label)))
        with st.container(horizontal=True):
            if is_imap_connected and st.button(t("Test connection"), icon=":material/refresh:"):
                with st.spinner(t("Checking the connection…")):
                    diag = connect_inbox(imap_creds.get("email_address", ""), imap_creds.get("app_password", ""),
                                         imap_host=imap_creds.get("imap_host", ""), imap_port=imap_creds.get("imap_port", 993),
                                         folder=imap_creds.get("folder", "INBOX"))
                if diag["success"]:
                    st.toast(diag["message"], icon=":material/check_circle:")
                else:
                    st.error(diag["message"], icon=":material/error:")
                    if diag.get("troubleshooting"):
                        st.caption(diag["troubleshooting"])
            if st.button(t("Disconnect"), icon=":material/link_off:"):
                reset_inbox_session()
                st.session_state.pop("imap_credentials", None)
                st.session_state.gmail_disconnected = True
                if is_oauth_connected:
                    st.logout()
                st.rerun()
else:
    conn_tabs = st.tabs([":material/key: " + t("App password"), ":material/login: " + t("Sign in with Google"), ":material/science: " + t("Demo inbox")])

    with conn_tabs[0]:
        st.caption(t("Works with Gmail, Outlook, Yahoo, iCloud, Zoho and most other email services. You need an app password, not your normal password."))
        PROVIDERS = ["Detect from my email address", "Gmail", "Outlook / Office 365", "Yahoo Mail", "iCloud", "Zoho Mail", "Other (enter server)"]
        provider_labels = [t(p) for p in PROVIDERS]
        chosen_provider = st.selectbox(t("Email service"), provider_labels)
        provider_choice = PROVIDERS[provider_labels.index(chosen_provider)] if chosen_provider in provider_labels else PROVIDERS[0]
        with st.form("universal_imap_form", border=False):
            inbox_email = st.text_input(t("Email address"), placeholder="name@gmail.com")
            custom_host, custom_port = "", 993
            if provider_choice == "Other (enter server)":
                ch_col1, ch_col2 = st.columns([3, 1])
                with ch_col1:
                    custom_host = st.text_input("IMAP server", placeholder="mail.yourdomain.com")
                with ch_col2:
                    custom_port = st.number_input("Port", min_value=1, max_value=65535, value=993)
            inbox_password = st.text_input(t("App password"), type="password", placeholder=t("16 characters; spaces are fine"))
            with st.expander(t("Folder (optional)"), icon=":material/folder:"):
                folder_choice = st.text_input(t("Folder to read"), value="INBOX", help=t("For example INBOX, [Gmail]/Spam or Junk."))
            submit_imap = st.form_submit_button(t("Connect"), type="primary", width="stretch", icon=":material/link:")
        if submit_imap:
            if not inbox_email.strip() or not inbox_password.strip():
                st.warning(t("Enter your email address and app password."))
            else:
                host_to_use, port_to_use = custom_host, custom_port
                if provider_choice != "Other (enter server)":
                    host_to_use, port_to_use, _ = resolve_imap_settings(inbox_email.strip())
                with st.spinner(t("Connecting…")):
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
        with st.expander(t("How do I get an app password?"), icon=":material/help:"):
            st.markdown(
                t("An app password is a separate password just for apps like this one. You need 2-step verification turned on first.") + "\n\n"
                "- **Gmail:** [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)\n"
                "- **Outlook / Hotmail:** [account.live.com/proofs/manage/additional](https://account.live.com/proofs/manage/additional), then *App passwords*\n"
                "- **Yahoo:** [login.yahoo.com/account/security](https://login.yahoo.com/account/security), then *Generate app password*\n"
                "- **iCloud:** [appleid.apple.com](https://appleid.apple.com), *Sign-In and Security*, then *App-Specific Passwords*"
            )

    with conn_tabs[1]:
        if auth_configured():
            st.caption(t("Sign in with Google to let the app read your Gmail. You can disconnect at any time."))
            if st.button(t("Sign in with Google"), icon=":material/login:", type="primary", width="stretch"):
                st.login("google" if "google" in st.secrets["auth"] else None)
        else:
            st.caption(":material/info: " + t("Google sign-in isn't set up on this server yet. Use an app password instead, or ask the administrator."))

    with conn_tabs[2]:
        st.caption(t("Five sample emails, including two scams, so you can try scanning without connecting your own inbox."))
        if st.button(t("Open demo inbox"), type="primary", icon=":material/play_circle:", width="stretch"):
            reset_inbox_session()
            st.session_state["imap_credentials"] = {"email_address": "demo@spamguard.local", "app_password": "demo",
                                                    "provider": "SpamGuard demo inbox", "folder": "INBOX"}
            st.session_state.gmail_disconnected = False
            st.switch_page("app_pages/check.py")

st.subheader(":material/lock: " + t("Privacy and saved data"), anchor=False)
st.caption(t("Checks run on this app's server. Message text and images are not saved or sent to an outside AI service."))
st.session_state["_save_history"] = st.session_state.save_history
st.session_state["_retention_days"] = st.session_state.retention_days


def save_privacy_preferences():
    st.session_state.save_history = st.session_state._save_history
    st.session_state.retention_days = st.session_state._retention_days or st.session_state.retention_days


st.toggle(t("Keep a history of my results"), key="_save_history", on_change=save_privacy_preferences, help=t("Saves category, assessment, score and date only. Message bodies and sender details are excluded."))
st.segmented_control(t("Keep history for"), [1, 7, 30], key="_retention_days", format_func=lambda d: t("1 day") if d == 1 else t("{days} days", days=d),
                     on_change=save_privacy_preferences)
if st.session_state.save_history:
    history = read_json("history.json", [])
    if history:
        st.dataframe(history, hide_index=True, column_order=["timestamp", "assessment", "score", "category"])
    else:
        st.caption(t("No assessment summaries saved yet."))
st.caption(t("Corrections you send are deleted after 30 days. Deleting below removes everything immediately."))
confirm = st.checkbox(t("Yes, delete my saved history, corrections and sender rules, and clear this session"))
if st.button(t("Delete my saved data"), disabled=not confirm, icon=":material/delete:", type="secondary"):
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

st.subheader(":material/contacts: " + t("Trusted and blocked senders"), anchor=False)
st.caption(t("Blocked senders raise the risk score. Trusted senders are still checked: a familiar address can be faked."))
rules = get_sender_rules()
col_trust, col_block = st.columns(2)
with col_trust.container(border=True, height="stretch"):
    st.markdown(f"**:green[:material/thumb_up:] {t('Trusted')}**")
    st.markdown("\n".join(f"- {md_escape(x)}" for x in rules.get("whitelist", [])) or t("None yet"))
with col_block.container(border=True, height="stretch"):
    st.markdown(f"**:red[:material/block:] {t('Blocked')}**")
    st.markdown("\n".join(f"- {md_escape(x)}" for x in rules.get("blacklist", [])) or t("None yet"))
with st.form("sender_rule", border=False):
    with st.container(horizontal=True, vertical_alignment="bottom"):
        sender = st.text_input(t("Email address or domain"), placeholder="news@company.com, company.com")
        rule = st.segmented_control(t("Rule"), ["Trust", "Block", "Remove"], default="Trust", format_func=t)
        submitted = st.form_submit_button(t("Save"), icon=":material/save:")
if submitted:
    if not sender.strip():
        st.warning(t("Enter an email address or domain."))
    else:
        action = {"Trust": add_to_whitelist, "Block": add_to_blacklist, "Remove": remove_sender_rule}[rule or "Trust"]
        action(sender.strip())
        st.rerun()
