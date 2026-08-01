"""Sentence-rhythm and information-flow measurement.

Prompt C §2 asks for rhythm, cadence, and information-flow analysis. This module
*measures*; it does not judge style and it does not rewrite. Everything it
reports is a count derived from the surface text, so two runs over the same
paragraph give the same answer and a reviewer can check any number by hand.

The thresholds are the ones stated in the approved corpus
(`market_voice_delivery_rules.md`): one principal thought per breath group,
varied sentence length, direct verbs over stacked nouns, and register-dependent
pace ranges. They are flags for a human or a calling model to act on — not a
score, and not a verdict.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

_SENTENCE = re.compile(r"[^.!?]+[.!?]*")
_WORD = re.compile(r"[A-Za-z0-9''`-]+")

# Breath groups: a comma, semicolon, colon, dash, or coordinating conjunction is
# where an English reader can take a breath without breaking the thought.
_BREATH_BOUNDARY = re.compile(r"[,;:—–]| \b(and|but|or|so|because|while|which|that)\b ", re.I)

# Noun stacking, e.g. "implementation configuration initialization process". Long
# words with nominalizing endings, three or more in a row, are the reliable
# signal — this is the pattern the corpus names as hard to read aloud.
_NOMINAL = re.compile(
    r"\b\w*(?:tion|sion|ment|ance|ence|ity|ness|ing|ization|isation)\b", re.I
)

_PASSIVE = re.compile(r"\b(is|are|was|were|be|been|being)\s+\w+(?:ed|en)\b", re.I)

_FILLER = (
    "in order to", "it should be noted", "it is important to note", "as previously",
    "at this point in time", "due to the fact that", "for the purpose of",
)

# Register pace ranges, quoted from the approved market rules. These are test
# targets, not laws — the corpus says so explicitly and so does this docstring.
PACE_RANGES = {
    "commercial": (140, 165),
    "professional_introduction": (135, 160),
    "technical_explainer": (90, 135),
    "reflective_narration": (90, 120),
    "compliance": (85, 125),
}


@dataclass
class SentenceMetrics:
    text: str
    words: int
    breath_groups: int
    words_per_group: float
    nominal_run: int
    passive: bool


@dataclass
class FlowAnalysis:
    words: int
    sentences: int
    mean_sentence_words: float
    median_sentence_words: float
    longest_sentence_words: int
    sentence_length_variation: float
    breath_groups: int
    mean_words_per_breath_group: float
    passive_sentences: int
    longest_nominal_run: int
    filler_phrases: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    per_sentence: list[SentenceMetrics] = field(default_factory=list)
    estimated_seconds: dict[str, list[float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "words": self.words,
            "sentences": self.sentences,
            "mean_sentence_words": round(self.mean_sentence_words, 1),
            "median_sentence_words": round(self.median_sentence_words, 1),
            "longest_sentence_words": self.longest_sentence_words,
            "sentence_length_variation": round(self.sentence_length_variation, 2),
            "breath_groups": self.breath_groups,
            "mean_words_per_breath_group": round(self.mean_words_per_breath_group, 1),
            "passive_sentences": self.passive_sentences,
            "longest_nominal_run": self.longest_nominal_run,
            "filler_phrases": self.filler_phrases,
            "flags": self.flags,
            "estimated_seconds_by_register": self.estimated_seconds,
            "per_sentence": [
                {
                    "words": s.words,
                    "breath_groups": s.breath_groups,
                    "words_per_group": round(s.words_per_group, 1),
                    "longest_nominal_run": s.nominal_run,
                    "passive": s.passive,
                    "excerpt": s.text[:60],
                }
                for s in self.per_sentence
            ],
            "note": (
                "Measurements only. Pace ranges are the approved corpus's test "
                "targets, not universal facts; delivery adapts to register and "
                "information density."
            ),
        }


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _longest_nominal_run(words: list[str]) -> int:
    longest = run = 0
    for word in words:
        if _NOMINAL.fullmatch(word) and len(word) > 6:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def analyze(text: str) -> FlowAnalysis:
    sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
    all_words = _words(text)

    per_sentence: list[SentenceMetrics] = []
    for sentence in sentences:
        words = _words(sentence)
        groups = len(_BREATH_BOUNDARY.findall(sentence)) + 1
        per_sentence.append(
            SentenceMetrics(
                text=sentence,
                words=len(words),
                breath_groups=groups,
                words_per_group=len(words) / groups if groups else float(len(words)),
                nominal_run=_longest_nominal_run(words),
                passive=bool(_PASSIVE.search(sentence)),
            )
        )

    lengths = [s.words for s in per_sentence] or [0]
    groups_total = sum(s.breath_groups for s in per_sentence)
    lowered = text.lower()

    analysis = FlowAnalysis(
        words=len(all_words),
        sentences=len(sentences),
        mean_sentence_words=statistics.fmean(lengths),
        median_sentence_words=statistics.median(lengths),
        longest_sentence_words=max(lengths),
        sentence_length_variation=statistics.pstdev(lengths) if len(lengths) > 1 else 0.0,
        breath_groups=groups_total,
        mean_words_per_breath_group=(len(all_words) / groups_total) if groups_total else 0.0,
        passive_sentences=sum(1 for s in per_sentence if s.passive),
        longest_nominal_run=max((s.nominal_run for s in per_sentence), default=0),
        filler_phrases=[phrase for phrase in _FILLER if phrase in lowered],
    )

    flags: list[str] = []
    if analysis.longest_sentence_words > 30:
        flags.append(
            f"a sentence runs {analysis.longest_sentence_words} words; the approved rules "
            f"ask for one principal thought per breath group"
        )
    if analysis.mean_words_per_breath_group > 14:
        flags.append(
            f"{analysis.mean_words_per_breath_group:.0f} words per breath group on average; "
            f"the reader has nowhere to breathe without breaking a thought"
        )
    if len(lengths) > 2 and analysis.sentence_length_variation < 3:
        flags.append(
            "sentence lengths are nearly uniform; the rules ask for varied but "
            "controlled sentence length, and uniformity reads as mechanical"
        )
    if analysis.longest_nominal_run >= 3:
        flags.append(
            f"{analysis.longest_nominal_run} nominalizations in a row (noun stacking); "
            f"the rules prefer direct verbs"
        )
    if analysis.passive_sentences and analysis.passive_sentences >= max(1, len(sentences) // 2):
        flags.append(
            f"{analysis.passive_sentences} of {len(sentences)} sentences are passive; "
            f"agency is hard to hear aloud"
        )
    if analysis.filler_phrases:
        flags.append(f"written-paper filler present: {', '.join(analysis.filler_phrases)}")
    analysis.flags = flags

    analysis.per_sentence = per_sentence
    analysis.estimated_seconds = {
        register: [
            round(len(all_words) / high * 60, 1),
            round(len(all_words) / low * 60, 1),
        ]
        for register, (low, high) in PACE_RANGES.items()
    }
    return analysis


__all__ = ["FlowAnalysis", "SentenceMetrics", "analyze", "PACE_RANGES"]
