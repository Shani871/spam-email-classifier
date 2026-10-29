"""Bounded MIME parsing without opening links or extracting files to disk."""
from email import policy
from email.parser import BytesParser
from src.email_content import html_details

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 100_000
MAX_PARTS = 200
MAX_DEPTH = 20


def parse_email_file(data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Choose a non-empty email file smaller than 10 MB.")
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
    except (RecursionError, ValueError):
        raise ValueError("The email structure could not be read. Export a simpler original message.") from None
    if not message.keys() or not any(message.get(name) for name in ("From", "Subject", "Date", "MIME-Version")):
        raise ValueError("This file does not contain recognizable email headers. Export the original message as .eml.")
    if sum(len(str(value)) for _, value in message.items()) > 50_000:
        raise ValueError("This email has unusually large headers and could not be checked.")
    headers = {}
    warnings = ["Headers in an uploaded email are claims, not verified authentication results."]
    for name in dict.fromkeys(message.keys()):
        values = message.get_all(name, [])
        headers[name] = ", ".join(str(value) for value in values)
        if len(values) > 1 and name.lower() in {"from", "reply-to", "authentication-results", "received-spf"}:
            warnings.append(f"Multiple {name} headers were found; verify the original message with your email provider.")
    plain, html, attachments = [], [], []
    count, text_size = 0, 0

    def visit(part, depth=0):
        nonlocal count, text_size
        count += 1
        if count > MAX_PARTS or depth > MAX_DEPTH:
            raise ValueError("This email has too many nested parts. Choose a simpler exported message.")
        if part.get_filename() or part.get_content_disposition() == "attachment" or part.get_content_type() == "message/rfc822":
            payload = part.get_payload(decode=True) or b""
            attachments.append({"filename": part.get_filename() or "unnamed attachment", "size": len(payload), "mime_type": part.get_content_type()})
            return
        if part.is_multipart():
            for child in part.iter_parts():
                visit(child, depth + 1)
            return
        if part.get_content_type() not in {"text/plain", "text/html"}:
            return
        payload = part.get_payload(decode=True) or b""
        try:
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")
            warnings.append("An unknown text encoding was replaced. Review the message preview for missing characters.")
        text_size += len(text)
        if text_size > MAX_TEXT:
            raise ValueError("The message text is too large to check. Use an email with less than 100,000 characters.")
        (html if part.get_content_type() == "text/html" else plain).append(text)

    visit(message)
    body = "\n".join(dict.fromkeys(plain)).strip()
    html_body = "\n".join(dict.fromkeys(html)).strip()
    display_body = body or html_details(html_body)["text"].strip()
    if not display_body:
        warnings.append("No readable message body found. Only available headers and attachment metadata can be checked.")
    if message.defects:
        warnings.append("The email structure is incomplete or malformed. Some evidence may be unavailable.")
    subject = str(message.get("Subject", "(No subject)"))
    full_text = f"Subject: {subject}\n\n{body or display_body}\n{html_body}".strip() if display_body else ""
    return {"subject": subject, "sender": str(message.get("From", "")), "headers": headers,
            "attachments": attachments, "display_body": display_body, "full_text": full_text, "warnings": list(dict.fromkeys(warnings))}
