import hashlib
import streamlit as st
from src.ui_shared import analyze

st.caption("01 / CHECK")
st.title("Is this message worth trusting?")
st.markdown("Check an email, a job offer, or a payment request before you take the next step.")
source = st.segmented_control("Message source", ["Paste text", "Email file", "Screenshot or QR", "Connected inbox"], default="Paste text", key="source")

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
    from src.gmail_scanner import scan_gmail_inbox
    token = gmail_token()
    credentials = st.session_state.get("imap_credentials", {})
    if not token and not credentials:
        st.info("Connect an inbox in Settings, or paste a message to check it privately.")
        st.page_link("app_pages/settings.py", label="Connect an inbox", icon=":material/settings:")
    else:
        with st.form("inbox_scan"):
            count = st.slider("Messages to check", 5, 25, 10, 5)
            unread = st.checkbox("Only unread messages")
            submitted = st.form_submit_button("Read recent messages", type="primary")
        if submitted:
            try:
                with st.spinner("Reading recent messages…"):
                    messages = scan_gmail_with_oauth(token, count, unread, "svm") if token else scan_gmail_inbox(**credentials, max_emails=count, only_unread=unread, model_type="svm")
                st.session_state["messages"] = messages
                if not messages:
                    st.info("No messages matched this scan.")
            except (PermissionError, ValueError, ConnectionError, RuntimeError, OSError):
                st.session_state["messages"] = []
                st.error("The inbox could not be read. Reconnect in Settings and check that Gmail access is permitted.")
        messages = st.session_state["messages"]
        if messages:
            chosen = st.selectbox("Choose a message", range(len(messages)), format_func=lambda i: f"{messages[i]['subject']} · {messages[i]['sender']}")
            message = messages[chosen]
            st.text(message["body_preview"])
            if st.button("Check this message", type="primary", icon=":material/search:"):
                try:
                    with st.spinner("Checking the message and its evidence…"):
                        analyze(message["full_text"], sender=message["sender"], headers=message.get("headers"), attachments=message.get("attachments"))
                    st.session_state["selected_message"] = dict(message)
                    st.switch_page("app_pages/understand.py")
                except (FileNotFoundError, ValueError):
                    st.error("The check could not be completed. Check the model setup in Advanced.")
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
        with st.expander("Try an example"):
            example = st.selectbox("Example message", ["Job offer with a fee", "Ordinary meeting", "Changed invoice details"])
            if st.button("Use example"):
                st.session_state["message_input"] = {
                    "Job offer with a fee": "You are selected for a remote internship. Pay a registration fee of ₹2,000 to confirm your job. Send your Aadhaar and bank details immediately.",
                    "Ordinary meeting": "Hi team, our project review is tomorrow at 10 AM. Please bring your notes. Thanks!",
                    "Changed invoice details": "Please pay the outstanding invoice using our new account number: 12345678901. Confirm once paid."}[example]
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
