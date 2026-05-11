"""Negation and speculative statement detection.

Prevents negative or speculative statements from being treated as
completed workflow facts. Flags sentences containing negation markers
or speculative language so downstream consumers can filter them.
"""

import re

# Negation markers — sentences containing these should not produce entities/relations
_NEGATION_PATTERNS = [
    re.compile(
        r"\b(?:not|no|never|neither|nor|cannot|can't|won't|wouldn't|shouldn't|doesn't|don't|didn't|isn't|aren't|wasn't|weren't)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:no longer|not yet|not currently|has not been|have not been|was not|were not)\b",
        re.IGNORECASE,
    ),
]

# Speculative / hypothetical markers
_SPECULATIVE_PATTERNS = [
    re.compile(
        r"\b(?:might|may|could|would|should|possibly|potentially|perhaps|if\s+applicable|if\s+needed|in\s+the\s+future|planned|proposed|considering|under\s+review)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:it\s+is\s+possible|there\s+is\s+a\s+chance|we\s+are\s+considering|to\s+be\s+determined|tbd)\b",
        re.IGNORECASE,
    ),
]


def is_negated(text: str) -> bool:
    """Return True if the text contains negation markers."""
    return any(p.search(text) for p in _NEGATION_PATTERNS)


def is_speculative(text: str) -> bool:
    """Return True if the text contains speculative/hypothetical language."""
    return any(p.search(text) for p in _SPECULATIVE_PATTERNS)


def sentence_flags(text: str) -> dict[str, bool]:
    """Return negation and speculative flags for a text segment."""
    return {
        "negated": is_negated(text),
        "speculative": is_speculative(text),
    }


def filter_negated_sentences(sentences: list[str]) -> tuple[list[str], list[str]]:
    """Split sentences into factual and non-factual (negated/speculative).

    Returns (factual_sentences, filtered_sentences).
    Filtered sentences are those containing negation or speculative markers.
    """
    factual = []
    filtered = []
    for s in sentences:
        if is_negated(s) or is_speculative(s):
            filtered.append(s)
        else:
            factual.append(s)
    return factual, filtered
