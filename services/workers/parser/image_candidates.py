"""Deterministic image candidate detection for process-diagram identification.

Uses filename keywords and structural PDF signals (image count vs. text density)
to flag pages or documents that likely contain process diagrams.

No OCR, no vision model, no AI calls.  All logic is rule-based and inexpensive.
"""

import os
import re
from typing import Any, Dict, List, Optional

# Filename keywords that suggest a process-diagram document.
_DIAGRAM_FILENAME_KEYWORDS = frozenset(
    {
        "flow",
        "workflow",
        "process",
        "diagram",
        "map",
        "swimlane",
        "chart",
        "bpmn",
        "flowchart",
        "dataflow",
        "procedure",
    }
)

# Keywords found in surrounding text (alt-text, captions) that raise confidence.
_DIAGRAM_TEXT_KEYWORDS = re.compile(
    r"\b(figure|fig\.|diagram|workflow|process\s+flow|flowchart|swimlane|bpmn|chart)\b",
    re.IGNORECASE,
)

# A page is a diagram candidate if it has images but very little body text.
# Heuristic: text_char_count < this threshold per image embedded on the page.
_LOW_TEXT_PER_IMAGE_THRESHOLD = 200


def detect_from_filename(filename: str) -> Optional[Dict[str, Any]]:
    """Return an image candidate dict if the filename suggests a process diagram.

    Args:
        filename: Original filename (extension-stripped, lowercased for matching).

    Returns:
        A candidate dict or None.
    """
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    # Tokenise on common separators so 'process_flow.png' → ['process', 'flow']
    tokens = set(re.split(r"[_\-\s\.]+", stem))
    matched = tokens & _DIAGRAM_FILENAME_KEYWORDS
    if not matched:
        return None
    return {
        "page": None,
        "location_hint": "filename",
        "reasons": ["filename_keyword:" + k for k in sorted(matched)],
        "confidence": "low",
    }


def detect_pdf_page_candidates(reader: Any) -> List[Dict[str, Any]]:
    """Identify PDF pages likely to contain process diagrams via structural signals.

    Signals used (no OCR, no vision):
    - Page has ≥1 embedded XObject image.
    - Page has fewer characters than _LOW_TEXT_PER_IMAGE_THRESHOLD per image
      (high image density relative to text suggests a diagram page).
    - Alt-text or metadata near XObjects contains diagram keywords (best-effort).

    Args:
        reader: A pypdf.PdfReader instance (already opened by the caller).

    Returns:
        List of candidate dicts, one per qualifying page (1-indexed page numbers).
        Empty list if no candidates found.  Never raises.
    """
    candidates: List[Dict[str, Any]] = []
    try:
        for page_index, page in enumerate(reader.pages):
            page_num = page_index + 1  # 1-indexed

            # Count embedded XObject images on this page.
            image_count = _count_page_images(page)
            if image_count == 0:
                continue

            # Extract text character count for this page only.
            text = page.extract_text() or ""
            text_char_count = len(text)

            reasons: List[str] = []

            # Structural signal: image-rich relative to text.
            if text_char_count < _LOW_TEXT_PER_IMAGE_THRESHOLD * image_count:
                reasons.append("high_image_to_text_ratio")

            # Context signal: nearby text mentions diagram keywords.
            if _DIAGRAM_TEXT_KEYWORDS.search(text):
                reasons.append("diagram_keyword_in_text")

            if not reasons:
                # Page has images but no strong diagram signals — skip.
                continue

            # Confidence: "medium" if both signals, "low" if only one.
            confidence = "medium" if len(reasons) >= 2 else "low"

            candidates.append(
                {
                    "page": page_num,
                    "location_hint": f"page_{page_num}",
                    "reasons": reasons,
                    "confidence": confidence,
                }
            )
    except Exception:
        # Non-fatal: candidate detection is best-effort.
        pass
    return candidates


def _count_page_images(page: Any) -> int:
    """Count embedded XObject images on a single PDF page.

    Used only for structural metadata — images are not decoded or stored.
    """
    count = 0
    try:
        resources = page.get("/Resources", {})
        xobjects = resources.get("/XObject", {})
        for key in xobjects:
            obj = xobjects[key].get_object()
            if obj.get("/Subtype") == "/Image":
                count += 1
    except Exception:
        pass
    return count


def score_candidates(
    filename: str,
    format_metadata: Dict[str, Any],
    reader: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Produce the combined list of image candidates for a parsed document.

    Merges filename-based and (for PDFs) page-level structural candidates.

    Args:
        filename: Original artifact filename.
        format_metadata: Metadata dict already produced by the format parser.
        reader: Open pypdf.PdfReader, if format is PDF.

    Returns:
        List of candidate dicts.  Empty list if none found.
    """
    candidates: List[Dict[str, Any]] = []

    filename_candidate = detect_from_filename(filename)
    if filename_candidate:
        candidates.append(filename_candidate)

    if reader is not None and format_metadata.get("format") == "pdf":
        candidates.extend(detect_pdf_page_candidates(reader))

    return candidates
