"""EML email parsing utilities for the parser worker.

Extracts structural metadata from .eml files using Python's stdlib email module.
No raw email body content is stored or logged — only safe metadata fields.
"""

import email
import email.utils
import hashlib
from typing import Any, Dict, List, Optional


def parse_eml(data: bytes, filename: str) -> Dict[str, Any]:
    """Extract structural metadata from an EML file.

    Args:
        data: Raw EML bytes, already downloaded from object storage.
        filename: Original filename (used for extension/MIME metadata only).

    Returns:
        Dict of metadata suitable for inclusion in a NormalizedEvidence JSON artifact.
        Never includes raw email body content.

    Raises:
        ValueError: If the bytes cannot be parsed as an email message.
    """
    try:
        msg = email.message_from_bytes(data)
    except Exception as exc:
        raise ValueError(f"Cannot parse EML '{filename}': {exc}") from exc

    subject = _decode_header_value(msg.get("Subject", ""))
    sender = _decode_header_value(msg.get("From", ""))
    message_id = msg.get("Message-ID", "").strip()

    recipients = _parse_address_list(msg.get("To", ""))
    cc = _parse_address_list(msg.get("Cc", ""))

    # Thread/reference headers for conversation lineage.
    references = msg.get("References", "").split() if msg.get("References") else []
    in_reply_to = msg.get("In-Reply-To", "").strip()
    thread_references = ([in_reply_to] if in_reply_to else []) + references

    # Parse the Date header; keep as ISO string if valid, None otherwise.
    source_date: Optional[str] = None
    date_raw = msg.get("Date", "")
    if date_raw:
        try:
            parsed_ts = email.utils.parsedate_to_datetime(date_raw)
            source_date = parsed_ts.isoformat()
        except Exception:
            # Non-fatal: malformed Date header is not uncommon.
            pass

    # Count body characters as a structural signal only; never log content.
    body_text_char_count = _count_body_chars(msg)

    # Collect attachment metadata — name and MIME type only, no content.
    attachment_metadata = _collect_attachment_metadata(msg)

    content_hash = "sha256:" + hashlib.sha256(data).hexdigest()

    return {
        "format": "eml",
        "original_filename": filename,
        "mime_type": "message/rfc822",
        "file_extension": ".eml",
        "subject": subject,
        "sender": sender,
        "recipients": recipients,
        "cc": cc,
        "message_id": message_id,
        "thread_references": thread_references,
        "source_date": source_date,
        "body_text_char_count": body_text_char_count,
        "attachment_metadata": attachment_metadata,
        "content_hash": content_hash,
    }


def _decode_header_value(raw: str) -> str:
    """Decode an RFC2047-encoded header value to a plain string.

    Returns an empty string if decoding fails.  Never raises.
    """
    if not raw:
        return ""
    try:
        from email.header import decode_header

        parts = decode_header(raw)
        decoded_parts = []
        for part_bytes, charset in parts:
            if isinstance(part_bytes, bytes):
                decoded_parts.append(
                    part_bytes.decode(charset or "utf-8", errors="replace")
                )
            else:
                decoded_parts.append(part_bytes)
        return "".join(decoded_parts).strip()
    except Exception:
        return raw.strip()


def _parse_address_list(raw: str) -> List[str]:
    """Parse a comma-separated RFC2822 address list into a list of address strings.

    Returns a list of bare address strings.
    Never raises — returns an empty list on any parse failure.
    """
    if not raw:
        return []
    try:
        return [
            addr.strip()
            for _name, addr in email.utils.getaddresses([raw])
            if addr.strip()
        ]
    except Exception:
        return []


def _count_body_chars(msg: email.message.Message) -> int:
    """Count total characters across all text/* body parts.

    This is a structural size signal only — the body text is not retained.
    """
    count = 0
    try:
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type.startswith("text/") and not part.get_filename():
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    count += len(payload.decode(charset, errors="replace"))
    except Exception:
        pass
    return count


def _collect_attachment_metadata(msg: email.message.Message) -> List[Dict[str, Any]]:
    """Collect name and MIME type of each attachment.

    Content is never read or stored.  Returns an empty list if none found.
    """
    attachments: List[Dict[str, Any]] = []
    try:
        for part in msg.walk():
            disposition = part.get_content_disposition()
            filename = part.get_filename()
            if disposition == "attachment" or filename:
                content_type = part.get_content_type()
                size: Optional[int] = None
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    size = len(payload)
                attachments.append(
                    {
                        "filename": _decode_header_value(filename or ""),
                        "content_type": content_type,
                        "size_bytes": size,
                    }
                )
    except Exception:
        pass
    return attachments


def is_eml(content_type: Optional[str], filename: str) -> bool:
    """Return True if the artifact looks like an EML file by MIME type or extension."""
    if content_type and content_type.lower() == "message/rfc822":
        return True
    return filename.lower().endswith(".eml")
