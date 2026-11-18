"""Shared view helpers; all private runtime data lives in Session State."""
from datetime import datetime, timedelta, timezone
import json
import os
import streamlit as st
from src.user_storage import read_json, update_json
from src.scam_assistant import check_message, ASSESSMENTS


def md_escape(value):
    """Neutralise Markdown in untrusted text (email subjects, senders, link text) so it
    cannot render links or remote images when shown with st.markdown or st.caption."""
    import re
    return re.sub(r"([\\`*_{}\[\]()#+!|<>~$:-])", r"\\\1", str(value or "")).replace("\n", " ")


def auth_configured():
    try:
        return bool(st.secrets.get("auth", {}).get("client_id") or st.secrets.get("auth", {}).get("google", {}).get("client_id"))
    except (FileNotFoundError, KeyError):
        return False


def local_admin_enabled():
    """Development-only switch. It is ignored when SPAMGUARD_ENV=production."""
    return os.environ.get("SPAMGUARD_LOCAL_ADMIN") == "1" and os.environ.get("SPAMGUARD_ENV") != "production"


def is_admin():
    if local_admin_enabled() and not auth_configured():
        return True
    try:
        email = st.user.get("email", "") if st.user.get("is_logged_in", False) else ""
        return bool(email and st.user.get("email_verified", False) and email in st.secrets.get("app", {}).get("admin_emails", []))
    except (FileNotFoundError, KeyError):
        return local_admin_enabled()


def gmail_token():
    if st.session_state.get("gmail_disconnected"):
        return ""
    try:
        return st.user.tokens["access"] or ""
    except (AttributeError, KeyError):
        return ""


def connect_inbox(email_address, app_password, **kwargs):
    """Rate-limited mailbox connection test. Limits apply per caller and per target mailbox."""
    from src.gmail_scanner import verify_inbox_connection
    from src.rate_limit import RateLimitExceeded, enforce, limiter
    target = str(email_address or "").strip().lower()
    if target != "demo@spamguard.local":
        try:
            enforce("inbox_connect", st.session_state.get("identity", ""))
            limiter.hit("inbox_connect_target", target)
        except RateLimitExceeded as error:
            return {"success": False, "error_type": "RATE_LIMITED", "message": str(error), "provider": "", "host": "",
                    "troubleshooting": "Connection attempts are limited to protect mailboxes from password guessing."}
    return verify_inbox_connection(email_address, app_password, **kwargs)


def analyze(text, **kwargs):
    from src.monitoring import record_metric, log_security_event, log_error
    from src.rate_limit import enforce
    enforce("check", st.session_state.get("identity", ""))
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
        with st.container(border=True, horizontal_alignment="center"):
            st.info("Check a message first. Your result and next steps will appear here.", icon=":material/info:")
            st.page_link("app_pages/check.py", label="Check a message", icon=":material/search:")
        st.stop()
        raise SystemExit(0)
    return result


# Plain-language verdicts. Hindi and Hinglish fall back to the translated labels below.
VERDICTS = {
    "High risk": ("error", ":material/gpp_bad:", "Likely a scam",
                  "Don't click links, reply, pay, or share codes or passwords."),
    "Needs verification": ("warning", ":material/help:", "Check before you act",
                           "Confirm with the sender using a phone number or website you already trust."),
    "No strong warning found": ("success", ":material/verified_user:", "No warning signs found",
                                "It looks normal. Stay careful with links and payment requests as usual."),
    "Unable to assess": ("info", ":material/info:", "Not enough to go on",
                         "Add more of the message, or the sender's address, and check again."),
}

_TRANSLATED_ACTIONS = {
    "Hindi": {
        "High risk": "पैसे भेजने या जानकारी साझा करने से पहले रुकें",
        "Needs verification": "स्वतंत्र रूप से पुष्टि करें",
        "No strong warning found": "प्रेषक अभी भी असत्यापित है",
        "Unable to assess": "अधिक संदर्भ आवश्यक",
    },
    "Hinglish": {
        "High risk": "Paise dene ya details share karne se pehle ruko",
        "Needs verification": "Independently confirm karein",
        "No strong warning found": "Sender verify nahi hua hai",
        "Unable to assess": "Zyada context chahiye",
    },
}


def quote_with_highlight(sentence, match):
    """A quoted sentence with the matched words highlighted, as escaped Markdown (theme-aware)."""
    position = sentence.lower().find((match or "").lower()) if match else -1
    if position < 0:
        return f"> {md_escape(sentence)}"
    end = position + len(match)
    return (f"> {md_escape(sentence[:position])}:orange-background[**{md_escape(sentence[position:end])}**]"
            f"{md_escape(sentence[end:])}")


def assessment_card(result, compact=False):
    """The verdict in one coloured box: what it is, and what to do now. `compact` hides the score."""
    language = st.session_state.get("language", "English")
    key = result["assessment"]
    kind, icon, title, action = VERDICTS.get(key, VERDICTS["Unable to assess"])
    if language != "English":
        title = ASSESSMENTS.get(language, ASSESSMENTS["English"]).get(key, key)
        action = _TRANSLATED_ACTIONS.get(language, {}).get(key, action)
    getattr(st, kind)(f"**{title}**  \n{action}", icon=icon)
    if result.get("score") is not None and not compact:
        score = int(result["score"])
        label = {"English": "Risk indicator", "Hindi": "जोखिम सूचक", "Hinglish": "Risk indicator"}.get(language, "Risk indicator")
        color = {"error": "red", "warning": "orange", "success": "green"}.get(kind, "gray")
        st.markdown(f":{color}-badge[:material/speed: {label}: {score}/100]")
        st.caption({
            "Hindi": "उच्च स्कोर का मतलब अधिक संदिग्ध संकेत। यह एक संकेतक है, गारंटीकृत निर्णय नहीं।",
            "Hinglish": "Score zyada matlab zyada suspicious cues. Yeh indicator hai, guarantee nahi.",
        }.get(language, "Higher means more warning signs were found. It is an indicator, not a guarantee."))
    if language != "English":
        st.caption("Key guidance and labels are translated. Technical evidence remains in original English; coverage limitations apply.")


STEPS = [
    ("Check", ":material/search:"),
    ("Result", ":material/fact_check:"),
    ("What to do", ":material/task_alt:"),
]


def step_tracker(current_step: int):
    """Compact progress line shown at the top of the three main pages."""
    parts = []
    has_result = bool(st.session_state.get("result"))
    for index, (title, icon) in enumerate(STEPS, 1):
        if index < current_step and has_result:
            parts.append(f":green-badge[:material/check: {title}]")
        elif index == current_step:
            parts.append(f":blue-badge[{icon} {index}. {title}]")
        else:
            parts.append(f":gray-badge[{index}. {title}]")
    st.markdown(" :material/chevron_right: ".join(parts))


def download_result(result):
    export = {key: value for key, value in result.items() if key != "report"}
    st.download_button("Download this result", json.dumps(export, ensure_ascii=False, indent=2),
                       file_name="spamguard-assessment.json", mime="application/json", icon=":material/download:")
