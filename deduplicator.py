"""
Deduplication check against existing requirements docs in the handoff folder.
Uses Jaccard similarity on title token sets — no heavy dependencies needed.
"""

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

# Common English stop words to exclude from similarity comparison
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall", "this",
    "that", "these", "those", "it", "its", "my", "your", "our", "their",
    "we", "you", "he", "she", "they", "i", "new", "app", "tool", "platform",
}


def _tokenise(text: str) -> set[str]:
    """Lowercase, remove punctuation, split, filter stop words."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 2}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _extract_doc_title(filepath: Path) -> str:
    """Read the first H1 heading from a markdown doc as its title."""
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
    except OSError:
        pass
    # Fall back to filename
    return filepath.stem.replace("_", " ")


def is_duplicate(
    opportunity: dict, handoff_folder: Path, config: dict
) -> bool:
    """
    Returns True if a sufficiently similar requirements doc already exists
    in the handoff folder.
    """
    threshold = config.get("dedup_similarity_threshold", 0.45)
    candidate_tokens = _tokenise(opportunity.get("title", ""))

    if not candidate_tokens:
        return False

    if not handoff_folder.exists():
        return False

    existing_docs = list(handoff_folder.glob("*.md"))
    if not existing_docs:
        return False

    for doc_path in existing_docs:
        existing_title = _extract_doc_title(doc_path)
        existing_tokens = _tokenise(existing_title)
        similarity = _jaccard(candidate_tokens, existing_tokens)

        if similarity >= threshold:
            log.debug(
                f"Duplicate detected: '{opportunity['title']}' ~ "
                f"'{existing_title}' (Jaccard={similarity:.2f})"
            )
            return True

    return False
