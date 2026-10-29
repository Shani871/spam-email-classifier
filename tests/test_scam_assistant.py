import base64
from unittest.mock import Mock
import pytest
from src.scam_assistant import check_message, recovery_steps
from src.security_analyzer import extract_urls
from src.gmail_api import scan_gmail_with_oauth, modify_message_labels
from src.gmail_scanner import scan_gmail_inbox


def test_empty_is_unknown():
    result = check_message("")
    assert result["assessment"] == "Unable to assess"
    assert result["score"] is None


def test_job_fee_has_specific_evidence():
    result = check_message("You are selected for an internship. Pay a registration fee of ₹2,000 to confirm your job.", "Job or internship")
    assert any("Recruitment payment" in e["title"] and "registration fee" in e["excerpt"] for e in result["evidence"])
    assert result["assessment"] in {"Needs verification", "High risk"}


def test_legitimate_job_still_requires_verification_without_fee_claim():
    result = check_message("Thank you for interviewing. We never pay a registration fee. Please review your job offer.", "Job or internship")
    assert not any("Recruitment payment" in e["title"] for e in result["evidence"])
    assert result["assessment"] != "No strong warning found"


def test_supplier_change_is_warning_not_fraud_proof():
    result = check_message("Please pay invoice to account number: 98765432100", "Invoice or payment", previous_text="Please pay invoice to account number: 12345678900")
    evidence = next(e for e in result["evidence"] if "Payment details differ" in e["title"])
    assert "not proof of fraud" in evidence["advice"]


def test_external_recruiter_is_not_automatically_high_risk():
    result = check_message("Thank you for your application. We would like to discuss the role tomorrow.", "Job or internship", sender="recruiter@agency.com", company_domain="employer.com")
    assert any("External recruiters can be legitimate" in e["advice"] for e in result["evidence"])
    assert result["assessment"] == "Needs verification"


def test_single_quoted_html_preserves_hidden_link():
    links = extract_urls("<a class='button' href='https://fraud.example/login'>https://paypal.com</a>")
    assert links[0]["anchor_text"] == "https://paypal.com"
    assert links[0]["url"] == "https://fraud.example/login"


def test_gmail_message_preserves_security_evidence(monkeypatch):
    html = "<a href='https://fraud.example'>https://paypal.com</a>"
    listing = Mock(status_code=200)
    listing.json.return_value = {"messages": [{"id": "abc123"}]}
    detail = Mock(status_code=200)
    detail.json.return_value = {"id": "abc123", "labelIds": ["INBOX"], "payload": {
        "headers": [{"name": "From", "value": "a@example.com"}, {"name": "Authentication-Results", "value": "dkim=fail"}],
        "parts": [{"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(html.encode()).decode()}},
                  {"filename": "invoice.pdf.exe", "mimeType": "application/octet-stream", "body": {"size": 40}}]}}
    get = Mock(side_effect=[listing, detail])
    monkeypatch.setattr("requests.get", get)
    rows = scan_gmail_with_oauth("token", only_unread=True)
    assert "href=" in rows[0]["full_text"]
    assert rows[0]["attachments"][0]["filename"] == "invoice.pdf.exe"
    assert "Authentication-Results" in rows[0]["headers"]
    assert get.call_args_list[0].kwargs["params"]["q"] == "in:inbox is:unread"


def test_failed_gmail_action_is_not_success(monkeypatch):
    monkeypatch.setattr("requests.post", Mock(return_value=Mock(status_code=403)))
    assert modify_message_labels("token", "abc123", ["SPAM"], ["INBOX"])["success"] is False
    with pytest.raises(ValueError):
        modify_message_labels("token", "abc123", ["TRASH"], [])


def test_imap_uses_uid_and_does_not_mark_read(monkeypatch):
    mail = Mock()
    mail.select.return_value = ("OK", [])
    mail.response.return_value = ("UIDVALIDITY", [b"100"])
    mail.uid.side_effect = [("OK", [b"44"]), ("OK", [(b"44", b"From: a@example.com\r\nSubject: Meeting\r\nContent-Type: text/plain\r\n\r\nTeam review tomorrow morning.")])]
    monkeypatch.setattr("imaplib.IMAP4_SSL", Mock(return_value=mail))
    rows = scan_gmail_inbox("user@gmail.com", "testpassword", model_type="svm")
    assert rows[0]["id"] == "44" and rows[0]["uidvalidity"] == "100"
    mail.select.assert_called_once_with("INBOX", readonly=True)
    assert mail.uid.call_args_list[1].args == ("FETCH", b"44", "(BODY.PEEK[])")
    mail.expunge.assert_not_called()


@pytest.mark.parametrize("language", ["English", "Hindi", "Hinglish"])
def test_recovery_guidance_for_money(language):
    steps = recovery_steps("Sent money or payment details", language)
    assert len(steps) >= 3
