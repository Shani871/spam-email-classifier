from email.message import EmailMessage
import pytest
from src.eml_reader import parse_email_file
from src.scam_assistant import check_message
from src.evidence import highlight_html


def test_multipart_preserves_hidden_link_and_attachment_metadata():
    message = EmailMessage()
    message["From"] = "Recruiter <hiring@example.com>"
    message["Subject"] = "Internship offer"
    message["Reply-To"] = "pay@another.example"
    message.set_content("Pay a registration fee to confirm your job.")
    message.add_alternative('<a href="https://fraud.example/verify">https://paypal.com</a>', subtype="html")
    message.add_attachment(b"Never execute me", maintype="application", subtype="octet-stream", filename="invoice.pdf.exe")
    parsed = parse_email_file(message.as_bytes())
    assert "href=" in parsed["full_text"]
    assert "Never execute me" not in parsed["full_text"]
    assert parsed["attachments"][0]["filename"] == "invoice.pdf.exe"
    result = check_message(parsed["full_text"], headers=parsed["headers"], attachments=parsed["attachments"])
    assert any(e["source"] == "Link destination" for e in result["evidence"])
    assert any(e["source"] == "Attachment metadata" for e in result["evidence"])
    assert any("reply address" in e["title"] for e in result["evidence"])


def test_html_only_email_shows_plain_preview_without_rendering_images():
    parsed = parse_email_file(b'From: a@example.com\r\nSubject: Test\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Please verify now.</p><img src="https://tracker.example/pixel">')
    assert "Please verify now." in parsed["display_body"]
    assert "<img" not in parsed["display_body"]
    assert "<img" in parsed["full_text"]


def test_unknown_charset_is_recoverable():
    parsed = parse_email_file(b'From: a@example.com\nSubject: Test\nContent-Type: text/plain; charset=not-a-charset\n\nOrdinary project meeting tomorrow.')
    assert "Ordinary project" in parsed["display_body"]
    assert any("unknown text encoding" in w for w in parsed["warnings"])


def test_attachment_only_email_still_checks_filename():
    message = EmailMessage()
    message["From"] = "a@example.com"
    message["Subject"] = "Document"
    message.add_attachment(b"contents", maintype="application", subtype="octet-stream", filename="report.pdf.exe")
    parsed = parse_email_file(message.as_bytes())
    assert not parsed["display_body"]
    result = check_message(parsed["full_text"], headers=parsed["headers"], attachments=parsed["attachments"])
    assert any("Attachment filename" in e["title"] for e in result["evidence"])
    assert result["assessment"] == "Needs verification"


@pytest.mark.parametrize("data", [b"", b"random file text", b"x" * (10 * 1024 * 1024 + 1)])
def test_invalid_or_oversized_files_rejected(data):
    with pytest.raises(ValueError):
        parse_email_file(data)


def test_large_message_text_is_rejected():
    with pytest.raises(ValueError, match="100,000"):
        parse_email_file(b"From: a@example.com\nSubject: Test\n\n" + b"a" * 100001)


def test_highlighting_escapes_untrusted_markup():
    output = highlight_html('<img src="https://evil.example" onerror="alert(1)"> Pay a registration fee.', "registration fee")
    assert "<img" not in output
    assert "&lt;img" in output
    assert "<mark>registration fee</mark>" in output


def test_exact_sentence_and_matched_phrase_are_observed():
    text = "Thanks for applying. Pay a registration fee to confirm your job. We await your reply."
    result = check_message(text, "Job or internship")
    evidence = next(e for e in result["evidence"] if "Recruitment payment" in e["title"])
    assert evidence["sentence"] == "Pay a registration fee to confirm your job."
    assert evidence["excerpt"] in evidence["sentence"]
    assert "Thanks for applying" not in evidence["sentence"]
