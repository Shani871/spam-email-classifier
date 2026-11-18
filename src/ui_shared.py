"""Shared view helpers; all private runtime data lives in Session State."""
from datetime import datetime, timedelta, timezone
import json
import os
import streamlit as st
from src import user_storage
from src.scam_assistant import check_message
from src.i18n import t


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
        user_storage.add_history(result["assessment"], result["score"], result["category"],
                                 retention_days=st.session_state.get("retention_days", 7))
    return result


def result_required():
    result = st.session_state.get("result")
    if not result:
        with st.container(border=True, horizontal_alignment="center"):
            st.info(t("Check a message first. Your result and next steps will appear here."), icon=":material/info:")
            st.page_link("app_pages/check.py", label=t("Check a message"), icon=":material/search:")
        st.stop()
        raise SystemExit(0)
    return result


# Plain-language verdicts (English keys; translated through src/i18n.py).
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
    key = result["assessment"]
    kind, icon, title, action = VERDICTS.get(key, VERDICTS["Unable to assess"])
    getattr(st, kind)(f"**{t(title)}**  \n{t(action)}", icon=icon)
    if result.get("score") is not None and not compact:
        score = int(result["score"])
        color = {"error": "red", "warning": "orange", "success": "green"}.get(kind, "gray")
        st.markdown(f":{color}-badge[:material/speed: {t('Risk indicator')}: {score}/100]")
        st.caption(t("Higher means more warning signs were found. It is an indicator, not a guarantee."))
    if st.session_state.get("language", "English") != "English":
        st.caption(t("Quotes from the message and some technical details stay in their original language."))


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
        label = t(title)
        if index < current_step and has_result:
            parts.append(f":green-badge[:material/check: {label}]")
        elif index == current_step:
            parts.append(f":blue-badge[{icon} {index}. {label}]")
        else:
            parts.append(f":gray-badge[{index}. {label}]")
    st.markdown(" :material/chevron_right: ".join(parts))


def download_result(result):
    export = {key: value for key, value in result.items() if key != "report"}
    st.download_button(t("Download this result"), json.dumps(export, ensure_ascii=False, indent=2),
                       file_name="spamguard-assessment.json", mime="application/json", icon=":material/download:")
