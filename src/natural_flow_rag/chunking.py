"""Tokenizer-aware chunking.

Contrast with the harness ingestion this replaces (audit E24): that code split on
whitespace with ``CHUNK_SIZE = 600`` and a comment claiming "tokens", used no
tokenizer at all, and destroyed every heading and paragraph boundary before
chunking. Chunks routinely began and ended mid-sentence.

Tokenizer caveat, recorded deliberately: ``cl100k_base`` is GPT tokenization, not
nomic-bert's. Counts are therefore approximate against the model's real 2048-token
ceiling. Two mitigations — the tokenizer name is written into every chunk's
metadata so a later switch is detectable, and the caps carry margin rather than
trusting the count to be exact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

DEFAULT_TOKENIZER = "cl100k_base"

# Split preference, most structural first. Headings and paragraph breaks are
# honoured before sentences, and sentences before words.
_SEPARATORS = [
    "\n## ",
    "\n# ",
    "\n\n",
    "\n",
    ". ",
    "? ",
    "! ",
    "; ",
    ", ",
    " ",
]

_SPEAKER_TURN = re.compile(r"^\s*(?:[A-Z][A-Za-z0-9_. -]{0,30}:|\[[^\]]{1,40}\])\s")

# One approved example per H2 section, or per horizontal rule where the document
# uses rules instead of headings. Used by profiles that set
# ``example_separator: heading``.
_EXAMPLE_SECTION = re.compile(r"(?m)^(?=##\s)|^-{3,}[ \t]*$")


class ChunkingError(RuntimeError):
    """Text could not be chunked within the model's hard limits."""


@dataclass
class Chunk:
    text: str
    index: int
    token_count: int
    profile: str
    tokenizer: str = DEFAULT_TOKENIZER
    heading: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@lru_cache(maxsize=4)
def _encoding(name: str):
    import tiktoken

    return tiktoken.get_encoding(name)


def count_tokens(text: str, tokenizer: str = DEFAULT_TOKENIZER) -> int:
    """Single chokepoint for token counting — swap the tokenizer here, nowhere else."""
    return len(_encoding(tokenizer).encode(text, disallowed_special=()))


def _split_once(text: str) -> list[str]:
    """Split on the most structural separator that actually appears."""
    for separator in _SEPARATORS:
        if separator in text:
            parts = text.split(separator)
            # Reattach the separator so meaning and spacing survive the round trip.
            out = [parts[0]]
            out += [separator.lstrip("\n") + p if separator.startswith("\n") else separator + p
                    for p in parts[1:]]
            return [p for p in out if p.strip()]
    return [text]


def _recursive_split(text: str, limit: int, tokenizer: str) -> list[str]:
    if count_tokens(text, tokenizer) <= limit:
        return [text]

    pieces = _split_once(text)
    if len(pieces) == 1:
        # Nothing left to split on — hard-cut on token boundaries.
        encoding = _encoding(tokenizer)
        ids = encoding.encode(text, disallowed_special=())
        return [encoding.decode(ids[i : i + limit]) for i in range(0, len(ids), limit)]

    out: list[str] = []
    for piece in pieces:
        out.extend(_recursive_split(piece, limit, tokenizer))
    return out


def _current_heading(text: str, fallback: str | None) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return fallback


def chunk_text(
    text: str,
    *,
    profile: str,
    profiles: dict[str, Any],
    tokenizer: str = DEFAULT_TOKENIZER,
    hard_maximum_tokens: int = 2048,
    safe_target_ceiling: int = 1024,
) -> list[Chunk]:
    """Chunk ``text`` according to a named profile.

    Profiles come from ``config/rag.yaml``; the caller passes the whole mapping so
    that this function never reads configuration itself and stays unit-testable.
    """
    settings = profiles.get(profile)
    if settings is None:
        raise ChunkingError(
            f"unknown chunk profile {profile!r}; known: {sorted(profiles)}"
        )

    target = int(settings.get("target_tokens", 512))
    overlap = int(settings.get("overlap_tokens", 0))
    minimum = int(settings.get("minimum_tokens", 0))
    maximum = int(settings.get("maximum_tokens", target + overlap))

    if target > safe_target_ceiling:
        raise ChunkingError(
            f"profile {profile!r} targets {target} tokens, above the safe ceiling of "
            f"{safe_target_ceiling}. The tokenizer is approximate against the model's "
            f"{hard_maximum_tokens}-token limit; keep margin."
        )
    if overlap >= target:
        raise ChunkingError(f"profile {profile!r}: overlap {overlap} >= target {target}")

    text = text.strip()
    if not text:
        return []

    # Short-example and pronunciation profiles must never merge distinct records.
    # What counts as a record boundary differs by document shape, so the profile
    # says which one applies:
    #
    #   blank_line (default) — one record per blank-line-separated block, and no
    #     re-merging afterwards. Correct for line-oriented records such as
    #     CMUdict entries.
    #   heading — one record per H2 section or horizontal rule. Correct for
    #     structured markdown, where blank-line splitting shatters a single
    #     example into its individual bullets (measured: 125 fragments averaging
    #     23 tokens from one 1,512-word document).
    #
    # In both cases a record is never merged with its neighbour; only the
    # paragraphs *inside* one record are packed back together, and only in
    # heading mode.
    separator_mode = str(settings.get("example_separator", "blank_line"))
    merge_within_unit = True

    if settings.get("never_merge_separate_examples"):
        if separator_mode == "heading":
            units = [u.strip() for u in _EXAMPLE_SECTION.split(text) if u and u.strip()]
        else:
            units = [u.strip() for u in re.split(r"\n\s*\n", text) if u.strip()]
            merge_within_unit = False
    elif settings.get("preserve_speaker_turns"):
        units = _split_speaker_turns(text)
    else:
        units = [text]

    chunks: list[Chunk] = []
    heading: str | None = None

    for unit in units:
        heading = _current_heading(unit, heading)
        pieces = _recursive_split(unit, target, tokenizer)
        merged = (
            _merge_with_overlap(
                pieces, target=target, overlap=overlap, minimum=minimum, tokenizer=tokenizer
            )
            if merge_within_unit
            else pieces
        )

        for piece in merged:
            piece = piece.strip()
            if not piece:
                continue
            count = count_tokens(piece, tokenizer)
            if count > hard_maximum_tokens:
                raise ChunkingError(
                    f"chunk of {count} tokens exceeds the model ceiling of "
                    f"{hard_maximum_tokens}; it would be silently truncated at embed time"
                )
            if count > maximum:
                raise ChunkingError(
                    f"chunk of {count} tokens exceeds profile maximum {maximum}"
                )
            chunks.append(
                Chunk(
                    text=piece,
                    index=len(chunks),
                    token_count=count,
                    profile=profile,
                    tokenizer=tokenizer,
                    heading=heading,
                )
            )

    return chunks


def _split_speaker_turns(text: str) -> list[str]:
    """Keep a speaker's turn intact; a turn is never split across chunks."""
    turns: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if _SPEAKER_TURN.match(line) and current:
            turns.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        turns.append("\n".join(current))
    return [t for t in turns if t.strip()] or [text]


def _merge_with_overlap(
    pieces: list[str], *, target: int, overlap: int, minimum: int, tokenizer: str
) -> list[str]:
    """Greedily pack pieces up to ``target``, carrying ``overlap`` tokens forward."""
    if not pieces:
        return []

    encoding = _encoding(tokenizer)
    merged: list[str] = []
    buffer = ""

    for piece in pieces:
        candidate = f"{buffer}\n{piece}".strip() if buffer else piece
        if count_tokens(candidate, tokenizer) <= target:
            buffer = candidate
            continue
        if buffer:
            merged.append(buffer)
            if overlap > 0:
                tail_ids = encoding.encode(buffer, disallowed_special=())[-overlap:]
                buffer = encoding.decode(tail_ids) + "\n" + piece
            else:
                buffer = piece
        else:
            merged.append(piece)
            buffer = ""

    if buffer:
        # Fold a runt tail into its predecessor rather than emitting a stub.
        if merged and minimum and count_tokens(buffer, tokenizer) < minimum:
            merged[-1] = merged[-1] + "\n" + buffer
        else:
            merged.append(buffer)

    return merged
