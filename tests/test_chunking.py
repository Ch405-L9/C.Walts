"""Chunking must respect the model ceiling and preserve structure."""

import pytest

from natural_flow_rag.chunking import ChunkingError, chunk_text, count_tokens

PROFILES = {
    "reference": {"target_tokens": 128, "overlap_tokens": 16, "maximum_tokens": 256},
    "approved_example": {"target_tokens": 64, "overlap_tokens": 0,
                         "maximum_tokens": 256, "never_merge_separate_examples": True},
    "transcript": {"target_tokens": 96, "overlap_tokens": 12,
                   "maximum_tokens": 256, "preserve_speaker_turns": True},
    "heading_example": {"target_tokens": 256, "overlap_tokens": 0,
                        "maximum_tokens": 512, "never_merge_separate_examples": True,
                        "example_separator": "heading"},
}

STRUCTURED = """# Title

Intro line.

## EXAMPLE-001

- first bullet
- second bullet

Explanatory paragraph for the first example.

## EXAMPLE-002

- another bullet

Explanatory paragraph for the second example.
"""


def test_chunks_stay_within_profile_maximum():
    text = "Sentence about cadence. " * 200
    chunks = chunk_text(text, profile="reference", profiles=PROFILES)
    assert chunks
    assert all(c.token_count <= 256 for c in chunks)


def test_examples_are_never_merged():
    text = "First approved example.\n\nSecond approved example.\n\nThird one."
    chunks = chunk_text(text, profile="approved_example", profiles=PROFILES)
    assert len(chunks) == 3


def test_heading_mode_keeps_one_example_whole():
    """A structured example must not shatter into its individual bullets."""
    chunks = chunk_text(STRUCTURED, profile="heading_example", profiles=PROFILES)
    assert len(chunks) == 3  # preamble + two examples
    second = next(c for c in chunks if "EXAMPLE-002" in c.text)
    assert "another bullet" in second.text
    assert "Explanatory paragraph for the second example." in second.text


def test_heading_mode_never_merges_two_examples():
    chunks = chunk_text(STRUCTURED, profile="heading_example", profiles=PROFILES)
    assert not any("EXAMPLE-001" in c.text and "EXAMPLE-002" in c.text for c in chunks)


def test_blank_line_mode_is_unchanged_by_heading_support():
    """CMUdict-style records still split per blank-line block and never re-merge."""
    text = "AARDVARK  AA1 R D V AA0 R K\n\nAARON  EH1 R AH0 N\n\nABACUS  AE1 B AH0 K AH0 S"
    chunks = chunk_text(text, profile="approved_example", profiles=PROFILES)
    assert len(chunks) == 3


def test_tokenizer_is_recorded_for_later_migration():
    chunks = chunk_text("short text", profile="reference", profiles=PROFILES)
    assert chunks[0].tokenizer == "cl100k_base"


def test_target_above_safe_ceiling_is_refused():
    profiles = {"big": {"target_tokens": 1500, "overlap_tokens": 0}}
    with pytest.raises(ChunkingError, match="safe ceiling"):
        chunk_text("x", profile="big", profiles=profiles, safe_target_ceiling=1024)


def test_unknown_profile_is_refused():
    with pytest.raises(ChunkingError, match="unknown chunk profile"):
        chunk_text("x", profile="nope", profiles=PROFILES)


def test_overlap_must_be_smaller_than_target():
    profiles = {"bad": {"target_tokens": 64, "overlap_tokens": 64}}
    with pytest.raises(ChunkingError, match="overlap"):
        chunk_text("x", profile="bad", profiles=profiles)


def test_notation_survives_chunking():
    text = "The H* accent and the L-L% boundary tone mark an intonational phrase."
    chunks = chunk_text(text, profile="reference", profiles=PROFILES)
    joined = " ".join(c.text for c in chunks)
    assert "H*" in joined and "L-L%" in joined


def test_empty_text_yields_nothing():
    assert chunk_text("   ", profile="reference", profiles=PROFILES) == []


def test_count_tokens_is_positive():
    assert count_tokens("hello world") > 0
