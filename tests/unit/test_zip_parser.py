"""Unit tests for the ZIP expansion module.

Uses synthetic in-memory ZIP fixtures — no real customer content.
"""

import hashlib
import io
import zipfile


def _make_zip(members: dict) -> bytes:
    """Build a ZIP archive in memory.

    Args:
        members: {filename: bytes_content}
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestZipParser:
    def test_inspect_zip_returns_metadata_fields(self):
        """inspect_zip returns all required metadata fields."""
        from services.workers.parser.zip import inspect_zip

        data = _make_zip({"report.pdf": b"fakepdf", "notes.txt": b"hello"})
        metadata, _ = inspect_zip(data, "archive.zip")

        assert metadata["format"] == "zip"
        assert metadata["original_filename"] == "archive.zip"
        assert metadata["mime_type"] == "application/zip"
        assert metadata["file_extension"] == ".zip"
        assert isinstance(metadata["member_count"], int)
        assert isinstance(metadata["extracted_count"], int)
        assert isinstance(metadata["skipped_count"], int)
        assert isinstance(metadata["child_entries"], list)
        assert metadata["content_hash"].startswith("sha256:")

    def test_content_hash_matches_input(self):
        """Content hash is the SHA-256 of the raw ZIP bytes."""
        from services.workers.parser.zip import inspect_zip

        data = _make_zip({"file.txt": b"content"})
        metadata, _ = inspect_zip(data, "archive.zip")

        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        assert metadata["content_hash"] == expected

    def test_supported_files_are_extracted(self):
        """PDF, EML, TXT, and MD files are extracted from ZIP."""
        from services.workers.parser.zip import inspect_zip

        members = {
            "report.pdf": b"fakepdf",
            "email.eml": b"From: a@b.com\r\n\r\nbody",
            "notes.txt": b"plain text",
            "readme.md": b"# Title",
        }
        data = _make_zip(members)
        metadata, child_entries = inspect_zip(data, "archive.zip")

        extracted_names = {e["name"] for e in child_entries}
        assert "report.pdf" in extracted_names
        assert "email.eml" in extracted_names
        assert "notes.txt" in extracted_names
        assert "readme.md" in extracted_names
        assert metadata["extracted_count"] == 4

    def test_unsupported_files_are_skipped(self):
        """Unsupported file types are skipped and recorded in skipped_entries."""
        from services.workers.parser.zip import inspect_zip

        data = _make_zip(
            {
                "report.pdf": b"fakepdf",
                "image.png": b"fakepng",
                "data.xlsx": b"fakexlsx",
            }
        )
        metadata, child_entries = inspect_zip(data, "archive.zip")

        extracted_names = {e["name"] for e in child_entries}
        assert "report.pdf" in extracted_names
        assert "image.png" not in extracted_names
        assert "data.xlsx" not in extracted_names
        assert metadata["skipped_count"] == 2

        skipped_names = {s["name"] for s in metadata["skipped_entries"]}
        assert "image.png" in skipped_names
        assert "data.xlsx" in skipped_names

    def test_nested_zip_is_skipped(self):
        """Nested ZIP files are not expanded (one-level only)."""
        from services.workers.parser.zip import inspect_zip

        inner_zip = _make_zip({"inner.txt": b"inner content"})
        data = _make_zip({"notes.txt": b"outer", "nested.zip": inner_zip})
        metadata, child_entries = inspect_zip(data, "archive.zip")

        extracted_names = {e["name"] for e in child_entries}
        assert "nested.zip" not in extracted_names
        assert "notes.txt" in extracted_names

        skipped_reasons = {s["name"]: s["reason"] for s in metadata["skipped_entries"]}
        assert skipped_reasons.get("nested.zip") == "nested_zip"

    def test_path_traversal_is_rejected(self):
        """Members with path traversal sequences are rejected."""
        from services.workers.parser.zip import inspect_zip

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("safe.txt", b"safe")
            # Manually add a traversal entry (ZipFile normally doesn't block this).
            zf.writestr("../evil.txt", b"evil")
        data = buf.getvalue()

        metadata, child_entries = inspect_zip(data, "archive.zip")

        extracted_names = {e["name"] for e in child_entries}
        assert "safe.txt" in extracted_names
        assert "evil.txt" not in extracted_names

        skipped_reasons = {s["name"]: s["reason"] for s in metadata["skipped_entries"]}
        assert any(v == "path_traversal" for v in skipped_reasons.values())

    def test_child_entries_contain_data(self):
        """Each extracted child entry includes raw bytes for uploading."""
        from services.workers.parser.zip import inspect_zip

        content = b"This is a text file."
        data = _make_zip({"notes.txt": content})
        _, child_entries = inspect_zip(data, "archive.zip")

        assert len(child_entries) == 1
        assert child_entries[0]["data"] == content
        assert child_entries[0]["size_bytes"] == len(content)

    def test_child_entry_hash(self):
        """Each child entry has a correct SHA-256 content_hash."""
        from services.workers.parser.zip import inspect_zip

        content = b"Hello!"
        data = _make_zip({"notes.txt": content})
        _, child_entries = inspect_zip(data, "archive.zip")

        expected_hash = "sha256:" + hashlib.sha256(content).hexdigest()
        assert child_entries[0]["content_hash"] == expected_hash

    def test_metadata_child_entries_exclude_bytes(self):
        """The metadata dict's child_entries do not contain raw bytes."""
        from services.workers.parser.zip import inspect_zip

        data = _make_zip({"notes.txt": b"content"})
        metadata, _ = inspect_zip(data, "archive.zip")

        for entry in metadata["child_entries"]:
            assert "data" not in entry

    def test_invalid_bytes_raises_value_error(self):
        """inspect_zip raises ValueError for non-ZIP data."""
        import pytest

        from services.workers.parser.zip import inspect_zip

        with pytest.raises(ValueError):
            inspect_zip(b"not a zip file", "bad.zip")

    def test_is_zip_by_mime_type(self):
        """is_zip detects ZIPs by MIME type."""
        from services.workers.parser.zip import is_zip

        assert is_zip("application/zip", "file.bin") is True
        assert is_zip("application/x-zip-compressed", "file.bin") is True
        assert is_zip("application/pdf", "file.pdf") is False

    def test_is_zip_by_extension(self):
        """is_zip detects ZIPs by .zip file extension."""
        from services.workers.parser.zip import is_zip

        assert is_zip(None, "archive.zip") is True
        assert is_zip(None, "archive.ZIP") is True
        assert is_zip(None, "report.pdf") is False

    def test_empty_zip_handled(self):
        """inspect_zip handles a ZIP with no files gracefully."""
        from services.workers.parser.zip import inspect_zip

        data = _make_zip({})
        metadata, child_entries = inspect_zip(data, "empty.zip")

        assert metadata["member_count"] == 0
        assert metadata["extracted_count"] == 0
        assert child_entries == []
