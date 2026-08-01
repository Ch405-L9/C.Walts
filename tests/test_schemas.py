"""Content-sensitive IDs — the defect that made the old corpus drift silently."""

import pytest

from natural_flow_rag.schemas import (
    ChunkRecord,
    SchemaError,
    chunk_id,
    link_neighbors,
    sha256_text,
    validate_filter,
)


def _record(**overrides):
    base = dict(
        id="a" * 16 + "_0", text="hello", source_id="s", source_path="p",
        source_title="t", license="BSD", source_checksum="c", chunk_index=0,
        chunk_total=1, chunk_profile="reference", embedding_model="nomic-embed-text",
        embedding_dimension=768, tokenizer="cl100k_base", token_count=5,
    )
    base.update(overrides)
    return ChunkRecord(**base)


def test_one_byte_edit_changes_the_id():
    a = chunk_id("src", sha256_text("hello world"), 0)
    b = chunk_id("src", sha256_text("hello worlds"), 0)
    assert a != b


def test_same_content_different_source_differs():
    h = sha256_text("identical")
    assert chunk_id("source_a", h, 0) != chunk_id("source_b", h, 0)


def test_id_format_matches_the_mcp_pattern():
    import re
    assert re.fullmatch(r"[a-f0-9]{16}_\d+", chunk_id("s", sha256_text("x"), 3))


def test_empty_license_is_refused():
    with pytest.raises(SchemaError, match="empty license"):
        _record(license="  ").validate()


def test_neighbors_link_both_directions():
    records = link_neighbors([_record(id=f"{i:016x}_0", chunk_index=i) for i in range(3)])
    assert records[0].chunk_prev_id is None
    assert records[0].chunk_next_id == records[1].id
    assert records[2].chunk_next_id is None


def test_filter_allowlist_rejects_unknown_keys():
    validate_filter({"doc_type": "reference"})
    with pytest.raises(SchemaError):
        validate_filter({"source_checksum": "leak"})
