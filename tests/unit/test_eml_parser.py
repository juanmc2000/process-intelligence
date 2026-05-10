"""Unit tests for the EML parser module.

Uses synthetic minimal EML fixtures — no real customer email content.
"""

import hashlib


def _make_minimal_eml(
    subject: str = "Test Subject",
    sender: str = "alice@example.com",
    recipient: str = "bob@example.com",
    body: str = "Hello world",
    message_id: str = "<abc123@example.com>",
    date: str = "Mon, 01 Jan 2024 12:00:00 +0000",
) -> bytes:
    """Build a minimal plain-text EML fixture."""
    raw = (
        f"From: {sender}\r\n"
        f"To: {recipient}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: {message_id}\r\n"
        f"Date: {date}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}\r\n"
    )
    return raw.encode("utf-8")


def _make_eml_with_attachment() -> bytes:
    """Build a minimal multipart EML with one attachment."""
    boundary = "boundary123"
    raw = (
        "From: alice@example.com\r\n"
        "To: bob@example.com\r\n"
        "Subject: With Attachment\r\n"
        "Date: Mon, 01 Jan 2024 12:00:00 +0000\r\n"
        f"Content-Type: multipart/mixed; boundary={boundary}\r\n"
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Body text here.\r\n"
        f"--{boundary}\r\n"
        "Content-Type: application/pdf\r\n"
        'Content-Disposition: attachment; filename="report.pdf"\r\n'
        "\r\n"
        "fakepdfbytes\r\n"
        f"--{boundary}--\r\n"
    )
    return raw.encode("utf-8")


def _make_eml_with_thread_headers() -> bytes:
    """Build an EML with In-Reply-To and References headers."""
    raw = (
        "From: bob@example.com\r\n"
        "To: alice@example.com\r\n"
        "Subject: Re: Test\r\n"
        "Message-ID: <reply1@example.com>\r\n"
        "In-Reply-To: <original@example.com>\r\n"
        "References: <original@example.com>\r\n"
        "Date: Mon, 01 Jan 2024 13:00:00 +0000\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Reply body.\r\n"
    )
    return raw.encode("utf-8")


class TestEmlParser:
    def test_parse_minimal_eml_returns_required_fields(self):
        """parse_eml returns all required metadata fields."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml()
        result = parse_eml(eml_bytes, "test.eml")

        assert result["format"] == "eml"
        assert result["original_filename"] == "test.eml"
        assert result["mime_type"] == "message/rfc822"
        assert result["file_extension"] == ".eml"
        assert isinstance(result["subject"], str)
        assert isinstance(result["sender"], str)
        assert isinstance(result["recipients"], list)
        assert isinstance(result["cc"], list)
        assert isinstance(result["message_id"], str)
        assert isinstance(result["thread_references"], list)
        assert isinstance(result["body_text_char_count"], int)
        assert isinstance(result["attachment_metadata"], list)
        assert result["content_hash"].startswith("sha256:")

    def test_content_hash_matches_input(self):
        """Content hash is the SHA-256 of the raw EML bytes."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml()
        result = parse_eml(eml_bytes, "test.eml")

        expected = "sha256:" + hashlib.sha256(eml_bytes).hexdigest()
        assert result["content_hash"] == expected

    def test_extracts_sender_and_recipients(self):
        """parse_eml correctly extracts sender and recipient addresses."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml(
            sender="alice@example.com", recipient="bob@example.com"
        )
        result = parse_eml(eml_bytes, "test.eml")

        assert "alice@example.com" in result["sender"]
        assert "bob@example.com" in result["recipients"]

    def test_extracts_subject(self):
        """parse_eml extracts the Subject header."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml(subject="My Important Subject")
        result = parse_eml(eml_bytes, "test.eml")

        assert result["subject"] == "My Important Subject"

    def test_extracts_source_date(self):
        """parse_eml parses the Date header into an ISO string."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml(date="Mon, 01 Jan 2024 12:00:00 +0000")
        result = parse_eml(eml_bytes, "test.eml")

        assert result["source_date"] is not None
        assert "2024" in result["source_date"]

    def test_extracts_message_id(self):
        """parse_eml captures Message-ID header."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml(message_id="<unique-id@example.com>")
        result = parse_eml(eml_bytes, "test.eml")

        assert "unique-id@example.com" in result["message_id"]

    def test_extracts_thread_references(self):
        """parse_eml captures In-Reply-To and References headers."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_eml_with_thread_headers()
        result = parse_eml(eml_bytes, "reply.eml")

        assert "<original@example.com>" in result["thread_references"]

    def test_extracts_attachment_metadata(self):
        """parse_eml captures attachment filename and MIME type without storing content."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_eml_with_attachment()
        result = parse_eml(eml_bytes, "with_attachment.eml")

        assert len(result["attachment_metadata"]) >= 1
        att = result["attachment_metadata"][0]
        assert att["filename"] == "report.pdf"
        assert "pdf" in att["content_type"]

    def test_body_text_char_count_is_int(self):
        """body_text_char_count is an integer count, not the text itself."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml(body="Hello world")
        result = parse_eml(eml_bytes, "test.eml")

        assert isinstance(result["body_text_char_count"], int)
        assert result["body_text_char_count"] > 0

    def test_no_raw_body_in_result(self):
        """Extracted body text is never returned in the metadata dict."""
        from services.workers.parser.eml import parse_eml

        eml_bytes = _make_minimal_eml(body="SECRET CONTENT DO NOT EXPOSE")
        result = parse_eml(eml_bytes, "test.eml")

        for value in result.values():
            if isinstance(value, str):
                assert "SECRET CONTENT" not in value

    def test_is_eml_by_mime_type(self):
        """is_eml detects EML by message/rfc822 MIME type."""
        from services.workers.parser.eml import is_eml

        assert is_eml("message/rfc822", "file.bin") is True
        assert is_eml("application/pdf", "file.pdf") is False

    def test_is_eml_by_extension(self):
        """is_eml detects EML by .eml file extension."""
        from services.workers.parser.eml import is_eml

        assert is_eml(None, "email.eml") is True
        assert is_eml(None, "email.EML") is True
        assert is_eml(None, "report.pdf") is False

    def test_missing_optional_headers_return_defaults(self):
        """parse_eml handles missing optional headers gracefully."""
        from services.workers.parser.eml import parse_eml

        # Minimal EML with no Cc, no Message-ID, no Date
        raw = b"From: alice@example.com\r\nTo: bob@example.com\r\n\r\nBody\r\n"
        result = parse_eml(raw, "minimal.eml")

        assert result["cc"] == []
        assert result["thread_references"] == []
        assert result["source_date"] is None
