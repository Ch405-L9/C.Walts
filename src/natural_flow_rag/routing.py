"""Deterministic content understanding and routing profiles.

The runtime classifier is deliberately conservative. Caller metadata wins, text
signals are combined rather than triggered by one keyword, and ambiguous input
falls back to a neutral delivery profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CONTENT_MODES = frozenset(
    {
        "narrative",
        "dialogue",
        "informational",
        "instructional",
        "persuasive",
        "reflective",
        "compliance",
    }
)
DOMAINS = frozenset(
    {"general", "educational", "technical", "commercial", "professional", "compliance"}
)
AUDIENCES = frozenset({"children", "general", "adult", "professional"})
GENRES = frozenset(
    {"neutral", "children", "horror_suspense", "comedy", "drama", "action", "reflective"}
)

# Auditable runtime preference policy. These are preferences only: the
# runtime deliberately falls back to the broader approved corpus when sparse.
ROUTE_REGISTER_PREFERENCES: dict[str, frozenset[str]] = {
    "general": frozenset(),
    "educational": frozenset({"technical_explainer", "educational_explainer"}),
    "technical": frozenset({"technical_explainer", "professional_introduction"}),
    "commercial": frozenset({"commercial"}),
    "professional": frozenset({"professional_introduction"}),
    "compliance": frozenset({"compliance"}),
}


def preferred_registers(profile: ContentProfile) -> frozenset[str]:
    """Return auditable preferred registers for a route, never hard filters."""
    if profile.register:
        return frozenset({profile.register})
    return ROUTE_REGISTER_PREFERENCES.get(profile.domain, frozenset())


_DIALOGUE = re.compile(r'(^|\n)\s*(?:[A-Z][\w -]{1,24}:|["“])|["”]', re.M)
_FIRST_PERSON = re.compile(r"\b(?:I|my|me|we|our|us)\b", re.I)
_IMPERATIVE = re.compile(
    r"(?:^|[.!?]\s*)(?:step\s+\d+\s*:\s*)?"
    r"(?:install|configure|run|click|select|enter|copy|open|create|set|use|connect|ensure)\b",
    re.I,
)

_SIGNALS: dict[str, tuple[str, ...]] = {
    "children": (
        "child",
        "children",
        "kid",
        "comic",
        "storybook",
        "playground",
        "giggle",
        "puppy",
        "cartoon",
        "dog",
        "boat",
        "map",
        "island",
        "sunset",
    ),
    "horror_suspense": (
        "shadow",
        "blood",
        "whisper",
        "grave",
        "dark",
        "scream",
        "haunt",
        "terror",
        "footsteps",
        "corridor",
        "stairs",
        "creak",
        "knocks",
        "bedroom door",
        "second floor",
    ),
    "educational": (
        "geography",
        "latitude",
        "longitude",
        "continent",
        "capital",
        "region",
        "river",
        "mountain",
        "climate",
        "located",
    ),
    "technical": (
        "api",
        "server",
        "database",
        "oauth",
        "endpoint",
        "token",
        "parameter",
        "configure",
        "command",
        "procedure",
        "battery",
        "electrode",
        "electrolyte",
        "lithium",
        "ions",
        "electrons",
        "circuit",
        "charging",
    ),
    "commercial": (
        "buy",
        "order",
        "offer",
        "sale",
        "subscribe",
        "discover",
        "limited",
        "call",
        "visit",
        "free",
    ),
    "reflective": (
        "remember",
        "memories",
        "looking back",
        "felt",
        "years ago",
        "quiet",
        "wondered",
        "journey",
    ),
    "compliance": ("must", "required", "policy", "audit", "prohibited", "shall", "compliance"),
}


@dataclass(frozen=True)
class ContentProfile:
    schema_version: int = 1
    content_mode: str = "narrative"
    domain: str = "general"
    audience: str = "general"
    genre: str = "neutral"
    register: str | None = None
    confidence: float = 0.0
    fallback_used: bool = True
    reason_codes: tuple[str, ...] = field(default_factory=lambda: ("neutral_clear",))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "content_mode": self.content_mode,
            "domain": self.domain,
            "audience": self.audience,
            "genre": self.genre,
            "register": self.register,
            "confidence": self.confidence,
            "fallback_used": self.fallback_used,
            "reason_codes": list(self.reason_codes),
        }


def _valid(value: Any, allowed: frozenset[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _explicit(metadata: dict[str, Any], key: str, allowed: frozenset[str]) -> str | None:
    return _valid(metadata.get(key), allowed)


def _count_signals(text: str) -> dict[str, int]:
    lowered = text.casefold()
    return {name: sum(lowered.count(term) for term in terms) for name, terms in _SIGNALS.items()}


class ContentClassifier:
    """Metadata-first, deterministic classifier with an injectable future model seam."""

    def classify(self, text: str, metadata: dict[str, Any] | None = None) -> ContentProfile:
        if not text or not text.strip():
            raise ValueError("text must be non-empty")
        metadata = dict(metadata or {})
        explicit_mode = _explicit(metadata, "content_mode", CONTENT_MODES)
        explicit_domain = _explicit(metadata, "domain", DOMAINS)
        explicit_audience = _explicit(metadata, "audience", AUDIENCES)
        explicit_genre = _explicit(metadata, "genre", GENRES)
        explicit_register = (
            metadata.get("register") if isinstance(metadata.get("register"), str) else None
        )

        signals = _count_signals(text)
        dialogue = bool(_DIALOGUE.search(text))
        imperative = bool(_IMPERATIVE.search(text))
        first_person = bool(_FIRST_PERSON.search(text))
        scores = dict(signals)
        if dialogue:
            scores["children"] += 1
            scores["comedy"] = scores.get("comedy", 0) + 1
        if imperative:
            scores["technical"] += 1
        if first_person:
            scores["reflective"] += 1

        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        best_name, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0
        strong = best_score >= 2 and best_score > second_score

        genre = explicit_genre
        if genre is None and strong:
            genre = {
                "children": "children",
                "horror_suspense": "horror_suspense",
                "reflective": "reflective",
            }.get(best_name, "neutral")
        genre = genre or "neutral"

        domain = explicit_domain
        if domain is None and strong:
            domain = {
                "educational": "educational",
                "technical": "technical",
                "commercial": "commercial",
                "compliance": "compliance",
            }.get(best_name, "general")
        domain = domain or "general"

        audience = explicit_audience or ("children" if genre == "children" else "general")
        mode = explicit_mode
        if mode is None:
            if dialogue:
                mode = "dialogue"
            elif best_name in {"educational"}:
                mode = "informational"
            elif best_name in {"technical", "compliance"}:
                mode = "instructional" if best_name != "compliance" else "compliance"
            elif best_name == "commercial":
                mode = "persuasive"
            elif best_name == "reflective" or first_person:
                mode = "reflective"
            else:
                mode = "narrative"

        register = explicit_register
        if register is None:
            register = {
                "technical": "technical_explainer",
                "commercial": "commercial",
                "reflective": "reflective_narration",
                "compliance": "compliance",
            }.get(best_name)

        explicit = (
            explicit_mode,
            explicit_domain,
            explicit_audience,
            explicit_genre,
            explicit_register,
        )
        fallback = not strong and not any(explicit)
        confidence = (
            0.35
            if fallback
            else min(0.98, 0.55 + 0.08 * best_score + (0.1 if best_score > second_score else 0))
        )
        reasons: list[str] = []
        if any(explicit):
            reasons.append("explicit_metadata")
        if dialogue:
            reasons.append("dialogue_markers")
        if imperative:
            reasons.append("imperative_structure")
        if strong:
            reasons.append(f"multi_signal_{best_name}")
        if fallback:
            reasons.append("neutral_clear")

        return ContentProfile(
            content_mode=mode,
            domain=domain,
            audience=audience,
            genre=genre,
            register=register,
            confidence=round(confidence, 2),
            fallback_used=fallback,
            reason_codes=tuple(reasons),
        )


__all__ = [
    "AUDIENCES",
    "CONTENT_MODES",
    "ContentClassifier",
    "ContentProfile",
    "DOMAINS",
    "GENRES",
    "ROUTE_REGISTER_PREFERENCES",
    "preferred_registers",
]
