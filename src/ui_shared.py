"""Shared view helpers; all private runtime data lives in Session State."""
from datetime import datetime, timedelta, timezone
import json
import os
import streamlit as st
from src.user_storage import read_json, update_json
from src.scam_assistant import check_message, ASSESSMENTS


def auth_configured():
    try:
        return bool(st.secrets.get("auth", {}).get("client_id") or st.secrets.get("auth", {}).get("google", {}).get("client_id"))
    except (FileNotFoundError, KeyError):
        return False


def is_admin():
    if os.environ.get("SPAMGUARD_LOCAL_ADMIN") == "1" and not auth_configured():
        return True
    try:
        email = st.user.get("email", "") if st.user.get("is_logged_in", False) else ""
        return bool(email and st.user.get("email_verified", False) and email in st.secrets.get("app", {}).get("admin_emails", []))
    except (FileNotFoundError, KeyError):
        return os.environ.get("SPAMGUARD_LOCAL_ADMIN") == "1"


def gmail_token():
    if st.session_state.get("gmail_disconnected"):
        return ""
    try:
        return st.user.tokens["access"] or ""
    except (AttributeError, KeyError):
        return ""


def analyze(text, **kwargs):
    from src.monitoring import record_metric, log_security_event, log_error
    result = check_message(text, **kwargs)
    st.session_state["result"] = result
    st.session_state["checked_text"] = text
    try:
        record_metric("checks_performed")
        if result.get("assessment") in {"High risk", "Needs verification"}:
            record_metric("threats_detected")
        log_security_event("MESSAGE_CHECKED", {
            "assessment": result.get("assessment"),
            "score": result.get("score"),
            "category": kwargs.get("category", "General message"),
            "has_attachments": bool(kwargs.get("attachments")),
            "has_comparison": bool(result.get("conversation_comparison", {}).get("has_comparison"))
        })
    except Exception as err:
        log_error(err, context="analyze_monitoring")
    if st.session_state.get("save_history"):
        now = datetime.now(timezone.utc)
        entry = {"timestamp": now.isoformat(), "assessment": result["assessment"], "score": result["score"],
                 "category": result["category"], "expires_at": (now + timedelta(days=st.session_state.get("retention_days", 7))).isoformat()}
        update_json("history.json", [], lambda rows: (rows + [entry])[-100:])
    return result


def result_required():
    result = st.session_state.get("result")
    if not result:
        st.info("Check a message first. Your assessment and next steps will appear here.", icon=":material/info:")
        st.page_link("app_pages/check.py", label="Check a message", icon=":material/search:")
        st.stop()
    return result


def assessment_card(result):
    language = st.session_state.get("language", "English")
    assessment_key = result["assessment"]
    title = ASSESSMENTS.get(language, ASSESSMENTS["English"]).get(assessment_key, assessment_key)
    with st.container(border=True):
        descriptors = {
            "English": {
                "High risk": (":material/report:", "red", "High risk · Action: Stop before paying or sharing details"),
                "Needs verification": (":material/help:", "orange", "Needs verification · Action: Confirm independently"),
                "No strong warning found": (":material/search_check:", "blue", "No strong warning found · Sender is still unverified"),
                "Unable to assess": (":material/info:", "gray", "Unable to assess · More context needed")
            },
            "Hindi": {
                "High risk": (":material/report:", "red", "उच्च जोखिम · कदम: पैसे भेजने या जानकारी साझा करने से पहले रुकें"),
                "Needs verification": (":material/help:", "orange", "पुष्टि आवश्यक · कदम: स्वतंत्र रूप से पुष्टि करें"),
                "No strong warning found": (":material/search_check:", "blue", "कोई बड़ा चेतावनी संकेत नहीं मिला · प्रेषक अभी भी असत्यापित है"),
                "Unable to assess": (":material/info:", "gray", "जाँच के लिए अपर्याप्त जानकारी · अधिक संदर्भ आवश्यक")
            },
            "Hinglish": {
                "High risk": (":material/report:", "red", "Risk zyada hai · Action: Paise dene ya details share karne se pehle ruko"),
                "Needs verification": (":material/help:", "orange", "Pehle verify karein · Action: Independently confirm karein"),
                "No strong warning found": (":material/search_check:", "blue", "Koi strong warning nahi mili · Sender verify nahi hua hai"),
                "Unable to assess": (":material/info:", "gray", "Check karne ke liye jaankari kam hai · Zyada context chahiye")
            }
        }
        icon, color, status_descriptor = descriptors.get(language, descriptors["English"]).get(
            assessment_key, (":material/info:", "gray", assessment_key)
        )
        st.badge(f"{title} — {status_descriptor}", icon=icon, color=color)
        localized_summary = result.get("localized_summaries", {}).get(language, result["summary"])
        st.subheader(localized_summary)
        if result["score"] is not None:
            if language == "Hindi":
                st.caption(f"जोखिम सूचक: {result['score']}/100 · उच्च स्कोर अधिक संदिग्ध संकेतों को दर्शाता है। यह एक संकेतक है, गारंटीकृत निर्णय नहीं।")
            elif language == "Hinglish":
                st.caption(f"Risk indicator: {result['score']}/100 · Score zyada hona matlab zyada suspicious cues mile. Yeh indicator hai, koi guarantee nahi.")
            else:
                st.caption(f"Risk indicator: {result['score']}/100 · Higher score indicates more detected suspicious cues. This is an indicator, not a mathematical probability or a guaranteed verdict.")
        if language != "English":
            st.caption("Key guidance and labels are translated. Technical evidence remains in original English; coverage limitations apply.")


def step_tracker(current_step: int):
    """Horizontal 3-step progress bar shown at the top of every main page."""
    steps = [
        ("Check", "Paste, upload, or connect inbox"),
        ("Understand", "See why it's suspicious"),
        ("Act", "Protect yourself"),
    ]
    parts = ['<div style="display:flex;align-items:flex-start;padding:12px 0 20px;gap:0;width:100%;">']
    for i, (title, desc) in enumerate(steps, 1):
        done, active = i < current_step, i == current_step
        circle_bg = "#22C55E" if done else ("#3B82F6" if active else "#1E293B")
        circle_border = "#22C55E" if done else ("#3B82F6" if active else "#334155")
        num_color = "#fff" if (done or active) else "#475569"
        title_color = "#F8FAFC" if active else ("#22C55E" if done else "#475569")
        desc_color = "#94A3B8" if active else ("#64748B" if done else "#334155")
        label = "✓" if done else str(i)
        parts.append(
            f'<div style="flex:1;text-align:center;">'
            f'<div style="width:32px;height:32px;border-radius:50%;background:{circle_bg};'
            f'border:2px solid {circle_border};color:{num_color};display:inline-flex;'
            f'align-items:center;justify-content:center;font-weight:700;font-size:13px;">{label}</div>'
            f'<div style="font-weight:600;font-size:13px;color:{title_color};margin-top:6px;">{title}</div>'
            f'<div style="font-size:11px;color:{desc_color};margin-top:2px;line-height:1.4;">{desc}</div>'
            f'</div>'
        )
        if i < 3:
            line_color = "#22C55E" if done else "#1E293B"
            parts.append(
                f'<div style="flex:0 0 24px;height:2px;background:{line_color};'
                f'margin-top:15px;align-self:flex-start;border-radius:1px;"></div>'
            )
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def download_result(result):
    export = {key: value for key, value in result.items() if key != "report"}
    st.download_button("Download assessment", json.dumps(export, ensure_ascii=False, indent=2),
                       file_name="spamguard-assessment.json", mime="application/json", icon=":material/download:")
