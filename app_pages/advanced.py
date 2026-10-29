from pathlib import Path
import json
import pandas as pd
import streamlit as st
from src.ui_shared import is_admin

st.title("Advanced")
st.caption("Optional tools for evaluation, learning, batch checks, and monitoring.")
tool = st.selectbox("Tool", ["Model comparison", "Modern detection benchmark", "Preprocessing inspector", "Batch CSV check", "Feedback and training", "Inbox monitor"])
root = Path(__file__).resolve().parents[1]
if tool == "Modern detection benchmark":
    from src.detection_evaluation import evaluate_detection
    st.subheader("Modern detection evaluation")
    st.caption("A curated evaluation set of realistic modern scams and genuine messages (including urgent business emails, Hindi, and Hinglish).")
    st.info("Synthetic benchmark notice: All test samples are realistic synthetic scenarios based on FTC, CERT-In, and observed fraud patterns. This evaluation does not make unsupported claims of 100% protection against unknown real-world fraud.", icon=":material/info:")
    eval_res = evaluate_detection()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Scenarios", eval_res["total_samples"])
    with col2:
        st.metric("Scams Detected", f"{eval_res['scams_detected']}/{eval_res['total_scams']}", delta=f"{int(eval_res['detection_rate']*100)}%")
    with col3:
        st.metric("Missed Scams", eval_res["missed_scams_count"], help="Scams that received no warning")
    with col4:
        st.metric("False Warnings", eval_res["false_warnings_count"], help="Legitimate messages flagged for verification")
    with col5:
        st.metric("High-Risk False Alarms", eval_res.get("high_risk_false_alarms_count", 0), help="Legitimate messages flagged as High risk")

    st.caption("Benchmark isolation: " + eval_res.get("evaluation_independence_disclosure", "This benchmark is kept strictly separate from the historical training dataset."))

    st.subheader("Results by language")
    lang_rows = []
    for lang, lstats in eval_res["by_language"].items():
        lang_rows.append({
            "Language": lang,
            "Total": lstats["total"],
            "Scams": lstats["scams"],
            "Detected": lstats["scams_detected"],
            "Missed scams": lstats["missed_scams"],
            "Legitimate": lstats["legit"],
            "False warnings": lstats["false_warnings"],
            "High-risk alarms": lstats.get("high_risk_false_alarms", 0),
            "Unable to assess": lstats.get("unable_to_assess", 0)
        })
    st.dataframe(pd.DataFrame(lang_rows), hide_index=True)

    with st.expander("Urgent genuine messages breakdown", expanded=True):
        urg = eval_res["urgent_genuine_breakdown"]
        st.markdown(f"- Total urgent genuine workplace/operational emails: **{urg['total']}**")
        st.markdown(f"- Cleared without high-risk warning: **{urg['cleared_without_high_risk']}**")
        st.markdown(f"- Flagged as high risk: **{urg['flagged_high_risk']}**")
        st.caption("Urgent genuine messages (e.g. server maintenance notices, payroll deadlines) test whether the detector avoids panicking over ordinary urgency.")

    with st.expander("Comparison: Modern ScamGuard vs Historical ML Classifier alone"):
        hist = eval_res["historical_classifier_comparison"]
        st.markdown(f"**Historical classifier alone on this same modern dataset:**")
        st.markdown(f"- Scams detected by ML alone: **{hist['scams_detected']} / {eval_res['total_scams']}** ({int(hist['detection_rate']*100)}%)")
        st.markdown(f"- Modern scams missed by ML alone: **{hist['missed_scams']}**")
        st.markdown(f"- False warnings on genuine emails by ML alone: **{hist['false_warnings']}**")
        st.caption(hist["why_different"])

    if eval_res["false_warnings"]:
        with st.expander(f"Inspect false warnings ({len(eval_res['false_warnings'])})"):
            for fw in eval_res["false_warnings"]:
                st.markdown(f"**{fw['id']}** ({fw['language']} · {fw['scenario']})")
                st.text(fw["text"])
                st.caption(f"Assessment: {fw['assessment']} · Score: {fw['score']}")
    if eval_res["missed_scams"]:
        with st.expander(f"Inspect missed scams ({len(eval_res['missed_scams'])})"):
            for ms in eval_res["missed_scams"]:
                st.markdown(f"**{ms['id']}** ({ms['language']} · {ms['scenario']})")
                st.text(ms["text"])
                st.caption(f"Assessment: {ms['assessment']} · Score: {ms['score']}")
elif tool == "Model comparison":
    active = root / "models" / "active.json"
    folder = root / "models"
    if active.exists():
        version = json.loads(active.read_text())["version"]
        folder = folder / "versions" / version if version != "baseline" else folder
    metrics_path = folder / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text())
        st.caption(f"Recorded evaluation: {metrics['test_samples']:,} examples. This benchmark does not establish modern scam detection accuracy.")
        rows = [{"Model": value["display_name"], "Accuracy": value["accuracy"], "Spam precision": value["precision_spam"], "Spam recall": value["recall_spam"], "False positives": value["confusion_matrix"]["false_positive"]} for value in metrics["models"].values()]
        st.dataframe(rows, hide_index=True)
        for name, value in metrics["models"].items():
            with st.expander(value["display_name"]):
                st.json(value["confusion_matrix"])
                st.bar_chart(pd.DataFrame(value["top_features"]["spam_keywords"][:10]).set_index("word"))
    else:
        st.warning("No recorded evaluation found. Train the baseline using the documented setup instructions.")
elif tool == "Preprocessing inspector":
    from src.preprocessing import inspect_preprocessing_steps
    with st.form("preprocess"):
        text = st.text_area("Message to inspect")
        submitted = st.form_submit_button("Inspect text")
    if submitted:
        st.json(inspect_preprocessing_steps(text))
elif tool == "Batch CSV check":
    from src.scam_assistant import check_message
    uploaded = st.file_uploader("CSV with a text column", type=["csv"], max_upload_size=5)
    if uploaded:
        try:
            frame = pd.read_csv(uploaded)
            if "text" not in frame.columns:
                st.warning("Add a column named text to your CSV.")
            elif len(frame) > 500:
                st.warning("Check up to 500 messages per file.")
            elif st.button("Check batch", type="primary"):
                with st.spinner("Checking messages…"):
                    rows = [check_message(str(text)[:50000] if pd.notna(text) else "") for text in frame.text]
                    frame["assessment"] = [r["assessment"] for r in rows]
                    frame["risk_indicator"] = [r["score"] for r in rows]
                st.dataframe(frame[["assessment", "risk_indicator"]], hide_index=True)
                # Neutralize spreadsheet formulas in every exported string column.
                safe = frame.map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
                st.download_button("Download checked CSV", safe.to_csv(index=False), "checked-messages.csv", "text/csv")
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError, FileNotFoundError):
            st.error("This CSV could not be checked. Verify the format and model setup.")
elif tool == "Feedback and training":
    from src.active_learning import (
        get_feedback_records,
        get_admin_feedback_queue,
        approve_feedback,
        reject_feedback,
        withdraw_feedback_consent,
        delete_feedback_record,
        retrain_model_with_feedback,
        rollback_model,
        get_trainable_feedback
    )
    user_rows = get_feedback_records()
    st.subheader("Your corrections")
    st.caption("Corrections submitted in this account. Deleting feedback removes it from your storage and the review queue.")
    st.info("Consent & Model Limitations: Deleting stored feedback removes it from the review queue and future model training, but does NOT retroactively remove its influence from an already trained and deployed model release. To revert a deployed release, an administrator must perform a model rollback.", icon=":material/privacy_tip:")
    if not user_rows:
        st.info("No saved corrections in this account. Add one from Take action.")
    else:
        st.dataframe(user_rows, hide_index=True)
        with st.expander("Manage your saved feedback"):
            manage_id = st.selectbox("Choose a submission to manage", [r["id"] for r in user_rows], format_func=lambda i: next(f"[{r.get('user_label', '').upper()}] {r['text'][:60]}…" for r in user_rows if r["id"] == i))
            rec_to_manage = next(r for r in user_rows if r["id"] == manage_id)
            col_w, col_d = st.columns(2)
            with col_w:
                if rec_to_manage.get("consent_given", False):
                    if st.button("Withdraw consent", help="Immediately removes this submission from administrator review"):
                        withdraw_feedback_consent(manage_id)
                        st.success("Consent withdrawn. This item will not be used in future training.")
                        st.rerun()
                else:
                    st.caption("Consent is not granted for this submission.")
            with col_d:
                if st.button("Delete feedback record", type="secondary"):
                    delete_feedback_record(manage_id)
                    st.success("Feedback permanently deleted from storage.")
                    st.rerun()

    if is_admin():
        st.divider()
        st.subheader("Administrator Review Queue")
        st.caption("Authorized review queue. Submissions appear here ONLY if the user gave explicit consent. Missing consent strictly defaults to false.")
        admin_queue = get_admin_feedback_queue(admin_user=True)
        pending = [r for r in admin_queue if not r.get("approved") and not r.get("rejected") and r.get("consent_given", False)]
        if not pending:
            st.info("No pending consented feedback awaiting administrator review.")
        else:
            st.dataframe(pending, hide_index=True)
            selected = st.selectbox("Correction to review (consented only)", [r["id"] for r in pending], format_func=lambda ident: next(f"[{r.get('user_label', '').upper()}] {r['text'][:90]}…" for r in pending if r["id"] == ident))
            chosen_record = next(r for r in pending if r["id"] == selected)
            st.text_area("Reviewed message content (anonymized)", value=chosen_record["text"], disabled=True)
            st.caption(f"User label: {chosen_record.get('user_label')} · Model predicted: {chosen_record.get('predicted_label')} · Explicit consent: Verified")
            col_app, col_rej = st.columns(2)
            with col_app:
                if st.button("Approve reviewed correction", type="primary"):
                    approve_feedback(selected, admin_user=True)
                    st.success("Correction approved for future model candidate training.")
                    st.rerun()
            with col_rej:
                reject_reason = st.text_input("Rejection reason (optional)", key=f"rej_reason_{selected}", placeholder="e.g. Inconclusive or ambiguous")
                if st.button("Reject correction", type="secondary"):
                    reject_feedback(selected, admin_user=True, reason=reject_reason)
                    st.warning("Correction rejected. It will not be used in future training.")
                    st.rerun()

        st.subheader("Model release management")
        trainable_count = len(get_trainable_feedback())
        st.caption(f"Currently eligible approved & consented corrections ready for training: **{trainable_count}**.")
        confirmed = st.checkbox("Release the candidate only if it passes the fixed evaluation gates")
        if st.button("Train and evaluate candidate", disabled=not confirmed, type="primary"):
            with st.spinner("Training and evaluating a candidate model…"):
                outcome = retrain_model_with_feedback(admin_user=True)
            (st.success if outcome["success"] else st.warning)(outcome["message"])
        if st.button("Roll back the last model release"):
            if rollback_model(admin_user=True):
                st.success("Previous model restored.")
            else:
                st.info("No previous release is available.")
    else:
        st.caption("An administrator must review feedback across accounts and release models. Deployment setup is described in docs/SETUP.md.")
elif tool == "Inbox monitor":
    from src.automation_worker import InboxAutomationWorker
    if st.session_state.worker is None:
        st.session_state.worker = InboxAutomationWorker(user_id=st.session_state.identity)
    worker = st.session_state.worker
    st.caption("Monitoring runs while this app process is alive. It recommends actions and never moves emails automatically. Logs stay in this session. Each run stops after 15 minutes.")
    mode = st.radio("Feed", ["Demo messages", "Connected app-password inbox"], horizontal=True)
    if mode == "Connected app-password inbox":
        credentials = st.session_state.get("imap_credentials")
        if not credentials:
            st.info("Connect with an app password in Settings first. OAuth inbox checks are available on Check a message.")
            st.stop()
        if worker.email_address != credentials["email_address"]:
            worker.stop()
            worker.configure_credentials(**credentials)
    elif worker.email_address:
        worker.stop()
        worker.configure_credentials("", "")
    seconds = st.slider("Seconds between checks", 15, 120, 30, 15)
    worker.set_interval(seconds)
    with st.container(horizontal=True):
        if st.button("Check once"):
            with st.spinner("Checking the feed…"):
                worker.scan_once()
        if st.button("Start monitor", disabled=worker.is_running()):
            worker.start()
        if st.button("Stop monitor", disabled=not worker.is_running()):
            worker.stop()
        if st.button("Clear monitor history"):
            worker.clear_audit_logs()
    @st.fragment(run_every="10s")
    def monitor_status():
        stats = worker.get_stats()
        st.caption(f"Status: {stats['status']} · Checked: {stats['total_scanned']} · Quarantine recommended: {stats.get('quarantine_recommended', 0)}")
        logs = worker.get_recent_audit_logs()
        if logs:
            st.dataframe([{k: r[k] for k in ["timestamp", "mode", "subject", "action", "threat_score"]} for r in logs], hide_index=True)
    monitor_status()
