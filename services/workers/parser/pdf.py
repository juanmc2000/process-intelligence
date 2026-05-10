"""PDF parsing utilities for the parser worker.

Only text-readable PDFs are supported — no OCR, no vision model calls.
Returns structural metadata only; extracted text is never logged or
stored in Postgres.
"""

import hashlib
import io
import os
from typing import Any, Dict, Optional


def parse_pdf(data: bytes, filename: str) -> Dict[str, Any]:
    """Extract structural metadata from a text-readable PDF.

    Args:
        data: Raw PDF bytes, already downloaded from object storage.
        filename: Original filename (used for extension/MIME metadata only).

    Returns:
        Dict of metadata suitable for inclusion in a NormalizedEvidence JSON artifact.
        Never includes extracted text content.

    Raises:
        ValueError: If the PDF cannot be opened or is encrypted/unreadable.
    """
    try:
        import pypdf
    except ImportError as exc:
        raise ImportError(
            "pypdf is required for PDF parsing: pip install pypdf"
        ) from exc

    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{filename}': {exc}") from exc

    if reader.is_encrypted:
        raise ValueError(f"PDF '{filename}' is encrypted — cannot extract text.")

    page_count = len(reader.pages)

    # Count characters across all pages without logging the content itself.
    # text_char_count is a structural signal, not customer data.
    text_char_count = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        text_char_count += len(text)

    # Count embedded image objects as a rough signal for diagram candidates.
    # Actual candidate scoring is handled by the image detection module (PARSER-005).
    image_count = _count_images(reader)

    content_hash = "sha256:" + hashlib.sha256(data).hexdigest()

    ext = os.path.splitext(filename)[1].lower() or ".pdf"

    # Detect image candidates using structural signals (no OCR, no vision model).
    from services.workers.parser.image_candidates import score_candidates

    base_metadata = {
        "format": "pdf",
        "original_filename": filename,
        "mime_type": "application/pdf",
        "file_extension": ext,
        "page_count": page_count,
        "text_char_count": text_char_count,
        "image_count": image_count,
        "content_hash": content_hash,
    }
    image_candidates = score_candidates(filename, base_metadata, reader=reader)
    return {**base_metadata, "image_candidates": image_candidates}


def _count_images(reader: Any) -> int:
    """Count embedded XObject images across all pages.

    Used only as a structural metadata signal — no images are decoded or stored.
    """
    count = 0
    try:
        for page in reader.pages:
            resources = page.get("/Resources", {})
            xobjects = resources.get("/XObject", {})
            for key in xobjects:
                obj = xobjects[key].get_object()
                if obj.get("/Subtype") == "/Image":
                    count += 1
    except Exception:
        # Non-fatal: image counting is best-effort metadata only.
        pass
    return count


def is_pdf(content_type: Optional[str], filename: str) -> bool:
    """Return True if the artifact looks like a PDF by MIME type or extension."""
    if content_type and "pdf" in content_type.lower():
        return True
    return filename.lower().endswith(".pdf")
