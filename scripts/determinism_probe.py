#!/usr/bin/env python3
"""Gate 1.2 Stage 1 determinism probe.

Read-only against the production store. Scratch Chroma indexes are built under a
temporary directory and removed before exit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.fusion import reciprocal_rank_fusion  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.retrieval import Retriever  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.vector_store import VectorStore  # noqa: E402

DEFAULT_OUT = PROJECT_ROOT / "docs" / "evidence" / "gate1_2-determinism.json"


def vector_digest(vector: Iterable[float]) -> str:
    values = [float(v) for v in vector]
    return hashlib.sha256(struct.pack(f"<{len(values)}d", *values)).hexdigest()


def normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("cannot normalize a zero vector")
    return matrix / norms


def exact_cosine_ranking(
    ids: list[str],
    vectors: np.ndarray,
    query_vector: Iterable[float],
    *,
    k: int,
) -> list[dict[str, object]]:
    """Return exact cosine-distance ranking, with chunk_id as deterministic tie-break."""
    if len(ids) != len(vectors):
        raise ValueError("ids and vectors length mismatch")
    query = np.asarray([list(map(float, query_vector))], dtype=np.float64)
    corpus = normalize(np.asarray(vectors, dtype=np.float64))
    query = normalize(query)[0]
    similarities = corpus @ query
    distances = 1.0 - similarities
    ordered = sorted(
        range(len(ids)),
        key=lambda index: (float(distances[index]), ids[index]),
    )[:k]
    return [
        {
            "chunk_id": ids[index],
            "rank": rank,
            "distance": round(float(distances[index]), 12),
        }
        for rank, index in enumerate(ordered, start=1)
    ]


def recall_at_k(expected: list[str], observed: list[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    target = set(expected[:k])
    if not target:
        return 0.0
    return len(target & set(observed[:k])) / len(target)


def kendall_tau_with_absent(reference: list[str], observed: list[str], k: int) -> float | None:
    """Kendall tau over the union of two top-k lists, absent items ranked k + 1."""
    items = sorted(set(reference[:k]) | set(observed[:k]))
    if len(items) < 2:
        return None

    ref_rank = {chunk_id: rank for rank, chunk_id in enumerate(reference[:k], start=1)}
    obs_rank = {chunk_id: rank for rank, chunk_id in enumerate(observed[:k], start=1)}
    absent = k + 1
    concordant = 0
    discordant = 0
    for left_index, left in enumerate(items):
        for right in items[left_index + 1 :]:
            ref_delta = ref_rank.get(left, absent) - ref_rank.get(right, absent)
            obs_delta = obs_rank.get(left, absent) - obs_rank.get(right, absent)
            product = ref_delta * obs_delta
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
    total = concordant + discordant
    if total == 0:
        return 1.0
    return (concordant - discordant) / total


def marker_hit(metadata: dict[str, Any], markers: list[str]) -> str | None:
    haystack = " ".join(
        str(metadata.get(key, ""))
        for key in ("section_heading", "source_id", "source_title", "register")
    )
    lowered = haystack.lower()
    for marker in markers:
        if marker.lower() in lowered:
            return marker
    return None


def result_signature(result: Any, markers: list[str]) -> dict[str, object]:
    ranked = [chunk for chunk in result.chunks if not chunk.is_neighbor]
    matched = next(
        (
            marker
            for chunk in ranked
            if (marker := marker_hit(chunk.metadata, markers))
        ),
        None,
    ) if markers else None
    return {
        "ranked_chunk_ids": [chunk.chunk_id for chunk in ranked],
        "matched_marker": matched,
        "useful_hit": bool(matched) if markers else None,
    }


def load_cases(limit: int | None = None) -> list[dict[str, Any]]:
    spec = yaml.safe_load((PROJECT_ROOT / "eval" / "expectations.yaml").read_text())
    cases = [case for case in spec["cases"] if case.get("mode", "retrieval") == "retrieval"]
    return cases[:limit] if limit is not None else cases


def fetch_collection_payload(store: VectorStore) -> dict[str, Any]:
    collection = store.get()
    payload = collection.get(include=["embeddings", "documents", "metadatas"])
    ids = list(payload["ids"])
    order = sorted(range(len(ids)), key=lambda index: ids[index])
    return {
        "ids": [ids[index] for index in order],
        "embeddings": [list(map(float, payload["embeddings"][index])) for index in order],
        "documents": [payload["documents"][index] or "" for index in order],
        "metadatas": [payload["metadatas"][index] or {} for index in order],
    }


def dense_ann_ids(store: VectorStore, vector: list[float], k: int) -> tuple[list[str], list[float]]:
    raw = store.query(embedding=vector, n_results=k)
    return (
        list(raw.get("ids", [[]])[0]),
        [float(distance) for distance in list(raw.get("distances", [[]])[0])],
    )


def fused_signature_from_dense_ids(
    *,
    dense_ids: list[str],
    query: str,
    markers: list[str],
    lexical: LexicalIndex,
    by_id: dict[str, dict[str, Any]],
    final_k: int,
    lexical_k: int,
    rrf_k: int,
    forbidden_doc_types: set[str],
    exclude_negative: bool,
) -> dict[str, object]:
    lexical_ids = [hit.chunk_id for hit in lexical.search(query, lexical_k)]
    fused = reciprocal_rank_fusion(dense_ids, lexical_ids, rrf_k=rrf_k)
    ranked: list[str] = []
    for hit in fused:
        metadata = by_id.get(hit.chunk_id, {}).get("metadata", {})
        doc_type = str(metadata.get("doc_type"))
        if doc_type in forbidden_doc_types:
            continue
        if exclude_negative and doc_type == "negative_pattern":
            continue
        if hit.chunk_id not in by_id:
            continue
        ranked.append(hit.chunk_id)
        if len(ranked) >= final_k:
            break
    matched = next(
        (
            marker
            for chunk_id in ranked
            if (marker := marker_hit(by_id[chunk_id]["metadata"], markers))
        ),
        None,
    ) if markers else None
    return {
        "ranked_chunk_ids": ranked,
        "matched_marker": matched,
        "useful_hit": bool(matched) if markers else None,
    }


def build_scratch_query(
    payload: dict[str, Any],
    query_vectors: dict[str, list[float]],
    k: int,
) -> dict[str, dict[str, list[Any]]]:
    import chromadb

    tempdir = Path(tempfile.mkdtemp(prefix="cwalts-stage1-hnsw-"))
    try:
        client = chromadb.PersistentClient(path=str(tempdir))
        collection = client.create_collection(
            name="stage1_probe",
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"created_by": "stage1_determinism_probe"},
        )
        collection.add(
            ids=payload["ids"],
            embeddings=payload["embeddings"],
            documents=payload["documents"],
            metadatas=payload["metadatas"],
        )
        out: dict[str, dict[str, list[Any]]] = {}
        for case_id, vector in query_vectors.items():
            raw = collection.query(
                query_embeddings=[vector],
                n_results=k,
                include=["distances"],
            )
            out[case_id] = {
                "ids": list(raw.get("ids", [[]])[0]),
                "distances": [float(distance) for distance in list(raw.get("distances", [[]])[0])],
            }
        return out
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def summarize_recalls(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "mean": None, "max": None}
    return {
        "min": round(min(values), 6),
        "mean": round(sum(values) / len(values), 6),
        "max": round(max(values), 6),
    }


def summarize_nullable_metrics(values: list[float | None]) -> dict[str, float | None]:
    present = [value for value in values if value is not None]
    if not present:
        return {"min": None, "mean": None, "max": None}
    return {
        "min": round(min(present), 6),
        "mean": round(sum(present) / len(present), 6),
        "max": round(max(present), 6),
    }


def summarize_distance_variance(
    runs: list[dict[str, Any]],
    oracle: dict[str, list[dict[str, object]]],
) -> dict[str, float | int | None]:
    """Summarize same-rank distance variance across repeated ANN query results."""
    by_case_rank: dict[tuple[str, int], list[float]] = {}
    max_abs_delta_to_oracle = 0.0
    compared_positions = 0

    for run in runs:
        for case in run["cases"]:
            case_id = str(case["id"])
            distances = case.get("ann_distances", [])
            for rank_index, distance in enumerate(distances):
                key = (case_id, rank_index + 1)
                by_case_rank.setdefault(key, []).append(float(distance))
                if rank_index < len(oracle[case_id]):
                    oracle_distance = float(oracle[case_id][rank_index]["distance"])
                    max_abs_delta_to_oracle = max(
                        max_abs_delta_to_oracle,
                        abs(float(distance) - oracle_distance),
                    )
                    compared_positions += 1

    variances = [
        float(np.var(values, dtype=np.float64))
        for values in by_case_rank.values()
        if len(values) > 1
    ]
    if not variances:
        return {
            "positions": 0,
            "min_variance": None,
            "mean_variance": None,
            "max_variance": None,
            "max_abs_delta_to_oracle": None,
            "compared_positions": compared_positions,
        }
    return {
        "positions": len(variances),
        "min_variance": round(min(variances), 18),
        "mean_variance": round(sum(variances) / len(variances), 18),
        "max_variance": round(max(variances), 18),
        "max_abs_delta_to_oracle": round(max_abs_delta_to_oracle, 12),
        "compared_positions": compared_positions,
    }


def decide_stage1_disposition(
    *,
    embedding_byte_stable: bool,
    fixed_recall_summary: dict[str, float | None],
    rebuilt_recall_summary: dict[str, float | None],
    fixed_kendall_summary: dict[str, float | None],
    rebuilt_kendall_summary: dict[str, float | None],
    fixed_verdict_flips: dict[str, object],
    rebuilt_verdict_flips: dict[str, object],
) -> dict[str, object]:
    criteria = {
        "embedding_byte_stable": embedding_byte_stable is True,
        "fixed_recall_min_is_1": fixed_recall_summary.get("min") == 1.0,
        "rebuilt_recall_min_is_1": rebuilt_recall_summary.get("min") == 1.0,
        "fixed_kendall_tau_min_is_1": fixed_kendall_summary.get("min") == 1.0,
        "rebuilt_kendall_tau_min_is_1": rebuilt_kendall_summary.get("min") == 1.0,
        "fixed_verdict_flips_zero": fixed_verdict_flips.get("verdict_flip_count") == 0,
        "rebuilt_verdict_flips_zero": rebuilt_verdict_flips.get("verdict_flip_count") == 0,
    }

    if all(criteria.values()):
        disposition = "cosmetic_float_noise"
    elif not criteria["embedding_byte_stable"]:
        disposition = "embedding_instability_detected"
    elif not (
        criteria["fixed_recall_min_is_1"]
        and criteria["rebuilt_recall_min_is_1"]
        and criteria["fixed_kendall_tau_min_is_1"]
        and criteria["rebuilt_kendall_tau_min_is_1"]
    ):
        disposition = "ann_oracle_rank_disagreement"
    else:
        disposition = "ranking_or_verdict_instability_detected"

    return {
        "disposition": disposition,
        "criteria": criteria,
        "nomic_embed_text_stays": all(criteria.values()),
        "thresholds_fit": False,
        "notes": [
            "Exact normalized-cosine NumPy oracle is used as dense ground truth at 84 vectors.",
            "No production ChromaDB or BM25 files are mutated by this probe.",
            "Distance fields remain diagnostic only and are not calibration inputs.",
        ],
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    settings = load_settings()
    store = VectorStore(settings)
    embedder = OllamaEmbedder(settings.embedding)
    lexical = LexicalIndex(settings.project_root / "var" / "bm25" / "index.json")
    retriever = Retriever(settings, store, embedder, lexical)
    cases = load_cases(args.case_limit)
    payload = fetch_collection_payload(store)
    vectors = np.asarray(payload["embeddings"], dtype=np.float64)
    by_id = {
        chunk_id: {"text": text, "metadata": metadata}
        for chunk_id, text, metadata in zip(
            payload["ids"], payload["documents"], payload["metadatas"], strict=True
        )
    }

    representative = [
        "dimension probe",
        cases[0]["query"],
        cases[min(7, len(cases) - 1)]["query"],
        cases[min(8, len(cases) - 1)]["query"],
        "What is ToBI?",
    ][: args.embedding_strings]

    embedding_repeat: list[dict[str, object]] = []
    for index, text in enumerate(representative, start=1):
        digests = [vector_digest(embedder.embed_one(text)) for _ in range(args.embedding_repeats)]
        embedding_repeat.append(
            {
                "probe": index,
                "sha256s": digests,
                "unique_sha256s": sorted(set(digests)),
                "byte_stable": len(set(digests)) == 1,
            }
        )

    dense_k = int(settings.retrieval.get("dense_candidates", 24))
    lexical_k = int(settings.retrieval.get("lexical_candidates", 24))
    final_k = int(settings.retrieval.get("final_chunks", 5))
    rrf_k = int(settings.retrieval.get("fusion", {}).get("rrf_k", 60))
    forbidden = {str(d) for d in settings.retrieval.get("forbid_doc_types_always", [])}

    query_vectors = {
        case["id"]: embedder.embed_one(" ".join(case["query"].split()))
        for case in cases
    }
    oracle: dict[str, list[dict[str, object]]] = {
        case["id"]: exact_cosine_ranking(
            payload["ids"], vectors, query_vectors[case["id"]], k=dense_k
        )
        for case in cases
    }

    fixed_runs: list[dict[str, Any]] = []
    for run_index in range(1, args.fixed_repeats + 1):
        case_results = []
        for case in cases:
            query = " ".join(case["query"].split())
            vector = embedder.embed_one(query)
            ann_ids, ann_distances = dense_ann_ids(store, vector, dense_k)
            exact_ids = [row["chunk_id"] for row in oracle[case["id"]]]
            result = retriever.search(query, k=final_k)
            case_results.append(
                {
                    "id": case["id"],
                    "ann_recall_at_dense_k": round(recall_at_k(exact_ids, ann_ids, dense_k), 6),
                    "ann_kendall_tau_at_dense_k": kendall_tau_with_absent(
                        exact_ids, ann_ids, dense_k
                    ),
                    "ann_distances": [round(distance, 12) for distance in ann_distances],
                    "ann_distance_min": round(min(ann_distances), 12) if ann_distances else None,
                    "ann_distance_max": round(max(ann_distances), 12) if ann_distances else None,
                    "verdict": result_signature(result, case.get("expect_any", []) or []),
                }
            )
        fixed_runs.append({"run": run_index, "cases": case_results})

    rebuilt_runs: list[dict[str, Any]] = []
    for run_index in range(1, args.rebuild_repeats + 1):
        scratch = build_scratch_query(payload, query_vectors, dense_k)
        case_results = []
        for case in cases:
            exact_ids = [row["chunk_id"] for row in oracle[case["id"]]]
            dense_ids = [str(chunk_id) for chunk_id in scratch[case["id"]]["ids"]]
            ann_distances = [float(distance) for distance in scratch[case["id"]]["distances"]]
            query = " ".join(case["query"].split())
            exclude_negative = not retriever.has_contrast_intent(query)
            verdict = fused_signature_from_dense_ids(
                dense_ids=dense_ids,
                query=query,
                markers=case.get("expect_any", []) or [],
                lexical=lexical,
                by_id=by_id,
                final_k=final_k,
                lexical_k=lexical_k,
                rrf_k=rrf_k,
                forbidden_doc_types=forbidden,
                exclude_negative=exclude_negative,
            )
            case_results.append(
                {
                    "id": case["id"],
                    "ann_recall_at_dense_k": round(recall_at_k(exact_ids, dense_ids, dense_k), 6),
                    "ann_kendall_tau_at_dense_k": kendall_tau_with_absent(
                        exact_ids, dense_ids, dense_k
                    ),
                    "ann_distances": [round(distance, 12) for distance in ann_distances],
                    "ann_distance_min": round(min(ann_distances), 12) if ann_distances else None,
                    "ann_distance_max": round(max(ann_distances), 12) if ann_distances else None,
                    "verdict": verdict,
                }
            )
        rebuilt_runs.append({"run": run_index, "cases": case_results})

    fixed_recalls = [
        case["ann_recall_at_dense_k"]
        for run in fixed_runs
        for case in run["cases"]
    ]
    rebuilt_recalls = [
        case["ann_recall_at_dense_k"]
        for run in rebuilt_runs
        for case in run["cases"]
    ]
    fixed_kendall = [
        case["ann_kendall_tau_at_dense_k"]
        for run in fixed_runs
        for case in run["cases"]
    ]
    rebuilt_kendall = [
        case["ann_kendall_tau_at_dense_k"]
        for run in rebuilt_runs
        for case in run["cases"]
    ]

    fixed_flips = verdict_flips(fixed_runs)
    rebuilt_flips = verdict_flips(rebuilt_runs)
    embedding_stable = all(row["byte_stable"] for row in embedding_repeat)
    fixed_recall_summary = summarize_recalls(fixed_recalls)
    rebuilt_recall_summary = summarize_recalls(rebuilt_recalls)
    fixed_kendall_summary = summarize_nullable_metrics(fixed_kendall)
    rebuilt_kendall_summary = summarize_nullable_metrics(rebuilt_kendall)
    decision = decide_stage1_disposition(
        embedding_byte_stable=embedding_stable,
        fixed_recall_summary=fixed_recall_summary,
        rebuilt_recall_summary=rebuilt_recall_summary,
        fixed_kendall_summary=fixed_kendall_summary,
        rebuilt_kendall_summary=rebuilt_kendall_summary,
        fixed_verdict_flips=fixed_flips,
        rebuilt_verdict_flips=rebuilt_flips,
    )

    return {
        "generated": datetime.now(UTC).isoformat(),
        "phase": "C.Walts v0.4 Gate 1.2 Stage 1 - determinism instrumentation",
        "version": "0.4.0-dev.2",
        "read_only_production_store": True,
        "scratch_indexes_removed": True,
        "collection": {
            "name": settings.collection.name,
            "count": len(payload["ids"]),
            "embedding_dimension": int(vectors.shape[1]),
        },
        "parameters": {
            "dense_k": dense_k,
            "lexical_k": lexical_k,
            "final_k": final_k,
            "embedding_repeats": args.embedding_repeats,
            "fixed_index_repeats": args.fixed_repeats,
            "rebuilt_index_repeats": args.rebuild_repeats,
            "case_count": len(cases),
        },
        "embedding_repeat": embedding_repeat,
        "embedding_byte_stable": embedding_stable,
        "oracle": {
            "kind": "exact_normalized_cosine_numpy",
            "tie_break": "chunk_id",
            "case_top_ids": {
                case_id: [row["chunk_id"] for row in rows[:final_k]]
                for case_id, rows in oracle.items()
            },
        },
        "fixed_index_repeated_queries": {
            "runs": fixed_runs,
            "recall_summary": fixed_recall_summary,
            "kendall_tau_summary": fixed_kendall_summary,
            "distance_variance_summary": summarize_distance_variance(fixed_runs, oracle),
            "verdict_flips": fixed_flips,
        },
        "rebuilt_index_fixed_vectors": {
            "runs": rebuilt_runs,
            "recall_summary": rebuilt_recall_summary,
            "kendall_tau_summary": rebuilt_kendall_summary,
            "distance_variance_summary": summarize_distance_variance(rebuilt_runs, oracle),
            "verdict_flips": rebuilt_flips,
        },
        "decision": decision,
    }


def verdict_flips(runs: list[dict[str, Any]]) -> dict[str, object]:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        for case in run["cases"]:
            by_case.setdefault(str(case["id"]), []).append(case["verdict"])
    flips = []
    for case_id, verdicts in sorted(by_case.items()):
        encoded = {json.dumps(verdict, sort_keys=True) for verdict in verdicts}
        if len(encoded) > 1:
            flips.append(case_id)
    return {
        "verdict_flip_count": len(flips),
        "cases": flips,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--embedding-repeats", type=int, default=10)
    parser.add_argument("--embedding-strings", type=int, default=5)
    parser.add_argument("--fixed-repeats", type=int, default=5)
    parser.add_argument("--rebuild-repeats", type=int, default=5)
    parser.add_argument("--case-limit", type=int, default=None)
    args = parser.parse_args()

    report = run_probe(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    fixed_flip_count = report["fixed_index_repeated_queries"]["verdict_flips"][
        "verdict_flip_count"
    ]
    rebuilt_flip_count = report["rebuilt_index_fixed_vectors"]["verdict_flips"][
        "verdict_flip_count"
    ]
    print(
        "determinism probe: "
        f"{report['collection']['count']} vectors, "
        f"embedding_byte_stable={report['embedding_byte_stable']}, "
        f"fixed_flips={fixed_flip_count}, "
        f"rebuilt_flips={rebuilt_flip_count}, "
        f"disposition={report['decision']['disposition']}"
    )
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
