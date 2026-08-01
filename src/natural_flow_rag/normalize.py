"""Text normalization.

Deliberately conservative. This corpus is *about* wording, rhythm, and notation,
so aggressive cleanup would destroy the signal being indexed. Specifically
preserved: case, ``*``, ``%``, ``-`` (so ``H*`` and ``L-L%`` survive), sentence
punctuation, and paragraph boundaries.

Contrast the harness ingestion (audit E24), which called ``text.split()`` and threw
away every newline before chunking.
"""

from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = re.compile(r"[​-‏﻿]")
_TRAILING_WS = re.compile(r"[ \t]+$", re.M)
_EXCESS_BLANKS = re.compile(r"\n{3,}")
_CR = re.compile(r"\r\n?")

# Smart punctuation is folded to ASCII: it is a transcription artifact, not
# prosodic content, and it fragments both BM25 tokens and embeddings.
_PUNCT_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "—", "…": "...", " ": " ",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _CR.sub("\n", text)
    text = _ZERO_WIDTH.sub("", text)
    for source, target in _PUNCT_MAP.items():
        text = text.replace(source, target)
    text = _TRAILING_WS.sub("", text)
    text = _EXCESS_BLANKS.sub("\n\n", text)
    return text.strip() + "\n"


def normalize_cmudict(text: str) -> str:
    """CMUdict entries: ``WORD  W ER1 D``. One entry per line, comments dropped.

    Each entry becomes its own paragraph so the pronunciation profile — which sets
    ``never_merge_separate_examples`` — keeps words from bleeding into each other.
    """
    entries: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";;;"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        word, phonemes = parts
        stress = "".join(c for c in phonemes if c.isdigit())
        entries.append(
            f"{word}\npronunciation: {phonemes}\nstress pattern: {stress or 'none'}"
        )
    return "\n\n".join(entries) + "\n"
