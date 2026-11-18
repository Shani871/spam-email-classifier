from datetime import datetime, timezone
import streamlit as st
from src.ui_shared import result_required, assessment_card, gmail_token, step_tracker
from src.scam_assistant import recovery_steps
from src.active_learning import record_feedback

step_tracker(3)
st.title("What to do now")
result = result_required()
assessment_card(result, compact=True)

SITUATIONS = {
    "Only received the message": ":material/mail: I only received it",
    "Clicked a link": ":material/ads_click: I clicked a link",
    "Shared a password or OTP": ":material/password: I shared a password or code",
    "Sent money or payment details": ":material/payments: I sent money or card details",
}
stage = st.pills("What has happened so far?", list(SITUATIONS), default="Only received the message", key="situation",
                 format_func=SITUATIONS.get) or "Only received the message"
with st.container(border=True):
    st.markdown("**:material/checklist: Do this now**")
    for index, step in enumerate(recovery_steps(stage, st.session_state.language), 1):
        st.markdown(f"{index}. {step}")

st.subheader("Report it", anchor=False)
with st.container(horizontal=True):
    st.link_button("India: cybercrime.gov.in or call 1930", "https://cybercrime.gov.in/", icon=":material/gavel:")
    st.link_button("USA: ReportFraud.ftc.gov", "https://consumer.ftc.gov/articles/what-do-if-you-were-scammed", icon=":material/policy:")
st.caption("Elsewhere, report to your national cybercrime authority or local police. If money left your account, call your bank first.")

message = st.session_state.get("selected_message")
if message and message.get("provider") == "gmail" and gmail_token():
    from src.gmail_api import modify_message_labels, get_message_labels
    st.subheader("Move this email", anchor=False)
    st.caption("Optional. It moves to your Gmail spam folder and can be undone; nothing is deleted.")
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
    st.caption(":material/info: To move this email to spam, use your email app. This connection can read emails but not move them.")

with st.expander("Was this result wrong? Tell us", icon=":material/feedback:"):
    from src.active_learning import redact_personal_data
    st.caption("Your correction helps improve the checker. Email addresses and phone numbers are hidden automatically; remove names or anything else private before sending.")
    with st.form("feedback"):
        corrected = st.radio("This message is actually", ["Legitimate message", "Spam message"], horizontal=True)
        clean_draft = redact_personal_data(st.session_state.checked_text)
        reviewed_text = st.text_area(
            "Message text to send (edit out private details)",
            value=clean_draft,
            height=130,
            max_chars=50000,
            help="Remove any personal names, physical addresses, or confidential details before sending."
        )
        comment = st.text_input("Why? (optional)", placeholder="e.g. It's a real alert from my bank")
        st.caption("Kept for up to 30 days and reviewed by an administrator before it is used. You can delete it any time in Settings.")
        consent = st.checkbox("I agree to share this corrected message with the administrators for review and model training")
        submitted = st.form_submit_button("Send correction", type="primary", icon=":material/send:")
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
                st.success("Thanks, your correction was saved. An administrator will review it before it is used.", icon=":material/check_circle:")
            except ValueError as error:
                st.error(str(error))
if st.session_state.actions:
    with st.expander("Actions taken in this session", icon=":material/history:"):
        st.dataframe([{k: v for k, v in a.items() if k in {"timestamp", "action", "undone"}} for a in st.session_state.actions], hide_index=True)
st.page_link("app_pages/check.py", label="Check another message", icon=":material/search:")
