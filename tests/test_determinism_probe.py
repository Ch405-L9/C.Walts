from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.determinism_probe import (  # noqa: E402
    exact_cosine_ranking,
    kendall_tau_with_absent,
    recall_at_k,
    summarize_distance_variance,
    summarize_nullable_metrics,
    vector_digest,
)


def test_exact_cosine_ranking_uses_chunk_id_tie_break() -> None:
    ids = ["b", "a", "c"]
    vectors = np.asarray(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ]
    )

    ranked = exact_cosine_ranking(ids, vectors, [1.0, 0.0], k=3)

    assert [row["chunk_id"] for row in ranked] == ["a", "b", "c"]
    assert ranked[0]["distance"] == 0.0


def test_recall_at_k_scores_overlap() -> None:
    assert recall_at_k(["a", "b", "c"], ["b", "x", "a"], 3) == 2 / 3


def test_kendall_tau_reports_identical_and_reversed_rankings() -> None:
    assert kendall_tau_with_absent(["a", "b", "c"], ["a", "b", "c"], 3) == 1.0
    assert kendall_tau_with_absent(["a", "b", "c"], ["c", "b", "a"], 3) == -1.0


def test_vector_digest_changes_with_float_bytes() -> None:
    assert vector_digest([0.0, 1.0]) == vector_digest([0.0, 1.0])
    assert vector_digest([0.0, 1.0]) != vector_digest([0.0, 1.0000000001])


def test_summarize_nullable_metrics_ignores_absent_values() -> None:
    assert summarize_nullable_metrics([1.0, None, 0.5]) == {
        "min": 0.5,
        "mean": 0.75,
        "max": 1.0,
    }


def test_summarize_distance_variance_compares_same_rank_to_oracle() -> None:
    runs = [
        {
            "cases": [
                {
                    "id": "EVAL-X",
                    "ann_distances": [0.1, 0.2],
                }
            ]
        },
        {
            "cases": [
                {
                    "id": "EVAL-X",
                    "ann_distances": [0.1, 0.22],
                }
            ]
        },
    ]
    oracle = {
        "EVAL-X": [
            {"distance": 0.1},
            {"distance": 0.2},
        ]
    }

    summary = summarize_distance_variance(runs, oracle)

    assert summary["positions"] == 2
    assert summary["min_variance"] == 0.0
    assert summary["max_variance"] == 0.0001
    assert summary["max_abs_delta_to_oracle"] == 0.02
    assert summary["compared_positions"] == 4
