"""Every on-screen string passed to t() has Hindi and Hinglish text with the same placeholders."""
import ast
from pathlib import Path
import string

from src.i18n import UI, translate
from src.multilingual import EVIDENCE_LOCALIZATIONS

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "app.py", ROOT / "src" / "ui_shared.py", *sorted((ROOT / "app_pages").glob("*.py"))]
# Labels that only exist as dictionary values in a page (passed to t() indirectly).
INDIRECT = {"Paste text", "Email file", "Screenshot or QR", "My inbox", "General", "Job or internship", "Invoice or payment",
            "Likely scam", "Check first", "Looks normal", "Not sure", "Job scam", "Fake payment", "OTP request",
            "I only received it", "I clicked a link", "I shared a password or code", "I sent money or card details",
            "All", "Needs attention", "Legitimate message", "Spam message", "Trust", "Block", "Remove",
            "Detect from my email address", "Other (enter server)", "Likely a scam", "Check before you act",
            "No warning signs found", "Not enough to go on", "Check", "Result", "What to do",
            "Don't click links, reply, pay, or share codes or passwords.",
            "Confirm with the sender using a phone number or website you already trust.",
            "It looks normal. Stay careful with links and payment requests as usual.",
            "Add more of the message, or the sender's address, and check again.",
            "Message text", "Link destination", "Email header (unverified claim)", "Email headers",
            "Attachment metadata", "Conversation comparison", "Supplied context", "Inbox", "Gmail spam"}


def literal_t_calls():
    found = set()
    for path in FILES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "t" and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    found.add(node.args[0].value)
    return found


def fields(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_ui_string_is_translated():
    used = literal_t_calls() | INDIRECT
    assert len(used) > 150
    missing = sorted(text for text in used if text not in UI)
    assert not missing, f"Add Hindi and Hinglish text to src/i18n.py for: {missing}"
    for text in used:
        for language in ("Hindi", "Hinglish"):
            translated = UI[text].get(language, "")
            assert translated.strip(), f"No {language} text for: {text}"
            assert fields(translated) == fields(text), f"Placeholders differ in {language} for: {text}"


def test_translate_fills_placeholders_and_falls_back_to_english():
    assert translate("{count} emails checked", "Hindi", count=3) == "3 ईमेल जांचे गए"
    assert translate("{count} emails checked", "English", count=3) == "3 emails checked"
    assert translate("Text that has no translation", "Hinglish") == "Text that has no translation"


def test_common_warning_types_are_translated():
    for title in ("Time pressure language", "Threat or security-alert language", "Payment or financial language",
                  "Prize or reward language", "Displayed link and destination differ", "Link destination has warning indicators",
                  "Sender and reply address use different domains", "Attachment filename has warning indicators"):
        for language in ("Hindi", "Hinglish"):
            entry = EVIDENCE_LOCALIZATIONS[title][language]
            assert entry["title"] and entry["advice"]


def test_full_journey_runs_in_hindi_and_hinglish():
    import pytest
    from streamlit.testing.v1 import AppTest
    for language in ("Hindi", "Hinglish"):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
        assert not app.exception, app.exception
        app.selectbox(key="_language_choice").set_value(language).run()
        assert not app.exception
        assert any(translate("Is this message safe?", language) == title.value for title in app.title)
        app.text_area(key="message_input").set_value("You are selected for an internship. Pay a registration fee of Rs 2000 to confirm your job.")
        app.button(key=f"FormSubmitter:message_check-{translate('Check message', language)}").click().run()
        assert not app.exception
        assert app.session_state["result"]["assessment"] in {"High risk", "Needs verification"}
        for page in ["app_pages/understand.py", "app_pages/action.py", "app_pages/settings.py", "app_pages/advanced.py"]:
            app.switch_page(page).run()
            assert not app.exception, (language, page, app.exception)
        app.switch_page("app_pages/understand.py").run()
        markdown = " ".join(m.value for m in app.markdown)
        expected = EVIDENCE_LOCALIZATIONS["Recruitment payment requested"][language]["title"]
        assert expected in markdown, (language, markdown[:500])
        assert translate("Why", language) in [s.value for s in app.subheader]
