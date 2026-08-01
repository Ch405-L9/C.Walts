"""RRF against hand-computed values — no dependencies, fully deterministic."""

from natural_flow_rag.fusion import reciprocal_rank_fusion


def test_hand_computed_scores():
    fused = reciprocal_rank_fusion(["a", "b"], ["b", "c"], rrf_k=60)
    scores = {h.chunk_id: h.score for h in fused}
    assert scores["a"] == 1 / 61
    assert scores["b"] == 1 / 62 + 1 / 61
    assert scores["c"] == 1 / 62
    # b appears in both lists, so it must outrank both single-list documents.
    assert fused[0].chunk_id == "b"


def test_found_by_attribution():
    fused = {h.chunk_id: h.found_by for h in reciprocal_rank_fusion(["a"], ["b"])}
    assert fused == {"a": "dense", "b": "lexical"}


def test_deterministic_on_ties():
    a = [h.chunk_id for h in reciprocal_rank_fusion(["x", "y"], [])]
    b = [h.chunk_id for h in reciprocal_rank_fusion(["x", "y"], [])]
    assert a == b


def test_empty_inputs():
    assert reciprocal_rank_fusion([], []) == []
