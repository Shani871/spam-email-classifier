import streamlit as st
from src.ui_shared import result_required, assessment_card, download_result, step_tracker, md_escape, quote_with_highlight

step_tracker(2)
st.title("Here's what we found")
result = result_required()

message = st.session_state.get("selected_message")
if message:
    st.caption(f":material/mail: {md_escape(message.get('subject', ''))} · {md_escape(message.get('sender', ''))}")

assessment_card(result)
if result.get("sender_verified"):
    st.caption(":material/verified: Your mail provider confirmed this came from the sender's real domain. That proves who sent it, not that the request is safe.")

with st.container(horizontal=True):
    if st.button("What should I do?", type="primary", icon=":material/arrow_forward:"):
        st.switch_page("app_pages/action.py")
    st.page_link("app_pages/check.py", label="Check another message", icon=":material/search:")

conv = result.get("conversation_comparison", {})
if conv.get("has_comparison") and conv.get("differences"):
    st.subheader(":material/compare_arrows: Conversation comparison findings", anchor=False)
    st.caption("What changed since the earlier message. A change is a reason to double-check, not proof of fraud.")
    for diff in conv["differences"]:
        with st.container(border=True):
            st.markdown(f"**{diff['title']}**")
            col_b, col_a = st.columns(2)
            with col_b:
                st.caption("Earlier message")
                st.code(diff["before"], language=None)
            with col_a:
                st.caption("This message")
                st.code(diff["after"], language=None)
            st.markdown(f"**Why it matters:** {diff['why_it_matters']}")
            st.caption(f":material/verified_user: {diff['advice']}")
    if conv.get("verification_checklist"):
        with st.expander("Checklist before you reply", icon=":material/checklist:", expanded=True):
            for step in conv["verification_checklist"]:
                st.markdown(f"- {step}")

from src.multilingual import localize_evidence_item, get_language_limitations
current_lang = st.session_state.get("language", "English")
st.subheader("Why", anchor=False)
if result["evidence"]:
    st.caption(f"{len(result['evidence'])} warning sign(s). Quotes are from the message; the advice is ours.")
    for item in result["evidence"]:
        loc_item = localize_evidence_item(item, current_lang)
        with st.container(border=True):
            st.markdown(f"**:orange[:material/warning:] {loc_item['title']}**")
            if loc_item.get("sentence"):
                st.markdown(quote_with_highlight(loc_item["sentence"], loc_item["excerpt"]))
            elif loc_item.get("excerpt"):
                st.code(loc_item["excerpt"], language=None)
            if loc_item.get("displayed_text"):
                st.caption("The link text shown to you")
                st.code(loc_item["displayed_text"], language=None)
            st.caption(f":material/lightbulb: {loc_item['advice']}  \nSource: {loc_item.get('source', 'Supplied context')}")
else:
    st.markdown(":green[:material/check_circle:] No scam patterns were found in the text, links or attachments.")
    st.caption("We can't confirm who sent it. Be careful with payment or personal details as you normally would.")

if result.get("job_check"):
    with st.expander("How to check a job offer", icon=":material/work:", expanded=True):
        st.markdown("1. Find the job on the employer's official careers page.\n"
                    "2. Contact the employer using details you found yourself, not the ones in the message.\n"
                    "3. Real employers don't ask you to pay to apply, train or join.\n"
                    "4. Don't send ID documents or bank details until you've confirmed the offer.")
        st.link_button("Official job scam guidance", "https://consumer.ftc.gov/articles/job-scams", icon=":material/open_in_new:")

with st.expander("What this check can and can't tell you", icon=":material/info:"):
    all_limitations = list(result.get("limitations", []))
    for lang_lim in get_language_limitations(current_lang):
        if lang_lim not in all_limitations:
            all_limitations.append(lang_lim)
    for limitation in all_limitations:
        st.markdown("- " + limitation)
with st.expander("Technical details", icon=":material/code:"):
    report = result.get("report", {})
    ml = report.get("ml_result", {})
    st.caption(f"Text classifier: {ml.get('label', 'Unknown')} (spam score {ml.get('prob_spam', 'n/a')}, threshold {ml.get('threshold', 'n/a')}). "
               "This describes the wording, not the chance of fraud.")
    st.json({"authentication": report.get("authentication_forensics"), "attachment_metadata": report.get("attachment_forensics"),
             "model": ml.get("model_type")}, expanded=False)
download_result(result)
