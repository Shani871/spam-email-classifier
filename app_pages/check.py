import hashlib
import streamlit as st
from src.ui_shared import analyze, step_tracker, md_escape

step_tracker(1)
st.title("Is this message safe?")
st.caption("Check an email, text, job offer or payment request before you click, reply or pay.")

SOURCES = {
    "Paste text": ":material/content_paste: Paste text",
    "Email file": ":material/mail: Email file",
    "Screenshot or QR": ":material/photo_camera: Screenshot or QR",
    "Connected inbox": ":material/inbox: My inbox",
}
source = st.segmented_control("Where is the message?", list(SOURCES), default="Paste text", key="source",
                              format_func=SOURCES.get, label_visibility="collapsed", width="stretch") or "Paste text"

CATEGORIES = {"General message": "General", "Job or internship": "Job or internship", "Invoice or payment": "Invoice or payment"}

# Inbox list badges: what the app concluded, in a few words.
INBOX_BADGES = {
    "High risk": ":red-badge[:material/gpp_bad: Likely scam]",
    "Needs verification": ":orange-badge[:material/help: Check first]",
    "No strong warning found": ":green-badge[:material/verified_user: Looks normal]",
    "Unable to assess": ":gray-badge[:material/info: Not sure]",
}


def category_picker(key):
    choice = st.segmented_control("What is it about?", list(CATEGORIES), default="General message", key=key,
                                  format_func=CATEGORIES.get, help="Job and payment messages get extra checks for common scams.")
    return choice or "General message"


def open_result():
    st.session_state["selected_message"] = None
    st.switch_page("app_pages/understand.py")


if source == "Email file":
    from src.eml_reader import parse_email_file
    uploaded_email = st.file_uploader("Upload an email saved as .eml", type=["eml"], max_upload_size=10, key="email_file",
                                      help="In Gmail: open the message, ⋮ menu, Download message. In Outlook: File, Save as.")
    st.caption("Links are not opened and attachments are not run. Sender headers in a file are treated as claims, not proof.")
    if uploaded_email:
        try:
            parsed = parse_email_file(uploaded_email.getvalue())
            with st.container(border=True):
                st.markdown(f"**{md_escape(parsed['subject']) or '(No subject)'}**")
                st.caption(f"From {md_escape(parsed['sender']) or 'an unknown sender'}")
                for warning in parsed["warnings"]:
                    st.warning(warning, icon=":material/warning:")
                with st.expander("Read the message text", icon=":material/article:"):
                    st.text(parsed["display_body"] or "No readable message body.")
                if parsed["attachments"]:
                    st.caption(f":material/attach_file: {len(parsed['attachments'])} attachment(s). Names and types are checked; contents are not scanned.")
            with st.form("email_file_check", border=False):
                category = category_picker("eml_category")
                with st.expander("More options", icon=":material/tune:"):
                    domain = st.text_input("Official website of the employer or supplier", placeholder="company.com")
                    previous = st.text_area("Earlier message in the same conversation", max_chars=50000, key="eml_prev_text",
                                            help="We compare payment details, sender and links between the two.")
                    previous_sender = st.text_input("Earlier sender address", key="eml_prev_sender")
                    previous_reply_to = st.text_input("Earlier reply-to address", key="eml_prev_reply_to")
                submitted = st.form_submit_button("Check this email", type="primary", icon=":material/search:", width="stretch")
            if submitted:
                with st.spinner("Checking the text, links and sender…"):
                    result = analyze(parsed["full_text"], category=category, sender=parsed["sender"], company_domain=domain,
                                     previous_text=previous, previous_sender=previous_sender, previous_reply_to=previous_reply_to,
                                     headers=parsed["headers"], attachments=parsed["attachments"])
                result["limitations"].extend(parsed["warnings"])
                open_result()
        except ValueError as error:
            st.error(str(error), icon=":material/error:")
        except FileNotFoundError:
            st.error("The checker is not set up yet. See Advanced for setup instructions.", icon=":material/error:")

elif source == "Connected inbox":
    from src.ui_shared import gmail_token, connect_inbox
    from src.rate_limit import enforce
    from src.gmail_api import scan_gmail_with_oauth
    from src.gmail_scanner import scan_gmail_inbox
    token = gmail_token()
    credentials = st.session_state.get("imap_credentials", {})
    if not token and not credentials:
        st.caption("Scan your recent emails without copying anything. We only read them; nothing is moved or deleted.")
        col_connect, col_demo = st.columns(2)
        with col_connect.container(border=True, height="stretch"):
            st.markdown("**:material/link: Connect your email**")
            with st.form("quick_inbox_connect", border=False):
                quick_email = st.text_input("Email address", placeholder="name@gmail.com")
                quick_pwd = st.text_input("App password", type="password", placeholder="16-character app password",
                                          help="Not your normal password. Create one in your email account's security settings; Settings explains how.")
                quick_submit = st.form_submit_button("Connect", type="primary", width="stretch", icon=":material/login:")
            if quick_submit:
                if not quick_email.strip() or not quick_pwd.strip():
                    st.warning("Enter your email address and app password.")
                else:
                    with st.spinner("Connecting…"):
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
            st.page_link("app_pages/settings.py", label="Other ways to connect", icon=":material/settings:")
        with col_demo.container(border=True, height="stretch"):
            st.markdown("**:material/science: Try the demo inbox**")
            st.caption("Five sample emails, including two scams, so you can see how it works first.")
            if st.button("Open demo inbox", icon=":material/play_circle:", width="stretch"):
                st.session_state["imap_credentials"] = {"email_address": "demo@spamguard.local", "app_password": "demo",
                                                        "provider": "SpamGuard demo inbox"}
                st.session_state["inbox_provider_name"] = "SpamGuard demo inbox"
                st.session_state.messages = []
                st.rerun()
    else:
        connected_email = credentials.get("email_address") or (st.user.get("email") if token else "your inbox")
        provider_name = credentials.get("provider") or st.session_state.get("inbox_provider_name") or ("Gmail" if token else "IMAP")
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(f"Connected: {md_escape(connected_email)} ({md_escape(provider_name)})", icon=":material/check_circle:", color="green")
            st.page_link("app_pages/settings.py", label="Change", icon=":material/settings:")
        with st.form("inbox_scan", border=True):
            col_count, col_folder = st.columns(2)
            with col_count:
                count = st.select_slider("How many recent emails", [5, 10, 15, 20, 25], value=10)
            with col_folder:
                folder = st.selectbox("Folder", ["INBOX", "[Gmail]/Spam", "Spam", "Junk"], index=0,
                                      format_func=lambda f: {"INBOX": "Inbox", "[Gmail]/Spam": "Gmail spam"}.get(f, f))
            unread = st.toggle("Only unread", value=False)
            submitted = st.form_submit_button("Scan emails", type="primary", width="stretch", icon=":material/search:")
        if submitted:
            try:
                enforce("inbox_scan", st.session_state.get("identity", ""))
                with st.spinner("Reading and checking your emails…"):
                    if token:
                        messages = scan_gmail_with_oauth(token, count, unread, "svm")
                    else:
                        messages = scan_gmail_inbox(email_address=credentials["email_address"], app_password=credentials["app_password"],
                                                    folder=folder, max_emails=count, only_unread=unread, model_type="svm",
                                                    imap_host=credentials.get("imap_host", ""), imap_port=credentials.get("imap_port", 993))
                st.session_state["messages"] = messages
                if not messages:
                    st.info("No emails matched this scan.", icon=":material/inbox:")
            except Exception as err:
                st.session_state["messages"] = []
                st.error(f"The scan didn't work: {err}", icon=":material/error:")
                st.caption("Try reconnecting in Settings, or check that your app password is still valid.")
        messages = st.session_state.get("messages", [])
        if messages:
            from src.scam_assistant import inbox_triage
            for m in messages:
                if "assessment" not in m:
                    m["assessment"] = inbox_triage(m)
            counts = {k: sum(m["assessment"] == k for m in messages) for k in INBOX_BADGES}
            attention = counts["High risk"] + counts["Needs verification"]
            st.subheader(f"{len(messages)} emails checked", anchor=False)
            st.markdown("  ".join(f"{INBOX_BADGES[k]} {counts[k]}" for k in INBOX_BADGES if counts[k]))
            show = st.segmented_control("Show", ["All", "Needs attention"], default="All", key="inbox_filter",
                                        label_visibility="collapsed") or "All"
            if show == "Needs attention" and not attention:
                st.success("Nothing here needs attention.", icon=":material/verified_user:")
            for index, message in enumerate(messages):
                if show == "Needs attention" and message["assessment"] not in {"High risk", "Needs verification"}:
                    continue
                with st.container(border=True, horizontal=True, vertical_alignment="center", gap="small"):
                    with st.container(gap="xsmall"):
                        st.markdown(f"{INBOX_BADGES[message['assessment']]} **{md_escape(message['subject']) or '(No subject)'}**")
                        st.caption(f"{md_escape(message['sender'])} · {md_escape(message.get('date', ''))[:31]}")
                    if st.button("Details", key=f"inbox_open_{index}", icon=":material/arrow_forward:", width="content"):
                        try:
                            with st.spinner("Checking this email in detail…"):
                                analyze(message["full_text"], sender=message["sender"], headers=message.get("headers"),
                                        attachments=message.get("attachments"),
                                        sender_verified=bool((message.get("sender_verification") or {}).get("verified")))
                            st.session_state["selected_message"] = dict(message)
                            st.switch_page("app_pages/understand.py")
                        except (FileNotFoundError, ValueError) as error:
                            st.error(f"The check could not be completed: {error}", icon=":material/error:")

else:
    st.session_state.setdefault("message_input", st.session_state.get("draft_text", ""))
    if source == "Screenshot or QR":
        from src.image_checks import extract_image_content
        uploaded = st.file_uploader("Upload a screenshot or a photo of a QR code", type=["png", "jpg", "jpeg", "webp"], max_upload_size=10)
        st.caption("Text is read on this server. QR links are shown, never opened. Check the text below before you continue.")
        if uploaded:
            data = uploaded.getvalue()
            digest = hashlib.sha256(data).hexdigest()
            with st.expander("Your image", icon=":material/image:"):
                st.image(data, width="stretch")
            if st.session_state.get("image_digest") != digest:
                try:
                    with st.spinner("Reading the image…"):
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
                st.caption("The QR code points to (not opened):")
                st.code(destination, language=None)
    else:
        EXAMPLES = {
            ":material/work: Job scam": "You are selected for a remote internship. Pay a registration fee of ₹2,000 to confirm your job. Send your Aadhaar and bank details immediately.",
            ":material/payments: Fake payment": "Your UPI payment of ₹9,999 is pending. Click here immediately to confirm your bank account: http://paypa1-verify.xyz",
            ":material/password: OTP request": "Dear customer, your account will be suspended. Share OTP 847291 with our agent on 8800123456 to verify your identity.",
        }

        def use_example():
            choice = st.session_state.get("example_choice")
            if choice:
                st.session_state["message_input"] = EXAMPLES[choice]
                st.session_state["example_choice"] = None

        st.pills("No message handy? Try an example", list(EXAMPLES), key="example_choice", on_change=use_example)

    with st.form("message_check", border=True):
        text = st.text_area("Message", height=200, key="message_input", max_chars=50000,
                            placeholder="Paste the whole message here, including any links. Remove anything private you don't want to share.")
        category = category_picker("message_category")
        with st.expander("More options: sender, earlier message, attachment", icon=":material/tune:"):
            sender = st.text_input("Sender's email address", placeholder="sender@example.com", key="current_sender_input")
            domain = st.text_input("Official website of the employer or supplier", placeholder="company.com",
                                   help="We warn if the sender or links don't match it.")
            st.markdown("**:material/compare_arrows: Compare with an earlier message**")
            st.caption("Useful for invoices and ongoing conversations: we look for changed bank details, senders, links or new requests.")
            previous = st.text_area("Earlier message", height=100, max_chars=50000, key="previous_message_input",
                                    placeholder="Paste an earlier message from the same conversation")
            prev_col1, prev_col2 = st.columns(2)
            with prev_col1:
                previous_sender = st.text_input("Earlier sender address", placeholder="alice@supplier.com", key="previous_sender_input")
            with prev_col2:
                previous_reply_to = st.text_input("Earlier reply-to address", placeholder="replies@supplier.com", key="previous_reply_to_input")
            filename = st.text_input("Attachment file name", placeholder="invoice.pdf",
                                     help="Only the name and type are checked; the file itself is not scanned.")
        submitted = st.form_submit_button("Check message", type="primary", icon=":material/search:", width="stretch")
        st.caption(":material/lock: Checked on this server. Nothing is sent to an outside AI service or saved unless you choose to.")
    if submitted:
        st.session_state["draft_text"] = text
        if not text.strip():
            st.warning("Paste a message first, then press Check message.", icon=":material/edit_note:")
        else:
            try:
                with st.spinner("Checking the message…"):
                    analyze(text, category=category, sender=sender, company_domain=domain, previous_text=previous,
                            previous_sender=previous_sender, previous_reply_to=previous_reply_to,
                            attachments=[{"filename": filename}] if filename else None)
                open_result()
            except (FileNotFoundError, ValueError) as error:
                st.error(str(error) if "Too many requests" in str(error) else "The check could not be completed. Check the setup in Advanced.",
                         icon=":material/error:")
