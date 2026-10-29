from datetime import datetime, timezone
import streamlit as st
from src.ui_shared import result_required, assessment_card, gmail_token, step_tracker
from src.scam_assistant import recovery_steps
from src.active_learning import record_feedback

step_tracker(3)
st.title("Choose your next step")
result = result_required()
assessment_card(result)
st.subheader("What happened so far?")
stage = st.selectbox("Your situation", ["Only received the message", "Clicked a link", "Shared a password or OTP", "Sent money or payment details"])
for index, step in enumerate(recovery_steps(stage, st.session_state.language), 1):
    st.markdown(f"{index}. {step}")
with st.container(horizontal=True):
    st.link_button("India: report cybercrime", "https://cybercrime.gov.in/")
    st.link_button("Recovery guidance (FTC)", "https://consumer.ftc.gov/articles/what-do-if-you-were-scammed")
st.caption("Region-specific: cybercrime.gov.in and helpline 1930 are India-only. Outside India, contact your national cybercrime authority or local police.")

message = st.session_state.get("selected_message")
if message and message.get("provider") == "gmail" and gmail_token():
    from src.gmail_api import modify_message_labels, get_message_labels
    st.subheader("Manage this email")
    st.caption("Moving to Spam is optional. Gmail must grant inbox action permission. No message is permanently deleted.")
    consent_key = f"confirm_{message['id']}"
    confirmed = st.checkbox("Move this selected email to Spam", key=consent_key)
    if st.button("Move to Spam", disabled=not confirmed, type="primary"):
        before = get_message_labels(gmail_token(), message["id"])
        if before is None:
            st.error("Could not confirm the current message state. Reconnect and rescan.")
        else:
            outcome = modify_message_labels(gmail_token(), message["id"], ["SPAM"], ["INBOX"])
            if outcome["success"]:
                st.session_state.actions.append({"id": message["id"], "timestamp": datetime.now(timezone.utc).isoformat(),
                                                 "action": "Moved to Spam", "before": before, "undone": False})
                st.success(outcome["message"])
            else:
                st.error(outcome["message"])
    recent = next((action for action in reversed(st.session_state.actions) if action["id"] == message["id"] and not action["undone"]), None)
    if recent and st.button("Undo last move", icon=":material/undo:"):
        current = get_message_labels(gmail_token(), message["id"])
        if current is None:
            st.error("Could not confirm the current message state. Reconnect and rescan.")
        else:
            original = set(recent["before"]) & {"SPAM", "INBOX"}
            outcome = modify_message_labels(gmail_token(), message["id"], sorted(original), sorted({"SPAM", "INBOX"} - original))
            if outcome["success"]:
                recent["undone"] = True
                st.session_state.actions.append({"id": message["id"], "timestamp": datetime.now(timezone.utc).isoformat(), "action": "Restored previous inbox/spam labels", "undone": True})
                st.success("Gmail confirmed that the previous inbox/spam labels were restored.")
            else:
                st.error(outcome["message"])
elif message:
    st.caption("This inbox connection supports checking only. Use Gmail directly to move messages, or connect with Google inbox action permission.")

with st.expander("Report an incorrect classification", expanded=False):
    from src.active_learning import redact_personal_data
    st.markdown("**:material/lock: Consent-based feedback review**")
    st.caption("Corrections help improve future models. Basic redaction masks email addresses and phone numbers; please review the text below and remove any remaining personal names, addresses, or sensitive details before submitting.")
    with st.form("feedback"):
        corrected = st.radio("Correct classification for this message", ["Legitimate message", "Spam message"])
        clean_draft = redact_personal_data(st.session_state.checked_text)
        reviewed_text = st.text_area(
            "Review and remove private details (pre-redacted)",
            value=clean_draft,
            height=130,
            max_chars=50000,
            help="Remove any personal names, physical addresses, or confidential details before sending."
        )
        comment = st.text_input("Optional comment or reason for correction", placeholder="e.g. Genuine internal project alert from IT team")
        st.markdown("**Privacy and retention notice:**")
        st.caption("Submissions remain strictly private until explicit consent is given. Feedback is held for up to 30 days. Deleting account data in Settings permanently removes saved feedback, but cannot retroactively modify already deployed model releases. Retraining requires administrator review and performance gates.")
        consent = st.checkbox("I give explicit consent to share this reviewed correction with administrators for review and potential model training")
        submitted = st.form_submit_button("Submit correction", disabled=not consent, type="primary")
    if submitted:
        if not consent:
            st.error("Explicit consent is required to submit a correction.")
        else:
            try:
                record_feedback(
                    reviewed_text,
                    result.get("report", {}).get("ml_result", {}).get("label", "Unknown"),
                    "ham" if corrected == "Legitimate message" else "spam",
                    comment,
                    consent_given=True
                )
                st.success("Correction saved with your explicit consent. An administrator will review it before it can affect future model candidates.")
            except ValueError as error:
                st.error(str(error))
if st.session_state.actions:
    with st.expander("Actions confirmed in this session"):
        st.dataframe([{k: v for k, v in a.items() if k in {"timestamp", "action", "undone"}} for a in st.session_state.actions], hide_index=True)
st.page_link("app_pages/check.py", label="Check another message", icon=":material/search:")
