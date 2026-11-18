from datetime import datetime, timezone
import streamlit as st
from src.ui_shared import result_required, assessment_card, gmail_token, step_tracker
from src.scam_assistant import recovery_steps
from src.active_learning import record_feedback
from src.i18n import t

step_tracker(3)
st.title(t("What to do now"))
result = result_required()
assessment_card(result, compact=True)

# Internal values stay in English (they select the recovery guide); labels are translated.
SITUATIONS = {
    "Only received the message": (":material/mail:", "I only received it"),
    "Clicked a link": (":material/ads_click:", "I clicked a link"),
    "Shared a password or OTP": (":material/password:", "I shared a password or code"),
    "Sent money or payment details": (":material/payments:", "I sent money or card details"),
}
stage = st.pills(t("What has happened so far?"), list(SITUATIONS), default="Only received the message", key="situation",
                 format_func=lambda key: f"{SITUATIONS[key][0]} {t(SITUATIONS[key][1])}") or "Only received the message"
with st.container(border=True):
    st.markdown(f"**:material/checklist: {t('Do this now')}**")
    for index, step in enumerate(recovery_steps(stage, st.session_state.language), 1):
        st.markdown(f"{index}. {step}")

st.subheader(t("Report it"), anchor=False)
with st.container(horizontal=True):
    st.link_button(t("India: cybercrime.gov.in or call 1930"), "https://cybercrime.gov.in/", icon=":material/gavel:")
    st.link_button(t("USA: ReportFraud.ftc.gov"), "https://consumer.ftc.gov/articles/what-do-if-you-were-scammed", icon=":material/policy:")
st.caption(t("Elsewhere, report to your national cybercrime authority or local police. If money left your account, call your bank first."))

message = st.session_state.get("selected_message")
if message and message.get("provider") == "gmail" and gmail_token():
    from src.gmail_api import modify_message_labels, get_message_labels
    st.subheader(t("Move this email to spam"), anchor=False)
    st.caption(t("Optional. It moves to your Gmail spam folder and can be undone; nothing is deleted."))
    consent_key = f"confirm_{message['id']}"
    confirmed = st.checkbox(t("Yes, move this email to spam"), key=consent_key)
    if st.button(t("Move to spam"), disabled=not confirmed, type="primary", icon=":material/report:"):
        before = get_message_labels(gmail_token(), message["id"])
        if before is None:
            st.error(t("Could not confirm the current message state. Reconnect and rescan."))
        else:
            outcome = modify_message_labels(gmail_token(), message["id"], ["SPAM"], ["INBOX"])
            if outcome["success"]:
                st.session_state.actions.append({"id": message["id"], "timestamp": datetime.now(timezone.utc).isoformat(),
                                                 "action": "Moved to Spam", "before": before, "undone": False})
                st.success(outcome["message"])
            else:
                st.error(outcome["message"])
    recent = next((action for action in reversed(st.session_state.actions) if action["id"] == message["id"] and not action["undone"]), None)
    if recent and st.button(t("Undo last move"), icon=":material/undo:"):
        current = get_message_labels(gmail_token(), message["id"])
        if current is None:
            st.error(t("Could not confirm the current message state. Reconnect and rescan."))
        else:
            original = set(recent["before"]) & {"SPAM", "INBOX"}
            outcome = modify_message_labels(gmail_token(), message["id"], sorted(original), sorted({"SPAM", "INBOX"} - original))
            if outcome["success"]:
                recent["undone"] = True
                st.session_state.actions.append({"id": message["id"], "timestamp": datetime.now(timezone.utc).isoformat(),
                                                 "action": "Restored previous inbox/spam labels", "undone": True})
                st.success(t("Gmail confirmed that the previous inbox/spam labels were restored."))
            else:
                st.error(outcome["message"])
elif message:
    st.caption(":material/info: " + t("To move this email to spam, use your email app. This connection can read emails but not move them."))

with st.expander(t("Was this result wrong? Tell us"), icon=":material/feedback:"):
    from src.active_learning import redact_personal_data
    st.caption(t("Your correction helps improve the checker. Email addresses and phone numbers are hidden automatically; remove names or anything else private before sending."))
    with st.form("feedback"):
        corrected = st.radio(t("This message is actually"), [t("Legitimate message"), t("Spam message")], horizontal=True)
        reviewed_text = st.text_area(
            t("Message text to send (edit out private details)"),
            value=redact_personal_data(st.session_state.checked_text),
            height=130,
            max_chars=50000,
            help=t("Remove any personal names, physical addresses, or confidential details before sending.")
        )
        comment = st.text_input(t("Why? (optional)"), placeholder=t("e.g. It's a real alert from my bank"))
        st.caption(t("Kept for up to 30 days and reviewed by an administrator before it is used. You can delete it any time in Settings."))
        consent = st.checkbox(t("I agree to share this corrected message with the administrators for review and model training"))
        submitted = st.form_submit_button(t("Send correction"), type="primary", icon=":material/send:")
    if submitted:
        if not consent:
            st.error(t("Explicit consent is required to submit a correction."))
        else:
            try:
                record_feedback(
                    reviewed_text,
                    result.get("report", {}).get("ml_result", {}).get("label", "Unknown"),
                    "ham" if corrected == t("Legitimate message") else "spam",
                    comment,
                    consent_given=True
                )
                st.success(t("Thanks, your correction was saved. An administrator will review it before it is used."), icon=":material/check_circle:")
            except ValueError as error:
                st.error(str(error))
if st.session_state.actions:
    with st.expander(t("Actions taken in this session"), icon=":material/history:"):
        st.dataframe([{k: v for k, v in a.items() if k in {"timestamp", "action", "undone"}} for a in st.session_state.actions], hide_index=True)
st.page_link("app_pages/check.py", label=t("Check another message"), icon=":material/search:")
