import hashlib
import streamlit as st
from src.ui_shared import analyze, step_tracker, md_escape
from src.i18n import t

step_tracker(1)
st.title(t("Is this message safe?"))
st.caption(t("Check an email, text, job offer or payment request before you click, reply or pay."))

# Internal values stay in English; only the labels are translated.
SOURCES = {
    "Paste text": (":material/content_paste:", "Paste text"),
    "Email file": (":material/mail:", "Email file"),
    "Screenshot or QR": (":material/photo_camera:", "Screenshot or QR"),
    "Connected inbox": (":material/inbox:", "My inbox"),
}
source = st.segmented_control(t("Where is the message?"), list(SOURCES), default="Paste text", key="source",
                              format_func=lambda key: f"{SOURCES[key][0]} {t(SOURCES[key][1])}",
                              label_visibility="collapsed", width="stretch") or "Paste text"

CATEGORIES = {"General message": "General", "Job or internship": "Job or internship", "Invoice or payment": "Invoice or payment"}

# Inbox list badges: what the app concluded, in a few words.
INBOX_BADGES = {
    "High risk": ("red", ":material/gpp_bad:", "Likely scam"),
    "Needs verification": ("orange", ":material/help:", "Check first"),
    "No strong warning found": ("green", ":material/verified_user:", "Looks normal"),
    "Unable to assess": ("gray", ":material/info:", "Not sure"),
}


def inbox_badge(assessment):
    color, icon, label = INBOX_BADGES[assessment]
    return f":{color}-badge[{icon} {t(label)}]"


def category_picker(key):
    choice = st.segmented_control(t("What is it about?"), list(CATEGORIES), default="General message", key=key,
                                  format_func=lambda c: t(CATEGORIES[c]),
                                  help=t("Job and payment messages get extra checks for common scams."))
    return choice or "General message"


def open_result():
    st.session_state["selected_message"] = None
    st.switch_page("app_pages/understand.py")


if source == "Email file":
    from src.eml_reader import parse_email_file
    uploaded_email = st.file_uploader(t("Upload an email saved as .eml"), type=["eml"], max_upload_size=10, key="email_file",
                                      help=t("In Gmail: open the message, ⋮ menu, Download message. In Outlook: File, Save as."))
    st.caption(t("Links are not opened and attachments are not run. Sender headers in a file are treated as claims, not proof."))
    if uploaded_email:
        try:
            parsed = parse_email_file(uploaded_email.getvalue())
            with st.container(border=True):
                st.markdown(f"**{md_escape(parsed['subject']) or t('(No subject)')}**")
                st.caption(t("From {sender}", sender=md_escape(parsed["sender"]) or t("an unknown sender")))
                for warning in parsed["warnings"]:
                    st.warning(warning, icon=":material/warning:")
                with st.expander(t("Read the message text"), icon=":material/article:"):
                    st.text(parsed["display_body"] or t("No readable message body."))
                if parsed["attachments"]:
                    st.caption(":material/attach_file: " + t("{count} attachment(s). Names and types are checked; contents are not scanned.",
                                                              count=len(parsed["attachments"])))
            with st.form("email_file_check", border=False):
                category = category_picker("eml_category")
                with st.expander(t("More options"), icon=":material/tune:"):
                    domain = st.text_input(t("Official website of the employer or supplier"), placeholder="company.com")
                    previous = st.text_area(t("Earlier message in the same conversation"), max_chars=50000, key="eml_prev_text",
                                            help=t("We compare payment details, sender and links between the two."))
                    previous_sender = st.text_input(t("Earlier sender address"), key="eml_prev_sender")
                    previous_reply_to = st.text_input(t("Earlier reply-to address"), key="eml_prev_reply_to")
                submitted = st.form_submit_button(t("Check this email"), type="primary", icon=":material/search:", width="stretch")
            if submitted:
                with st.spinner(t("Checking the text, links and sender…")):
                    result = analyze(parsed["full_text"], category=category, sender=parsed["sender"], company_domain=domain,
                                     previous_text=previous, previous_sender=previous_sender, previous_reply_to=previous_reply_to,
                                     headers=parsed["headers"], attachments=parsed["attachments"])
                result["limitations"].extend(parsed["warnings"])
                open_result()
        except ValueError as error:
            st.error(str(error), icon=":material/error:")
        except FileNotFoundError:
            st.error(t("The checker is not set up yet. See Advanced for setup instructions."), icon=":material/error:")

elif source == "Connected inbox":
    from src.ui_shared import gmail_token, connect_inbox
    from src.rate_limit import enforce
    from src.gmail_api import scan_gmail_with_oauth
    from src.gmail_scanner import scan_gmail_inbox
    token = gmail_token()
    credentials = st.session_state.get("imap_credentials", {})
    if not token and not credentials:
        st.caption(t("Scan your recent emails without copying anything. We only read them; nothing is moved or deleted."))
        col_connect, col_demo = st.columns(2)
        with col_connect.container(border=True, height="stretch"):
            st.markdown(f"**:material/link: {t('Connect your email')}**")
            with st.form("quick_inbox_connect", border=False):
                quick_email = st.text_input(t("Email address"), placeholder="name@gmail.com")
                quick_pwd = st.text_input(t("App password"), type="password", placeholder=t("16-character app password"),
                                          help=t("Not your normal password. Create one in your email account's security settings; Settings explains how."))
                quick_submit = st.form_submit_button(t("Connect"), type="primary", width="stretch", icon=":material/login:")
            if quick_submit:
                if not quick_email.strip() or not quick_pwd.strip():
                    st.warning(t("Enter your email address and app password."))
                else:
                    with st.spinner(t("Connecting…")):
                        res = connect_inbox(quick_email.strip(), quick_pwd.strip())
                    if res["success"]:
                        st.session_state["imap_credentials"] = {"email_address": quick_email.strip(), "app_password": quick_pwd.strip(),
                                                                "provider": res["provider"]}
                        st.session_state["inbox_provider_name"] = res["provider"]
                        st.session_state.messages = []
                        st.rerun()
                    else:
                        st.error(res["message"], icon=":material/error:")
                        if res.get("troubleshooting"):
                            st.caption(res["troubleshooting"])
            st.page_link("app_pages/settings.py", label=t("Other ways to connect"), icon=":material/settings:")
        with col_demo.container(border=True, height="stretch"):
            st.markdown(f"**:material/science: {t('Try the demo inbox')}**")
            st.caption(t("Five sample emails, including two scams, so you can see how it works first."))
            if st.button(t("Open demo inbox"), icon=":material/play_circle:", width="stretch"):
                st.session_state["imap_credentials"] = {"email_address": "demo@spamguard.local", "app_password": "demo",
                                                        "provider": "SpamGuard demo inbox"}
                st.session_state["inbox_provider_name"] = "SpamGuard demo inbox"
                st.session_state.messages = []
                st.rerun()
    else:
        connected_email = credentials.get("email_address") or (st.user.get("email") if token else "your inbox")
        provider_name = credentials.get("provider") or st.session_state.get("inbox_provider_name") or ("Gmail" if token else "IMAP")
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(t("Connected: {email} ({provider})", email=md_escape(connected_email), provider=md_escape(provider_name)),
                     icon=":material/check_circle:", color="green")
            st.page_link("app_pages/settings.py", label=t("Change"), icon=":material/settings:")
        with st.form("inbox_scan", border=True):
            col_count, col_folder = st.columns(2)
            with col_count:
                count = st.select_slider(t("How many recent emails"), [5, 10, 15, 20, 25], value=10)
            with col_folder:
                folders = {t("Inbox"): "INBOX", t("Gmail spam"): "[Gmail]/Spam", "Spam": "Spam", "Junk": "Junk"}
                folder = folders.get(st.selectbox(t("Folder"), list(folders), index=0), "INBOX")
            unread = st.toggle(t("Only unread"), value=False)
            submitted = st.form_submit_button(t("Scan emails"), type="primary", width="stretch", icon=":material/search:")
        if submitted:
            try:
                enforce("inbox_scan", st.session_state.get("identity", ""))
                with st.spinner(t("Reading and checking your emails…")):
                    if token:
                        messages = scan_gmail_with_oauth(token, count, unread, "svm")
                    else:
                        messages = scan_gmail_inbox(email_address=credentials["email_address"], app_password=credentials["app_password"],
                                                    folder=folder, max_emails=count, only_unread=unread, model_type="svm",
                                                    imap_host=credentials.get("imap_host", ""), imap_port=credentials.get("imap_port", 993))
                st.session_state["messages"] = messages
                if not messages:
                    st.info(t("No emails matched this scan."), icon=":material/inbox:")
            except Exception as err:
                st.session_state["messages"] = []
                st.error(t("The scan didn't work: {error}", error=err), icon=":material/error:")
                st.caption(t("Try reconnecting in Settings, or check that your app password is still valid."))
        messages = st.session_state.get("messages", [])
        if messages:
            from src.scam_assistant import inbox_triage
            for m in messages:
                if "assessment" not in m:
                    m["assessment"] = inbox_triage(m)
            counts = {k: sum(m["assessment"] == k for m in messages) for k in INBOX_BADGES}
            attention = counts["High risk"] + counts["Needs verification"]
            st.subheader(t("{count} emails checked", count=len(messages)), anchor=False)
            st.markdown("  ".join(f"{inbox_badge(k)} {counts[k]}" for k in INBOX_BADGES if counts[k]))
            show = st.segmented_control(t("Show"), ["All", "Needs attention"], default="All", key="inbox_filter",
                                        format_func=t, label_visibility="collapsed") or "All"
            if show == "Needs attention" and not attention:
                st.success(t("Nothing here needs attention."), icon=":material/verified_user:")
            for index, message in enumerate(messages):
                if show == "Needs attention" and message["assessment"] not in {"High risk", "Needs verification"}:
                    continue
                with st.container(border=True, horizontal=True, vertical_alignment="center", gap="small"):
                    with st.container(gap="xsmall"):
                        st.markdown(f"{inbox_badge(message['assessment'])} **{md_escape(message['subject']) or t('(No subject)')}**")
                        st.caption(f"{md_escape(message['sender'])} · {md_escape(message.get('date', ''))[:31]}")
                    if st.button(t("Details"), key=f"inbox_open_{index}", icon=":material/arrow_forward:", width="content"):
                        try:
                            with st.spinner(t("Checking this email in detail…")):
                                analyze(message["full_text"], sender=message["sender"], headers=message.get("headers"),
                                        attachments=message.get("attachments"),
                                        sender_verified=bool((message.get("sender_verification") or {}).get("verified")))
                            st.session_state["selected_message"] = dict(message)
                            st.switch_page("app_pages/understand.py")
                        except (FileNotFoundError, ValueError) as error:
                            st.error(t("The check could not be completed: {error}", error=error), icon=":material/error:")

else:
    st.session_state.setdefault("message_input", st.session_state.get("draft_text", ""))
    if source == "Screenshot or QR":
        from src.image_checks import extract_image_content
        uploaded = st.file_uploader(t("Upload a screenshot or a photo of a QR code"), type=["png", "jpg", "jpeg", "webp"], max_upload_size=10)
        st.caption(t("Text is read on this server. QR links are shown, never opened. Check the text below before you continue."))
        if uploaded:
            data = uploaded.getvalue()
            digest = hashlib.sha256(data).hexdigest()
            with st.expander(t("Your image"), icon=":material/image:"):
                st.image(data, width="stretch")
            if st.session_state.get("image_digest") != digest:
                try:
                    with st.spinner(t("Reading the image…")):
                        extracted = extract_image_content(data, "eng+hin" if st.session_state.language == "Hindi" else "eng")
                    st.session_state["image_digest"] = digest
                    st.session_state["image_extraction"] = extracted
                    st.session_state["message_input"] = extracted["text"] + "\n" + "\n".join(extracted["qr_destinations"])
                except ValueError as error:
                    st.error(str(error), icon=":material/error:")
            extracted = st.session_state.get("image_extraction", {})
            for warning in extracted.get("warnings", []):
                st.warning(warning, icon=":material/warning:")
            for destination in extracted.get("qr_destinations", []):
                st.caption(t("The QR code points to (not opened):"))
                st.code(destination, language=None)
    else:
        EXAMPLES = {
            "Job scam": (":material/work:", "You are selected for a remote internship. Pay a registration fee of ₹2,000 to confirm your job. Send your Aadhaar and bank details immediately."),
            "Fake payment": (":material/payments:", "Your UPI payment of ₹9,999 is pending. Click here immediately to confirm your bank account: http://paypa1-verify.xyz"),
            "OTP request": (":material/password:", "Dear customer, your account will be suspended. Share OTP 847291 with our agent on 8800123456 to verify your identity."),
        }

        def use_example():
            choice = st.session_state.get("example_choice")
            if choice:
                st.session_state["message_input"] = EXAMPLES[choice][1]
                st.session_state["example_choice"] = None

        st.pills(t("No message handy? Try an example"), list(EXAMPLES), key="example_choice", on_change=use_example,
                 format_func=lambda key: f"{EXAMPLES[key][0]} {t(key)}")

    with st.form("message_check", border=True):
        text = st.text_area(t("Message"), height=200, key="message_input", max_chars=50000,
                            placeholder=t("Paste the whole message here, including any links. Remove anything private you don't want to share."))
        category = category_picker("message_category")
        with st.expander(t("More options: sender, earlier message, attachment"), icon=":material/tune:"):
            sender = st.text_input(t("Sender's email address"), placeholder="sender@example.com", key="current_sender_input")
            domain = st.text_input(t("Official website of the employer or supplier"), placeholder="company.com",
                                   help=t("We warn if the sender or links don't match it."))
            st.markdown(f"**:material/compare_arrows: {t('Compare with an earlier message')}**")
            st.caption(t("Useful for invoices and ongoing conversations: we look for changed bank details, senders, links or new requests."))
            previous = st.text_area(t("Earlier message"), height=100, max_chars=50000, key="previous_message_input",
                                    placeholder=t("Paste an earlier message from the same conversation"))
            prev_col1, prev_col2 = st.columns(2)
            with prev_col1:
                previous_sender = st.text_input(t("Earlier sender address"), placeholder="alice@supplier.com", key="previous_sender_input")
            with prev_col2:
                previous_reply_to = st.text_input(t("Earlier reply-to address"), placeholder="replies@supplier.com", key="previous_reply_to_input")
            filename = st.text_input(t("Attachment file name"), placeholder="invoice.pdf",
                                     help=t("Only the name and type are checked; the file itself is not scanned."))
        submitted = st.form_submit_button(t("Check message"), type="primary", icon=":material/search:", width="stretch")
        st.caption(":material/lock: " + t("Checked on this server. Nothing is sent to an outside AI service or saved unless you choose to."))
    if submitted:
        st.session_state["draft_text"] = text
        if not text.strip():
            st.warning(t("Paste a message first, then press Check message."), icon=":material/edit_note:")
        else:
            try:
                with st.spinner(t("Checking the message…")):
                    analyze(text, category=category, sender=sender, company_domain=domain, previous_text=previous,
                            previous_sender=previous_sender, previous_reply_to=previous_reply_to,
                            attachments=[{"filename": filename}] if filename else None)
                open_result()
            except (FileNotFoundError, ValueError) as error:
                st.error(str(error) if "Too many requests" in str(error) else t("The check could not be completed. Check the setup in Advanced."),
                         icon=":material/error:")
