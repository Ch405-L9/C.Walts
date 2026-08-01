"""The gates that stand between this code and the production corpus.

These are the tests that matter most. The audit found a 2,372-chunk production
collection in a world-writable file under live cron write pressure; every
assertion here exists to prove this project cannot reach it.
"""

import pytest

from natural_flow_rag.settings import ConfigError, load_settings
from natural_flow_rag.vector_store import VectorStore, VectorStoreError


@pytest.fixture
def store():
    return VectorStore(load_settings())


def test_create_is_refused_while_writes_disabled(store):
    with pytest.raises(ConfigError, match="writes are disabled"):
        store.create()


def test_add_is_refused_while_writes_disabled(store):
    with pytest.raises(ConfigError, match="writes are disabled"):
        store.add(["a" * 16 + "_0"], [[0.0] * 768], ["x"], [{"license": "x"}])


@pytest.mark.parametrize("production", ["badgr_corpus", "job_opportunities", "social_lab"])
def test_production_collections_are_unreachable(store, production):
    """Not merely 'not written to' — not nameable."""
    with pytest.raises(ConfigError, match="not allowlisted"):
        store.create(production)
    with pytest.raises(ConfigError, match="not allowlisted"):
        store.query([0.0] * 768, 5, name=production)


def test_wrong_dimension_query_is_refused(store):
    """384-d against a 768-d collection is audit hazard B2 in one line."""
    with pytest.raises(VectorStoreError, match="384-d vector against a 768-d"):
        store.query([0.0] * 384, 5)


def test_persistence_path_is_inside_the_project(store):
    assert store.path.is_relative_to(load_settings().project_root.resolve())
    assert "badgr_harness" not in str(store.path)


# ── stale-chunk deletion ─────────────────────────────────────────────────────
#
# Deletion is the only operation in this project that can lose data a rebuild
# cannot reproduce, so every refusal on the path gets its own assertion.


def test_delete_is_refused_while_writes_disabled(store):
    with pytest.raises(ConfigError, match="writes are disabled"):
        store.delete(["a" * 16 + "_0"])


def test_delete_is_refused_on_a_production_collection(store):
    """The write gate must not be the only thing standing in the way."""
    with pytest.raises(ConfigError, match="not allowlisted"):
        store.delete(["a" * 16 + "_0"], name="badgr_corpus")


def test_delete_refuses_an_empty_id_list(monkeypatch, store):
    """Chroma spells 'delete everything' as delete() with no ids.

    An empty stale set must therefore be a refusal, not a call — otherwise the
    difference between 'nothing to remove' and 'remove the collection' is one
    absent argument.
    """
    monkeypatch.setenv("NFR_ALLOW_WRITES", "true")
    assert store.settings.writes_allowed, "precondition: the write gate is open"
    with pytest.raises(VectorStoreError, match="empty id list"):
        store.delete([])
