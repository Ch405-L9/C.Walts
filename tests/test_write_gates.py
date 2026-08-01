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
