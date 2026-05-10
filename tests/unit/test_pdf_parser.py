"""Unit tests for the PDF parser module.

Uses a synthetic minimal PDF fixture — no real customer documents.
"""

import hashlib
import io


def _make_minimal_pdf(text: str = "Process step A\nProcess step B") -> bytes:
    """Build a minimal valid single-page PDF with embedded text.

    Uses only standard PDF syntax — no external libraries needed for fixture creation.
    The content stream encodes the text in a font-less form sufficient for pypdf to
    extract via extract_text().
    """
    from pypdf import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # pypdf does not expose a simple add-text API without reportlab; instead we embed
    # the text directly into the page content stream using raw PDF operators.
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    from pypdf.generic import (
        DecodedStreamObject,
        NameObject,
    )

    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject("/Contents")] = stream

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_minimal_pdf_bytes() -> bytes:
    """Return a minimal valid PDF as raw bytes without using pypdf writer."""
    # A minimal syntactically valid PDF with one blank page.
    raw = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n190\n%%EOF\n"
    )
    return raw


class TestPdfParser:
    def test_parse_minimal_pdf_returns_required_fields(self):
        """parse_pdf returns all required metadata fields."""
        from services.workers.parser.pdf import parse_pdf

        pdf_bytes = _make_minimal_pdf_bytes()
        result = parse_pdf(pdf_bytes, "test.pdf")

        assert result["format"] == "pdf"
        assert result["original_filename"] == "test.pdf"
        assert result["mime_type"] == "application/pdf"
        assert result["file_extension"] == ".pdf"
        assert isinstance(result["page_count"], int)
        assert result["page_count"] >= 1
        assert isinstance(result["text_char_count"], int)
        assert isinstance(result["image_count"], int)
        assert result["content_hash"].startswith("sha256:")

    def test_content_hash_matches_input(self):
        """Content hash is the SHA-256 of the raw PDF bytes."""
        from services.workers.parser.pdf import parse_pdf

        pdf_bytes = _make_minimal_pdf_bytes()
        result = parse_pdf(pdf_bytes, "test.pdf")

        expected = "sha256:" + hashlib.sha256(pdf_bytes).hexdigest()
        assert result["content_hash"] == expected

    def test_invalid_bytes_raises_value_error(self):
        """parse_pdf raises ValueError for non-PDF data."""
        import pytest

        from services.workers.parser.pdf import parse_pdf

        with pytest.raises(ValueError):
            parse_pdf(b"not a pdf", "bad.pdf")

    def test_is_pdf_by_content_type(self):
        """is_pdf detects PDFs by MIME type."""
        from services.workers.parser.pdf import is_pdf

        assert is_pdf("application/pdf", "file.bin") is True
        assert is_pdf("text/plain", "file.txt") is False

    def test_is_pdf_by_extension(self):
        """is_pdf detects PDFs by file extension."""
        from services.workers.parser.pdf import is_pdf

        assert is_pdf(None, "report.pdf") is True
        assert is_pdf(None, "report.PDF") is True
        assert is_pdf(None, "report.txt") is False

    def test_no_raw_text_in_result(self):
        """Extracted text is never returned in the metadata dict."""
        from services.workers.parser.pdf import parse_pdf

        pdf_bytes = _make_minimal_pdf_bytes()
        result = parse_pdf(pdf_bytes, "test.pdf")

        # The dict must not contain any key that would expose raw content.
        assert "text" not in result
        assert "content" not in result
        assert "body" not in result
        # text_char_count is a count (int), not the actual text.
        assert isinstance(result.get("text_char_count"), int)
