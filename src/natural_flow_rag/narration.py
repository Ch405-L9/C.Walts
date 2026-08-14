"""Provider-neutral narration planning over the author's unchanged text."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .analysis import PACE_RANGES, FlowAnalysis
from .routing import ContentProfile

_DIALOGUE = re.compile(r'(^|\n)\s*[A-Z][\w -]{1,24}:|["“].+["”]', re.S)


@dataclass(frozen=True)
class Delivery:
    pace: str
    target_wpm: tuple[int, int]
    pause_tendency: str
    emphasis_tendency: str
    energy: str
    expressiveness: str
    pitch_tendency: str
    volume_tendency: str
    dialogue_handling: str
    pronunciation_hints: tuple[str, ...] = ()
    voice_character_hint: str = "clear_neutral"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pace": self.pace,
            "target_wpm": list(self.target_wpm),
            "pause_tendency": self.pause_tendency,
            "emphasis_tendency": self.emphasis_tendency,
            "energy": self.energy,
            "expressiveness": self.expressiveness,
            "pitch_tendency": self.pitch_tendency,
            "volume_tendency": self.volume_tendency,
            "dialogue_handling": self.dialogue_handling,
            "pronunciation_hints": list(self.pronunciation_hints),
            "voice_character_hint": self.voice_character_hint,
        }


@dataclass(frozen=True)
class NarrationSegment:
    text: str
    text_sha256: str
    segment_index: int
    dialogue: bool
    pause_before_ms: int
    pause_after_ms: int
    emphasis: str
    pace_modifier: float
    energy_modifier: float
    pitch_tendency: str
    pronunciation_hints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "text_sha256": self.text_sha256,
            "segment_index": self.segment_index,
            "dialogue": self.dialogue,
            "pause_before_ms": self.pause_before_ms,
            "pause_after_ms": self.pause_after_ms,
            "emphasis": self.emphasis,
            "pace_modifier": self.pace_modifier,
            "energy_modifier": self.energy_modifier,
            "pitch_tendency": self.pitch_tendency,
            "pronunciation_hints": list(self.pronunciation_hints),
        }


@dataclass(frozen=True)
class NarrationPlan:
    schema_version: int
    source_text: str
    source_text_sha256: str
    content_profile: dict[str, Any]
    delivery: dict[str, Any]
    segments: tuple[NarrationSegment, ...]
    retrieval_summary: dict[str, Any]
    preservation: dict[str, Any]
    fallbacks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_text": self.source_text,
            "source_text_sha256": self.source_text_sha256,
            "content_profile": self.content_profile,
            "delivery": self.delivery,
            "segments": [segment.to_dict() for segment in self.segments],
            "retrieval_summary": self.retrieval_summary,
            "preservation": self.preservation,
            "fallbacks": list(self.fallbacks),
        }


def _delivery(profile: ContentProfile, flow: FlowAnalysis) -> Delivery:
    fallback = profile.fallback_used
    ranges = PACE_RANGES.get(profile.register or "", (115, 145))
    if profile.genre == "children":
        return Delivery(
            "moderate", (125, 155), "natural", "light", "light", "engaging", "bright",
            "moderate", "dialogue_aware", voice_character_hint="age_appropriate_clear",
        )
    if profile.genre == "horror_suspense":
        return Delivery(
            "deliberate", (95, 125), "deliberate", "restrained", "controlled", "restrained",
            "slightly_low", "moderate", "dialogue_aware", voice_character_hint="controlled_tension",
        )
    if profile.domain == "educational":
        return Delivery(
            "moderate", (115, 145), "natural", "key_terms", "moderate", "restrained",
            "neutral", "moderate", "standard",
        )
    if profile.domain == "technical":
        return Delivery(
            "density_aware", ranges, "clause_boundaries", "key_terms", "moderate", "restrained",
            "neutral", "moderate", "standard",
        )
    if profile.domain == "commercial":
        return Delivery(
            "forward", ranges, "natural", "cta", "moderately_high", "engaging", "slightly_high",
            "moderate", "standard",
        )
    if profile.genre == "reflective":
        return Delivery(
            "deliberate", ranges, "spacious", "key_phrases", "low", "restrained", "slightly_low",
            "soft", "standard",
        )
    if fallback:
        return Delivery(
            "moderate", (115, 145), "natural", "normal", "moderate", "restrained", "neutral",
            "moderate", "standard",
        )
    return Delivery(
        "moderate", ranges, "natural", "key_phrases", "moderate", "restrained", "neutral",
        "moderate", "standard",
    )


def build_plan(
    text: str,
    profile: ContentProfile,
    flow: FlowAnalysis,
    retrieval_summary: dict[str, Any],
    fallbacks: tuple[str, ...] = (),
) -> NarrationPlan:
    if not text.strip():
        raise ValueError("text must be non-empty")
    delivery = _delivery(profile, flow)
    segments: list[NarrationSegment] = []
    for index, sentence in enumerate(flow.per_sentence):
        segment_text = sentence.text
        dialogue = bool(_DIALOGUE.search(segment_text))
        pause_after = 500 if segment_text.endswith(('.', '?', '!')) else 250
        if profile.genre == "horror_suspense":
            pause_after += 150
        if profile.genre == "reflective":
            pause_after += 100
        emphasis = "dialogue" if dialogue else (
            "key_terms" if profile.domain in {"technical", "educational"} else "none"
        )
        segments.append(
            NarrationSegment(
                text=segment_text,
                text_sha256=hashlib.sha256(segment_text.encode("utf-8")).hexdigest(),
                segment_index=index,
                dialogue=dialogue,
                pause_before_ms=120 if index else 0,
                pause_after_ms=pause_after,
                emphasis=emphasis,
                pace_modifier=0.95 if profile.domain == "technical" else 1.0,
                energy_modifier=(
                    0.85 if profile.genre == "horror_suspense"
                    else (1.08 if profile.genre == "children" else 1.0)
                ),
                pitch_tendency=delivery.pitch_tendency,
            )
        )
    preservation = {
        "source_text_preserved": True,
        "rewrite_performed": False,
        "normalization_authorized": False,
    }
    return NarrationPlan(
        schema_version=1,
        source_text=text,
        source_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        content_profile=profile.to_dict(),
        delivery=delivery.to_dict(),
        segments=tuple(segments),
        retrieval_summary=retrieval_summary,
        preservation=preservation,
        fallbacks=fallbacks,
    )


__all__ = ["Delivery", "NarrationPlan", "NarrationSegment", "build_plan"]
