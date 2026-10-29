import streamlit as st
from src.ui_shared import result_required, assessment_card, download_result
from src.evidence import highlight_html

st.caption("02 / UNDERSTAND")
st.title("Understand the warning")
result = result_required()
assessment_card(result)
if st.button("Choose next steps", type="primary", icon=":material/arrow_forward:", width="stretch"):
    st.switch_page("app_pages/action.py")
conv = result.get("conversation_comparison", {})
if conv.get("has_comparison") and conv.get("differences"):
    st.subheader(":material/compare_arrows: Conversation comparison findings")
    st.caption("Observed differences between earlier messages and this message. Treat changes as reasons to verify, not automatic proof of fraud.")
    for diff in conv["differences"]:
        with st.container(border=True):
            st.markdown(f"**{diff['title']}**")
            col_b, col_a = st.columns(2)
            with col_b:
                st.caption("Earlier message (Before)")
                st.code(diff["before"], language=None)
            with col_a:
                st.caption("Current message (After)")
                st.code(diff["after"], language=None)
            st.markdown(f"**Why this change may matter:** {diff['why_it_matters']}")
            st.info(f"**Verification step:** {diff['advice']}", icon=":material/verified_user:")
    if conv.get("verification_checklist"):
        with st.expander("Verification checklist before responding", expanded=True):
            for step in conv["verification_checklist"]:
                st.markdown(f"- {step}")

st.subheader("Why this result?")
from src.multilingual import localize_evidence_item, get_language_limitations
current_lang = st.session_state.get("language", "English")
if result["evidence"]:
    for item in result["evidence"]:
        loc_item = localize_evidence_item(item, current_lang)
        with st.container(border=True):
            st.markdown(f"**{loc_item['title']}**")
            st.caption("Observed evidence · " + loc_item.get("source", "Supplied context"))
            if loc_item.get("sentence"):
                st.html(highlight_html(loc_item["sentence"], loc_item["excerpt"]))
            elif loc_item.get("excerpt"):
                st.text(loc_item["excerpt"])
            if loc_item.get("displayed_text"):
                st.caption("Displayed link text")
                st.text(loc_item["displayed_text"])
            st.caption("Interpretation and next step")
            st.text(loc_item["advice"])
else:
    st.markdown("No specific warning evidence was found. Verify the sender independently before sharing money or sensitive information.")
if result.get("job_check"):
    with st.expander("Verify a job offer", expanded=True):
        st.markdown("1. Find the vacancy on the employer's official careers page.\n2. Contact the employer using contact details you found independently.\n3. Verify the recruiter and the purpose of any document request.\n4. Pause if asked to pay for recruitment or forward money from a check.")
        st.link_button("Read official job scam guidance", "https://consumer.ftc.gov/articles/job-scams")
with st.expander("What this check can and cannot tell you"):
    all_limitations = list(result.get("limitations", []))
    for lang_lim in get_language_limitations(current_lang):
        if lang_lim not in all_limitations:
            all_limitations.append(lang_lim)
    for limitation in all_limitations:
        st.markdown("- " + limitation)
with st.expander("Technical details"):
    report = result.get("report", {})
    ml = report.get("ml_result", {})
    st.caption(f"Spam classification: {ml.get('label', 'Unknown')}. Spam probability describes the classifier output, not the probability of fraud.")
    st.json({"authentication": report.get("authentication_forensics"), "attachment_metadata": report.get("attachment_forensics"), "model": ml.get("model_type")})
with st.container(horizontal=True):
    st.page_link("app_pages/action.py", label="Take action", icon=":material/arrow_forward:")
    st.page_link("app_pages/check.py", label="Check another message", icon=":material/search:")
download_result(result)
