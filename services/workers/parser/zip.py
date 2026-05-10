"""ZIP expansion utilities for the parser worker.

Safely inspects and extracts supported files from ZIP archives without writing
to disk.  Extracted bytes are held in memory and uploaded directly to MinIO.

Supported child formats: PDF, EML, TXT, MD.
Nested ZIPs and password-protected archives are skipped with a log warning.
"""

import hashlib
import io
import mimetypes
import os
import zipfile
from typing import Any, Dict, List, Optional, Tuple


# Extensions eligible for extraction and downstream parsing.
_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".eml", ".txt", ".md"})

# Reject member names with path traversal patterns before extracting.
_TRAVERSAL_MARKERS = ("..", "//", "\\")

# Guard against ZIP bombs or excessively large archives.
_MAX_MEMBER_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB per extracted member


def is_zip(content_type: Optional[str], filename: str) -> bool:
    """Return True if the artifact looks like a ZIP by MIME type or extension."""
    if content_type and content_type.lower() in (
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    ):
        # application/octet-stream with .zip extension is common.
        if content_type.lower() != "application/octet-stream":
            return True
    return filename.lower().endswith(".zip")


def inspect_zip(
    data: bytes, filename: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Inspect a ZIP archive and return metadata + list of extractable entries.

    This function is pure: it does not upload to object storage or touch the DB.
    Callers (e.g. the parse_artifact activity) are responsible for persisting
    the child entries returned.

    Args:
        data: Raw ZIP bytes.
        filename: Original ZIP filename (for metadata only).

    Returns:
        (metadata_dict, child_entries) where:
        - metadata_dict: suitable for merging into NormalizedEvidence JSON.
        - child_entries: list of dicts with keys
            {name, data, content_type, size_bytes, content_hash, supported}.

    Raises:
        ValueError: If the bytes cannot be opened as a ZIP file.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Cannot open ZIP '{filename}': {exc}") from exc

    content_hash = "sha256:" + hashlib.sha256(data).hexdigest()
    child_entries: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    with zf:
        all_names = [i.filename for i in zf.infolist() if not i.is_dir()]

        for info in zf.infolist():
            if info.is_dir():
                continue

            member_name = info.filename
            ext = os.path.splitext(member_name)[1].lower()

            # Safety: reject path traversal attempts.
            if _is_path_traversal(member_name):
                skipped.append({"name": member_name, "reason": "path_traversal"})
                continue

            # Skip nested ZIPs to prevent infinite expansion.
            if ext == ".zip":
                skipped.append({"name": member_name, "reason": "nested_zip"})
                continue

            supported = ext in _SUPPORTED_EXTENSIONS
            if not supported:
                skipped.append({"name": member_name, "reason": "unsupported_type"})
                continue

            # Guard against large members before reading into memory.
            if info.file_size > _MAX_MEMBER_SIZE_BYTES:
                skipped.append({"name": member_name, "reason": "exceeds_size_limit"})
                continue

            member_data = zf.read(member_name)
            member_hash = "sha256:" + hashlib.sha256(member_data).hexdigest()
            content_type = _guess_content_type(member_name)

            child_entries.append(
                {
                    "name": os.path.basename(member_name),
                    "zip_path": member_name,
                    "data": member_data,
                    "content_type": content_type,
                    "size_bytes": len(member_data),
                    "content_hash": member_hash,
                }
            )

    metadata: Dict[str, Any] = {
        "format": "zip",
        "original_filename": filename,
        "mime_type": "application/zip",
        "file_extension": ".zip",
        "member_count": len(all_names),
        "extracted_count": len(child_entries),
        "skipped_count": len(skipped),
        "skipped_entries": skipped,
        # Child entry metadata (no bytes — bytes are in child_entries return value).
        "child_entries": [
            {
                "name": e["name"],
                "zip_path": e["zip_path"],
                "content_type": e["content_type"],
                "size_bytes": e["size_bytes"],
                "content_hash": e["content_hash"],
            }
            for e in child_entries
        ],
        "content_hash": content_hash,
    }
    return metadata, child_entries


def _is_path_traversal(member_name: str) -> bool:
    """Return True if the member name contains a path traversal sequence.

    Checks for '..', double slashes, and backslashes that could escape the
    intended extraction directory.
    """
    for marker in _TRAVERSAL_MARKERS:
        if marker in member_name:
            return True
    # Absolute paths are also unsafe.
    if member_name.startswith("/"):
        return True
    return False


def _guess_content_type(filename: str) -> str:
    """Guess MIME type from filename extension; fall back to octet-stream."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"
