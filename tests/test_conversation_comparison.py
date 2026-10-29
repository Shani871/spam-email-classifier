"""Unit tests for conversation comparison between earlier and newer messages.

Includes regression tests for:
- Ordinary email addresses NOT treated as UPI IDs
- Words like "DETAILS" NOT extracted as account identifiers
- Negation handling: "Never share your password" is NOT a request
- Same-domain link change detection
- Scoring consistency between comparison engine and assessment
- Honest missing-field summaries
"""
import pytest
from src.conversation_comparison import (
    compare_conversations,
    extract_payment_indicators,
    extract_sensitive_requests,
)
from src.scam_assistant import check_message


def test_no_earlier_message():
    comp = compare_conversations(earlier_text="", newer_text="Hello, here is your project update.")
    assert comp["has_comparison"] is False
    assert comp["differences"] == []


def test_sender_domain_change():
    comp = compare_conversations(
        earlier_text="Thanks for your partnership.",
        newer_text="Please find the revised terms.",
        earlier_sender="Alice Smith <alice@partner.com>",
        newer_sender="Alice Smith <alice@partner-security.com>"
    )
    assert comp["has_comparison"] is True
    diffs = [d for d in comp["differences"] if d["category"] == "sender"]
    assert len(diffs) == 1
    assert "domain changed" in diffs[0]["title"]
    assert diffs[0]["before"] == "alice@partner.com"
    assert diffs[0]["after"] == "alice@partner-security.com"
    assert "Treat changes as reasons to verify, not automatic proof of fraud." in comp["disclaimer"]


def test_reply_to_divergence():
    comp = compare_conversations(
        earlier_text="Let's confirm the agenda.",
        newer_text="Confirm your attendance.",
        newer_sender="executive@bigcorp.com",
        newer_reply_to="assistant-temp@fastmail.com"
    )
    assert comp["has_comparison"] is True
    diffs = [d for d in comp["differences"] if d["category"] == "reply_to"]
    assert len(diffs) == 1
    assert "different domain" in diffs[0]["title"]
    assert "assistant-temp@fastmail.com" in diffs[0]["after"]


def test_payment_detail_change():
    earlier = "Our standard payment terms: send to A/C: 1234567890."
    newer = "Please note our updated banking details: A/C: 9876543210. Kindly remit immediately."
    comp = compare_conversations(earlier_text=earlier, newer_text=newer)
    assert comp["has_comparison"] is True
    diffs = [d for d in comp["differences"] if d["category"] == "payment"]
    assert len(diffs) >= 1
    assert "Payment details changed" in diffs[0]["title"]
    assert "1234567890" in diffs[0]["before"]
    assert "9876543210" in diffs[0]["after"]
    assert "A change alone is not proof of fraud" in diffs[0]["advice"]


def test_upi_payment_introduction():
    earlier = "Discussion on consulting scope."
    newer = "Please transfer the initial deposit to vendor@okaxis via UPI."
    comp = compare_conversations(earlier_text=earlier, newer_text=newer)
    diffs = [d for d in comp["differences"] if d["category"] == "payment"]
    assert len(diffs) >= 1
    assert "vendor@okaxis" in diffs[0]["after"]


def test_new_links_introduced():
    earlier = "Review the documents on our company intranet."
    newer = "Click here to view our new vendor portal at https://secure-files-drop.xyz/login."
    comp = compare_conversations(earlier_text=earlier, newer_text=newer)
    diffs = [d for d in comp["differences"] if d["category"] == "links"]
    assert len(diffs) >= 1
    assert "secure-files-drop.xyz" in diffs[0]["after"]


def test_sensitive_info_request_escalation():
    earlier = "Nice to meet you yesterday. We are drafting the candidate paperwork."
    newer = "To finalize your onboarding, please reply with your Aadhaar, bank details, and the OTP sent to your phone."
    comp = compare_conversations(earlier_text=earlier, newer_text=newer)
    diffs = [d for d in comp["differences"] if d["category"] == "sensitive_request"]
    assert len(diffs) >= 1
    assert "sensitive information" in diffs[0]["title"].lower()
    assert "OTP" in diffs[0]["after"] or "Aadhaar" in diffs[0]["after"]


def test_scam_assistant_integration():
    res = check_message(
        "Urgent: send the payment to our new UPI ID billing@okhdfcbank right now.",
        category="Invoice or payment",
        sender="billing@supplier-update.com",
        previous_text="Thank you for your order. Previous bank account was A/C: 4444555566.",
        previous_sender="billing@supplier.com"
    )
    assert res["conversation_comparison"]["has_comparison"] is True
    assert len(res["conversation_comparison"]["differences"]) >= 2
    # Check that reasons to verify advice is present
    for diff in res["conversation_comparison"]["differences"]:
        assert diff["severity"] in {"Needs verification", "Informational"}
    assert "conversation_comparison" in res


# ─── REGRESSION TESTS ───


class TestOrdinaryEmailNotUPI:
    """billing@vendor.com must NOT be treated as a UPI ID."""

    def test_ordinary_email_not_extracted_as_payment(self):
        indicators = extract_payment_indicators(
            "Contact billing@vendor.com for invoice queries."
        )
        values = [p["value"] for p in indicators]
        assert "billing@vendor.com" not in values
        # Also test other ordinary addresses
        indicators2 = extract_payment_indicators(
            "Send questions to support@company.org or hr@firm.co.in"
        )
        values2 = [p["value"] for p in indicators2]
        assert not any("@" in v and "." in v.split("@")[-1] for v in values2)

    def test_real_upi_is_still_detected(self):
        indicators = extract_payment_indicators(
            "Send payment to merchant@okaxis"
        )
        values = [p["value"] for p in indicators]
        assert "merchant@okaxis" in values

    def test_email_in_conversation_not_payment_diff(self):
        """An ordinary email mentioned in both messages should not trigger payment diff."""
        comp = compare_conversations(
            earlier_text="Contact billing@vendor.com for support.",
            newer_text="Reach out to billing@vendor.com regarding your order."
        )
        payment_diffs = [d for d in comp["differences"] if d["category"] == "payment"]
        assert len(payment_diffs) == 0


class TestAccountWordExtraction:
    """Words like 'DETAILS' from 'account details' must NOT be extracted."""

    def test_details_not_extracted(self):
        indicators = extract_payment_indicators(
            "Please share your account details for verification."
        )
        values = [p["value"] for p in indicators]
        assert "DETAILS" not in values

    def test_number_not_extracted_without_separator(self):
        indicators = extract_payment_indicators(
            "Check your account number for accuracy."
        )
        values = [p["value"] for p in indicators]
        # "NUMBER" should not be extracted as an identifier
        assert "NUMBER" not in values

    def test_real_account_with_separator_is_detected(self):
        indicators = extract_payment_indicators(
            "Transfer to A/C: 9876543210"
        )
        values = [p["value"] for p in indicators]
        assert "9876543210" in values


class TestNegationHandling:
    """'Never share your password or OTP' must NOT classify as sharing request."""

    def test_never_share_password_not_flagged(self):
        results = extract_sensitive_requests(
            "Never share your password or OTP with anyone."
        )
        assert results == []

    def test_do_not_share_not_flagged(self):
        results = extract_sensitive_requests(
            "Do not share your bank account details or PIN."
        )
        assert results == []

    def test_hindi_negation_not_flagged(self):
        results = extract_sensitive_requests(
            "कभी नहीं भेजें अपना पासवर्ड या ओटीपी।"
        )
        assert results == []

    def test_actual_request_still_flagged(self):
        results = extract_sensitive_requests(
            "Please share your password and OTP to verify your account."
        )
        assert len(results) >= 1
        assert "Password or PIN" in results or "One-Time Password (OTP)" in results

    def test_negation_in_comparison(self):
        """A safety advisory in the newer message should not trigger sensitive_request diff."""
        comp = compare_conversations(
            earlier_text="Welcome to our platform.",
            newer_text="Important: Never share your password or OTP with anyone, including our staff."
        )
        sensitive_diffs = [d for d in comp["differences"] if d["category"] == "sensitive_request"]
        assert len(sensitive_diffs) == 0


class TestSameDomainLinkChanges:
    """Detect changed link destinations within the same domain."""

    def test_same_domain_different_path_detected(self):
        comp = compare_conversations(
            earlier_text="Review at https://portal.example.com/invoices/2024",
            newer_text="Review at https://portal.example.com/verify-account?token=abc"
        )
        link_diffs = [d for d in comp["differences"] if d["category"] == "links"]
        assert any("portal.example.com" in d.get("title", "") for d in link_diffs)

    def test_same_domain_explains_legitimate_changes(self):
        comp = compare_conversations(
            earlier_text="See https://docs.company.com/guide-v1",
            newer_text="See https://docs.company.com/guide-v2"
        )
        link_diffs = [d for d in comp["differences"] if d["category"] == "links"]
        assert len(link_diffs) >= 1
        assert any("legitimate" in d.get("why_it_matters", "").lower() for d in link_diffs)


class TestScoringConsistency:
    """Scoring between comparison engine and scam_assistant must be consistent."""

    def test_comparison_score_matches_assessment(self):
        comp = compare_conversations(
            earlier_text="Our bank account is A/C: 1111222233.",
            newer_text="Updated bank details: A/C: 9999888877.",
            earlier_sender="finance@company.com",
            newer_sender="finance@company-new.com"
        )
        # The comparison engine should have a definite extra_score
        assert comp["extra_score"] > 0
        total_expected = comp["extra_score"]

        # Now check via scam_assistant — the final score should include
        # the comparison engine's aggregated extra_score
        res = check_message(
            "Updated bank details: A/C: 9999888877.",
            category="Invoice or payment",
            previous_text="Our bank account is A/C: 1111222233.",
            previous_sender="finance@company.com",
            sender="finance@company-new.com"
        )
        # The score should be at least as high as the comparison extra_score
        assert res["score"] >= total_expected


class TestHonestMissingSummary:
    """Summary must not imply all fields were verified when data is missing."""

    def test_no_differences_reports_compared_fields(self):
        comp = compare_conversations(
            earlier_text="Meeting tomorrow at 10.",
            newer_text="Meeting tomorrow at 10."
        )
        # Should mention which fields were compared
        assert "compared" in comp["summary"].lower() or "fields" in comp["summary"].lower()
        assert comp["has_comparison"] is True

    def test_missing_sender_noted(self):
        comp = compare_conversations(
            earlier_text="Hello",
            newer_text="Hello again",
            newer_sender="alice@example.com"
        )
        # Should note that earlier sender wasn't available
        if not comp["differences"]:
            assert comp["fields_not_available"]
            assert "earlier sender" in " ".join(comp["fields_not_available"]).lower()

    def test_has_comparison_fields_list(self):
        comp = compare_conversations(
            earlier_text="Discussion about project.",
            newer_text="Follow-up on project.",
            earlier_sender="alice@example.com",
            newer_sender="alice@example.com"
        )
        assert "fields_compared" in comp
        assert "fields_not_available" in comp
