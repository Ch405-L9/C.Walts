"""The invariants that keep production data unreachable."""

import pytest

from natural_flow_rag.settings import ConfigError, load_settings


def test_real_config_loads():
    s = load_settings()
    assert s.embedding.vector_dimension == 768
    assert s.embedding.normalize_vectors is False
    assert s.embedding.model_context_tokens == 2048
    assert s.collection.space == "cosine"


def test_writes_are_disabled_by_default():
    assert load_settings().writes_allowed is False
    with pytest.raises(ConfigError, match="writes are disabled"):
        load_settings().assert_writes_allowed("test")


def test_production_chroma_path_is_unreachable():
    s = load_settings()
    with pytest.raises(ConfigError, match="escapes the project root"):
        s.resolve_inside_project("/home/t0n34781/projects/badgr_harness/rag_db")


def test_traversal_out_of_project_is_refused():
    s = load_settings()
    with pytest.raises(ConfigError, match="escapes the project root"):
        s.resolve_inside_project("../../../etc")


def test_collection_allowlist_is_enforced():
    s = load_settings()
    s.collection.assert_allowed("badgr_natural_flow_v1")
    for forbidden in ("badgr_corpus", "job_opportunities", "social_lab"):
        with pytest.raises(ConfigError, match="not allowlisted"):
            s.collection.assert_allowed(forbidden)
