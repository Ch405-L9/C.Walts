"""Runtime orchestration: profile, route, retrieve, and build a narration plan."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .analysis import analyze
from .narration import NarrationPlan, build_plan
from .retrieval import RetrievalResult, RetrievedChunk, Retriever
from .routing import ContentClassifier, ContentProfile, preferred_registers

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteResult:
    profile: ContentProfile
    retrieval: RetrievalResult | None
    chunks: tuple[RetrievedChunk, ...]
    summary: dict[str, Any]


def _compatible(chunk: RetrievedChunk, profile: ContentProfile) -> bool:
    metadata = chunk.metadata
    register = str(metadata.get("register", ""))
    return register in preferred_registers(profile)


class NarrationRuntime:
    def __init__(
        self,
        retriever: Retriever | None = None,
        classifier: ContentClassifier | None = None,
    ):
        self.retriever = retriever
        self.classifier = classifier or ContentClassifier()

    def route(self, text: str, metadata: dict[str, Any] | None = None, k: int = 5) -> RouteResult:
        profile = self.classifier.classify(text, metadata)
        if self.retriever is None:
            return RouteResult(
                profile,
                None,
                (),
                {
                    "route": profile.domain,
                    "confidence": profile.confidence,
                    "route_filter_applied": False,
                    "route_filter_relaxed": True,
                    "retrieval_confidence": 0.0,
                    "retrieval_count": 0,
                    "retrieved_chunk_ids": [],
                    "retrieval_sources": [],
                    "retrieval_arm": "unavailable",
                    "lexical_degraded": False,
                },
            )

        try:
            result = self.retriever.search(text, k=max(k, 8))
        except Exception as exc:  # retrieval must not block narration planning
            log.warning("retrieval failed route=%s error=%s", profile.domain, type(exc).__name__)
            return RouteResult(
                profile,
                None,
                (),
                {
                    "route": profile.domain,
                    "confidence": profile.confidence,
                    "route_filter_applied": False,
                    "route_filter_relaxed": True,
                    "retrieval_confidence": 0.0,
                    "retrieval_count": 0,
                    "retrieved_chunk_ids": [],
                    "retrieval_sources": [],
                    "retrieval_arm": "failed",
                    "lexical_degraded": True,
                    "fallback_reason": "retrieval_unavailable",
                },
            )

        compatible = [chunk for chunk in result.chunks if _compatible(chunk, profile)]
        ordered = compatible + [chunk for chunk in result.chunks if chunk not in compatible]
        relaxed = len(compatible) < min(k, 2)
        selected = tuple(ordered[:k])
        match_ratio = len(compatible) / len(result.chunks) if result.chunks else 0.0
        summary = {
            "route": profile.domain,
            "confidence": profile.confidence,
            "route_filter_applied": bool(compatible),
            "route_filter_relaxed": relaxed,
            "retrieval_confidence": round(
                min(1.0, match_ratio * 0.7 + (0.3 if result.chunks else 0.0)), 2
            ),
            "retrieval_count": len(selected),
            "retrieved_chunk_ids": [chunk.chunk_id for chunk in selected],
            "retrieval_sources": sorted({chunk.source_title for chunk in selected}),
            "retrieval_arm": "hybrid",
            "lexical_degraded": result.lexical_error is not None,
            "lexical_error_code": (
                result.lexical_error
                if isinstance(result.lexical_error, str)
                else "lexical_degraded"
            )
            if result.lexical_error
            else None,
        }
        return RouteResult(profile, result, selected, summary)

    def plan(self, text: str, metadata: dict[str, Any] | None = None, k: int = 5) -> NarrationPlan:
        route = self.route(text, metadata, k)
        flow = analyze(text)
        fallbacks = tuple(["neutral_clear"] if route.profile.fallback_used else [])
        if route.summary.get("route_filter_relaxed"):
            fallbacks += ("broader_retrieval",)
        return build_plan(text, route.profile, flow, route.summary, fallbacks)


__all__ = ["NarrationRuntime", "RouteResult"]
