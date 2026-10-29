from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_three_step_flow_preserves_result():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    assert len(app.tabs) == 0
    app.text_area(key="message_input").set_value("You are selected for an internship. Pay a registration fee to confirm your job.")
    app.button(key="FormSubmitter:message_check-Check message").click().run()
    assert not app.exception
    assert app.session_state["result"]["assessment"] in {"High risk", "Needs verification"}
    result = app.session_state["result"]
    for page in ["app_pages/action.py", "app_pages/settings.py", "app_pages/advanced.py", "app_pages/check.py", "app_pages/understand.py"]:
        app.switch_page(page).run()
        assert not app.exception
        assert app.session_state["result"] == result


def test_empty_submit_and_no_result_actions():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app.button(key="FormSubmitter:message_check-Check message").click().run()
    assert app.warning
    assert app.session_state["result"] is None
    app.switch_page("app_pages/action.py").run()
    assert not app.exception
    assert any("Check a message first" in item.value for item in app.info)


def test_privacy_preferences_and_submitted_draft_survive_navigation():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app.switch_page("app_pages/settings.py").run()
    app.toggle(key="_save_history").set_value(True).run()
    app.switch_page("app_pages/check.py").run()
    assert app.session_state["save_history"] is True
    text = "Hi team, the project review is tomorrow morning."
    app.text_area(key="message_input").set_value(text)
    app.button(key="FormSubmitter:message_check-Check message").click().run()
    app.switch_page("app_pages/check.py").run()
    assert app.text_area(key="message_input").value == text
    assert not app.exception


def test_conversation_comparison_ui_flow():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
    assert not app.exception
    # Current message with new payment details and changed domain
    app.text_area(key="message_input").set_value("Please remit payment to our new UPI handle vendor@okhdfcbank.")
    app.text_input(key="current_sender_input").set_value("billing@vendor-update.com")

    # Earlier message in thread with original account and original sender
    app.text_area(key="previous_message_input").set_value("Invoice #101: Please pay to our standard account 1234567890.")
    app.text_input(key="previous_sender_input").set_value("billing@vendor.com")

    app.button(key="FormSubmitter:message_check-Check message").click().run()
    assert not app.exception
    assert app.session_state["result"] is not None

    conv = app.session_state["result"].get("conversation_comparison", {})
    assert conv.get("has_comparison") is True
    assert len(conv.get("differences", [])) >= 1

    app.switch_page("app_pages/understand.py").run()
    assert not app.exception
    assert any("Conversation comparison findings" in s.value for s in app.subheader)
    
    # Assert displayed differences in markdown/code containers
    displayed_markdown = " ".join(m.value for m in app.markdown)
    displayed_code = " ".join(c.value for c in app.code)
    assert "okhdfcbank" in displayed_code or "okhdfcbank" in displayed_markdown or "Payment" in displayed_markdown

    app.switch_page("app_pages/action.py").run()
    assert not app.exception


def test_advanced_detection_benchmark_ui_flow():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
    app.switch_page("app_pages/advanced.py").run()
    assert not app.exception
    # Select the Modern detection benchmark tool
    app.selectbox[0].select("Modern detection benchmark").run()
    assert not app.exception
    assert any("Modern detection evaluation" in s.value for s in app.subheader)

