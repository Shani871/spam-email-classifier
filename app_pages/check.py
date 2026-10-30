import hashlib
import streamlit as st
from src.ui_shared import analyze, step_tracker

step_tracker(1)
st.title("Is this message worth trusting?")
st.markdown("Check an email, a job offer, or a payment request before you take the next step.")
source = st.segmented_control("Message source", ["Paste text", "Email file", "Screenshot or QR", "Connected inbox"], default="Paste text", key="source")

_METHOD_INFO = {
    "Paste text": ("📋", "Copy any suspicious message — email, SMS, WhatsApp, or job offer — and paste it below."),
    "Email file": ("📎", "Export the email as .eml from your email app and upload it. Links, headers, and metadata are all checked."),
    "Screenshot or QR": ("📷", "Upload a screenshot or a QR code image. Text is extracted locally — the image is never sent anywhere."),
    "Connected inbox": ("📬", "Connect Gmail in Settings and scan recent messages directly without copying anything."),
}
_icon, _desc = _METHOD_INFO.get(source, ("📋", ""))
st.markdown(
    f'<div style="display:flex;gap:14px;align-items:center;padding:14px 18px;'
    f'background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;margin:8px 0 16px;">'
    f'<span style="font-size:24px;flex-shrink:0;">{_icon}</span>'
    f'<span style="color:#1E40AF;font-size:13px;line-height:1.5;">{_desc}</span></div>',
    unsafe_allow_html=True
)

if source == "Email file":
    from src.eml_reader import parse_email_file
    st.caption("Export a message as .eml from your email app. Links are not opened, and attachment files are not executed or extracted to disk.")
    uploaded_email = st.file_uploader("Upload an email file", type=["eml"], max_upload_size=10, key="email_file")
    if uploaded_email:
        try:
            parsed = parse_email_file(uploaded_email.getvalue())
            st.text(f"Subject: {parsed['subject']}\nFrom: {parsed['sender'] or '(Not supplied)'}")
            for warning in parsed["warnings"]:
                st.warning(warning)
            with st.expander("Review message text", expanded=True):
                st.text(parsed["display_body"] or "No readable message body.")
            if parsed["attachments"]:
                st.caption("Attachment metadata only — file contents are not scanned")
                st.dataframe(parsed["attachments"], hide_index=True)
            with st.form("email_file_check"):
                category = st.selectbox("What kind of email is this?", ["General message", "Job or internship", "Invoice or payment"])
                domain = st.text_input("Employer or supplier's official domain (optional)")
                with st.expander("Compare with earlier message in thread (optional)"):
                    previous = st.text_area("Earlier message text", max_chars=50000, key="eml_prev_text")
                    previous_sender = st.text_input("Earlier sender address (optional)", key="eml_prev_sender")
                    previous_reply_to = st.text_input("Earlier reply-to address (optional)", key="eml_prev_reply_to")
                submitted = st.form_submit_button("Check email file", type="primary", icon=":material/search:", width="stretch")
            if submitted:
                with st.spinner("Checking email text, links, and metadata…"):
                    result = analyze(parsed["full_text"], category=category, sender=parsed["sender"], company_domain=domain,
                                     previous_text=previous, previous_sender=previous_sender, previous_reply_to=previous_reply_to,
                                     headers=parsed["headers"], attachments=parsed["attachments"])
                result["limitations"].extend(parsed["warnings"])
                st.session_state["selected_message"] = None
                st.switch_page("app_pages/understand.py")
        except ValueError as error:
            st.error(str(error))
        except FileNotFoundError:
            st.error("The model is unavailable. Check the setup instructions in Advanced.")
elif source == "Connected inbox":
    from src.ui_shared import gmail_token
    from src.gmail_api import scan_gmail_with_oauth
    from src.gmail_scanner import scan_gmail_inbox, verify_inbox_connection, resolve_imap_settings
    token = gmail_token()
    credentials = st.session_state.get("imap_credentials", {})
    if not token and not credentials:
        st.info("No active inbox connection. Connect your email or try the demo mailbox to scan messages automatically.")
        col_conn, col_demo = st.columns([1, 1])
        with col_conn:
            st.markdown("#### Connect Your Email")
            with st.form("quick_inbox_connect"):
                quick_email = st.text_input("Email address", placeholder="e.g. name@gmail.com or user@outlook.com")
                quick_pwd = st.text_input("App Password", type="password", placeholder="16-character App Password")
                quick_submit = st.form_submit_button("Test & Connect", type="primary", width="stretch")
            if quick_submit:
                if not quick_email.strip() or not quick_pwd.strip():
                    st.warning("Enter both your email and App Password.")
                else:
                    with st.spinner("Connecting to mail server…"):
                        res = verify_inbox_connection(quick_email.strip(), quick_pwd.strip())
                    if res["success"]:
                        st.session_state["imap_credentials"] = {
                            "email_address": quick_email.strip(),
                            "app_password": quick_pwd.strip(),
                            "provider": res["provider"]
                        }
                        st.session_state["inbox_provider_name"] = res["provider"]
                        st.session_state.messages = []
                        st.success(res["message"])
                        st.rerun()
                    else:
                        st.error(res["message"])
                        if res.get("troubleshooting"):
                            st.info(res["troubleshooting"])
            st.page_link("app_pages/settings.py", label="Open advanced connection settings", icon=":material/settings:")
        with col_demo:
            st.markdown("#### Instant Demo Mailbox")
            st.caption("Scan 5 pre-configured realistic threat and legitimate emails without entering your credentials.")
            if st.button("Use Demo Mailbox (5 emails)", type="secondary", icon=":material/play_circle:", width="stretch"):
                st.session_state["imap_credentials"] = {
                    "email_address": "demo@spamguard.local",
                    "app_password": "demo",
                    "provider": "SpamGuard Demo Feed"
                }
                st.session_state["inbox_provider_name"] = "SpamGuard Demo Feed"
                st.session_state.messages = []
                st.success("Connected to SpamGuard Demo Mailbox!")
                st.rerun()
    else:
        connected_email = credentials.get("email_address") or (st.user.get("email") if token else "Connected Email")
        provider_name = credentials.get("provider") or st.session_state.get("inbox_provider_name") or ("Google Gmail (OAuth)" if token else "IMAP Mailbox")
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;'
            f'background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;margin-bottom:12px;">'
            f'<div><span style="font-weight:600;color:#15803D;">● Connected:</span> {connected_email} '
            f'<span style="font-size:12px;color:#4B5563;">({provider_name})</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )
        with st.form("inbox_scan"):
            scan_col1, scan_col2, scan_col3 = st.columns([1, 1, 1])
            with scan_col1:
                count = st.slider("Messages to check", 5, 25, 10, 5)
            with scan_col2:
                folder = st.selectbox("Folder", ["INBOX", "[Gmail]/Spam", "Spam", "Junk"], index=0)
            with scan_col3:
                unread = st.checkbox("Only unread messages", value=False)
            submitted = st.form_submit_button("Read recent messages", type="primary", width="stretch")
        if submitted:
            try:
                with st.spinner("Reading and classifying messages…"):
                    if token:
                        messages = scan_gmail_with_oauth(token, count, unread, "svm")
                    else:
                        messages = scan_gmail_inbox(
                            email_address=credentials["email_address"],
                            app_password=credentials["app_password"],
                            folder=folder,
                            max_emails=count,
                            only_unread=unread,
                            model_type="svm",
                            imap_host=credentials.get("imap_host", ""),
                            imap_port=credentials.get("imap_port", 993)
                        )
                st.session_state["messages"] = messages
                if not messages:
                    st.info(f"No messages found matching this scan in '{folder}'.")
            except Exception as err:
                st.session_state["messages"] = []
                st.error(f"Inbox scan error: {err}")
                st.info("Try reconnecting in Settings or checking your App Password permissions.")
        messages = st.session_state.get("messages", [])
        if messages:
            st.markdown(f"**Found {len(messages)} messages:**")
            def format_msg(i):
                m = messages[i]
                tag = "🚨 SPAM" if m.get("is_spam") else "✅ CLEAN"
                return f"{tag} · {m['subject']} · {m['sender']}"
            chosen = st.selectbox("Choose a message to examine", range(len(messages)), format_func=format_msg)
            message = messages[chosen]
            with st.container(border=True):
                st.markdown(f"**Subject:** {message['subject']}")
                st.markdown(f"**From:** `{message['sender']}` · **Date:** {message['date']}")
                if message.get("attachments"):
                    st.caption(f"📎 Attachments ({len(message['attachments'])}): {', '.join(a.get('filename', '') for a in message['attachments'])}")
                st.text_area("Body preview", message["body_preview"], height=100, disabled=True)
            if st.button("Check this message in depth", type="primary", icon=":material/search:", width="stretch"):
                try:
                    with st.spinner("Running security analysis & forensics…"):
                        analyze(message["full_text"], sender=message["sender"], headers=message.get("headers"), attachments=message.get("attachments"))
                    st.session_state["selected_message"] = dict(message)
                    st.switch_page("app_pages/understand.py")
                except (FileNotFoundError, ValueError) as e:
                    st.error(f"The check could not be completed: {e}")
else:
    st.session_state.setdefault("message_input", st.session_state.get("draft_text", ""))
    if source == "Screenshot or QR":
        from src.image_checks import extract_image_content
        uploaded = st.file_uploader("Upload a screenshot or QR image", type=["png", "jpg", "jpeg", "webp"], max_upload_size=10)
        if uploaded:
            data = uploaded.getvalue()
            digest = hashlib.sha256(data).hexdigest()
            st.image(data, caption="Uploaded image — review extracted text before checking.", width="stretch")
            if st.session_state.get("image_digest") != digest:
                try:
                    with st.spinner("Reading the image locally…"):
                        extracted = extract_image_content(data, "eng+hin" if st.session_state.language == "Hindi" else "eng")
                    st.session_state["image_digest"] = digest
                    st.session_state["image_extraction"] = extracted
                    st.session_state["message_input"] = extracted["text"] + "\n" + "\n".join(extracted["qr_destinations"])
                except ValueError as error:
                    st.error(str(error))
            extracted = st.session_state.get("image_extraction", {})
            for warning in extracted.get("warnings", []):
                st.warning(warning)
            for destination in extracted.get("qr_destinations", []):
                st.caption("Decoded QR content — destination has not been opened")
                st.code(destination, language=None)
    else:
        if source == "Paste text":
            st.markdown("**💡 Not sure what to paste? Try a real example:**")
            _ex_col1, _ex_col2, _ex_col3 = st.columns(3)
            _EXAMPLES = {
                "🪤 Job scam": "You are selected for a remote internship. Pay a registration fee of ₹2,000 to confirm your job. Send your Aadhaar and bank details immediately.",
                "💳 Fake payment": "Your UPI payment of ₹9,999 is pending. Click here immediately to confirm your bank account: http://paypa1-verify.xyz",
                "🔑 OTP phishing": "Dear customer, your account will be suspended. Share OTP 847291 with our agent on 8800123456 to verify your identity.",
            }
            for _col, (_label, _text) in zip([_ex_col1, _ex_col2, _ex_col3], _EXAMPLES.items()):
                with _col:
                    if st.button(_label, width="stretch", key=f"ex_{_label}"):
                        st.session_state["message_input"] = _text
                        st.rerun()
    with st.form("message_check", border=True):
        category = st.selectbox("What kind of message is this?", ["General message", "Job or internship", "Invoice or payment"])
        text = st.text_area("Message text", height=220, placeholder="Paste the full message here. Remove private details you do not want to submit.", key="message_input", max_chars=50000)
        with st.expander("Add context or compare earlier message"):
            sender = st.text_input("Current sender email address (optional)", placeholder="sender@example.com", key="current_sender_input")
            domain = st.text_input("Employer or supplier's official domain (optional)", placeholder="company.com")
            st.markdown("**:material/compare_arrows: Compare earlier message in thread (optional)**")
            st.caption("Check for sudden changes in sender, reply-to, payment details, links, or sensitive requests.")
            previous = st.text_area("Earlier message text (optional)", height=100, max_chars=50000, placeholder="Paste earlier message from this thread to compare…", key="previous_message_input")
            prev_col1, prev_col2 = st.columns(2)
            with prev_col1:
                previous_sender = st.text_input("Earlier sender address (optional)", placeholder="alice@supplier.com", key="previous_sender_input")
            with prev_col2:
                previous_reply_to = st.text_input("Earlier reply-to address (optional)", placeholder="replies@supplier.com", key="previous_reply_to_input")
            filename = st.text_input("Attachment filename (optional)", help="Filename and metadata checks only; file contents will not be scanned.")
        st.markdown(
            '<div style="display:flex;gap:10px;align-items:center;padding:10px 14px;'
            'background:#F0FDF4;border:1px solid #BBF7D0;'
            'border-radius:8px;margin:6px 0 4px;">'
            '<span style="font-size:15px;">🔒</span>'
            '<span style="font-size:12px;color:#15803D;">Checked on this server only — '
            'nothing is sent to any AI service unless you choose it.</span></div>',
            unsafe_allow_html=True
        )
        submitted = st.form_submit_button("Check message", type="primary", icon=":material/search:", width="stretch")
    if submitted:
        st.session_state["draft_text"] = text
        if not text.strip():
            st.warning("Add message text before checking.")
        else:
            try:
                with st.spinner("Checking the message and its evidence…"):
                    analyze(text, category=category, sender=sender, company_domain=domain, previous_text=previous,
                            previous_sender=previous_sender, previous_reply_to=previous_reply_to,
                            attachments=[{"filename": filename}] if filename else None)
                st.session_state["selected_message"] = None
                st.switch_page("app_pages/understand.py")
            except (FileNotFoundError, ValueError):
                st.error("The check could not be completed. Check the model setup in Advanced.")
st.caption("No account connection needed for pasted text. Results stay in this session unless saving is enabled in Settings.")
