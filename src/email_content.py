"""Keep message text and security evidence separate from display formatting."""
from html import unescape
from html.parser import HTMLParser
from email.utils import parseaddr
from urllib.parse import urlsplit


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.text = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.active = {"url": dict(attrs).get("href", ""), "anchor_text": "", "is_html_link": True}

    def handle_data(self, data):
        self.text.append(data)
        if self.active is not None:
            self.active["anchor_text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.active is not None:
            url = (self.active.get("url") or "").strip()
            if url and not url.lower().startswith(("data:", "javascript:", "mailto:", "tel:")):
                self.links.append(self.active)
            self.active = None


def html_details(html):
    parser = LinkParser()
    parser.feed(html)
    return {"text": unescape(" ".join(parser.text)), "links": parser.links}


def address_domain(address):
    parsed = parseaddr(address or "")[1]
    return parsed.rsplit("@", 1)[-1].lower() if "@" in parsed else ""


def domain_from_url(url):
    try:
        return (urlsplit(url if "://" in url else "https://" + url).hostname or "").encode("idna").decode().lower()
    except (ValueError, UnicodeError):
        return ""


def belongs_to(domain, expected):
    return bool(domain and expected and (domain == expected or domain.endswith("." + expected)))


def payload_metadata(payload):
    attachments, html_bodies = [], []
    from src.gmail_api import decode_base64url
    def visit(part):
        if part.get("filename"):
            attachments.append({"filename": part["filename"], "size": part.get("body", {}).get("size", 0), "mime_type": part.get("mimeType", "")})
        elif part.get("mimeType") == "text/html":
            html_bodies.append(decode_base64url(part.get("body", {}).get("data", "")))
        for child in part.get("parts", []):
            visit(child)
    visit(payload)
    return attachments, "\n".join(html_bodies)
