"""Preservation checking for rewrites.

Prompt C §10: "preservation violations return the original text with a warning
rather than an altered result." This module is what makes that enforceable — it
compares a candidate rewrite against the source and reports what the rewrite
changed that it was not allowed to change.

Scope, deliberately narrow. This is a *detector*, not a rewriter, and it makes no
claim to understand meaning. It checks the categories Prompt C §9 names, each of
which is checkable from the surface text:

  numbers       every numeric literal in the source survives, and none appear
                that were not in the source (a hallucinated figure is the most
                damaging failure mode in technical narration)
  dates         same rule, for the common written date forms
  protected     caller-supplied exact terms, plus anything the source marks with
                backticks — `OAuth scopes`, `Admin console`, product names
  obligation    a requirement stays a requirement. "must" may not become
                "should", "may", or an optional framing
  certainty     a hedge stays a hedge. "may reduce" may not become "reduces",
                and "has not been proven" may not turn into a guarantee
  names         capitalized proper nouns present in the source are still present

What it deliberately does NOT do: judge whether the rewrite is *good*. Style is
the calling model's job; this module only draws the line it may not cross.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 1,200 · 3.5 · 80% · $40 · 250 — but not the "2" inside "OAuth2" or a version
# string, which are handled as protected terms instead.
_NUMBER = re.compile(r"(?<![\w.])[$€£]?\d[\d,]*(?:\.\d+)?%?(?![\w])")

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_DATE = re.compile(
    rf"\b(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|"
    rf"(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s*\d{{0,4}}|"
    rf"\d{{1,2}}\s+(?:{_MONTHS})\.?\s*\d{{0,4}})\b",
    re.I,
)

_BACKTICKED = re.compile(r"`([^`\n]{1,80})`")

# Mid-sentence capitalized words: sentence-initial capitals are excluded because
# they carry no evidence of being a proper noun.
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n)\s*")
_CAPITALIZED = re.compile(r"\b[A-Z][a-zA-Z]{1,}(?:[A-Z][a-zA-Z]*)?\b")

OBLIGATION_STRONG = ("must", "shall", "required", "requires", "mandatory", "have to", "has to")
OBLIGATION_WEAK = ("should", "may", "might", "can", "could", "optional", "consider", "recommended")

CERTAINTY_HEDGES = (
    "may", "might", "could", "can", "possibly", "potentially", "not been proven",
    "unproven", "appears", "suggests", "likely", "unlikely", "in some cases",
)
CERTAINTY_ABSOLUTES = (
    "will always", "guarantees", "guaranteed", "prevents", "ensures", "eliminates",
    "proven to", "never fails", "always works", "certainly",
)


@dataclass
class Violation:
    category: str
    detail: str
    expected: str = ""
    found: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "detail": self.detail,
            "expected": self.expected,
            "found": self.found,
        }


@dataclass
class PreservationReport:
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    checked: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "checked": self.checked,
            "summary": (
                "all protected content preserved"
                if self.passed
                else f"{len(self.violations)} preservation violation(s)"
            ),
        }


def _normalize_number(token: str) -> str:
    return token.replace(",", "").replace("$", "").replace("€", "").replace("£", "").lower()


def numbers(text: str) -> list[str]:
    """Numeric literals, with dates removed first so 2026-07-31 is not three numbers."""
    without_dates = _DATE.sub(" ", text)
    return [_normalize_number(m.group(0)) for m in _NUMBER.finditer(without_dates)]


def dates(text: str) -> list[str]:
    return [m.group(0).strip().lower() for m in _DATE.finditer(text)]


def backticked_terms(text: str) -> list[str]:
    return [m.group(1).strip() for m in _BACKTICKED.finditer(text)]


def proper_names(text: str) -> list[str]:
    """Capitalized tokens that are not sentence-initial and not common openers."""
    starts = {m.end() for m in _SENTENCE_START.finditer(text)}
    found: list[str] = []
    for match in _CAPITALIZED.finditer(text):
        if match.start() in starts:
            continue
        found.append(match.group(0))
    return found


def _present(term: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I) is not None


def _any_present(terms: tuple[str, ...], text: str) -> list[str]:
    return [t for t in terms if _present(t, text)]


def check(
    original: str,
    rewrite: str,
    protected_terms: list[str] | None = None,
) -> PreservationReport:
    """Compare a candidate rewrite against its source. Never modifies either."""
    violations: list[Violation] = []
    protected = list(protected_terms or []) + backticked_terms(original)

    # ── numbers ───────────────────────────────────────────────────────────────
    source_numbers = numbers(original)
    rewrite_numbers = numbers(rewrite)
    for value in dict.fromkeys(source_numbers):
        if source_numbers.count(value) > rewrite_numbers.count(value):
            violations.append(Violation("number", f"{value!r} is missing from the rewrite", value))
    for value in dict.fromkeys(rewrite_numbers):
        if rewrite_numbers.count(value) > source_numbers.count(value):
            violations.append(
                Violation("number", f"{value!r} does not appear in the source", found=value)
            )

    # ── dates ─────────────────────────────────────────────────────────────────
    source_dates, rewrite_dates = dates(original), dates(rewrite)
    for value in source_dates:
        if value not in rewrite_dates:
            violations.append(Violation("date", f"{value!r} is missing from the rewrite", value))
    for value in rewrite_dates:
        if value not in source_dates:
            violations.append(
                Violation("date", f"{value!r} does not appear in the source", found=value)
            )

    # ── protected terms ───────────────────────────────────────────────────────
    for term in dict.fromkeys(protected):
        if not _present(term, rewrite):
            violations.append(
                Violation("protected_term", f"{term!r} was not preserved verbatim", term)
            )

    # ── obligation ────────────────────────────────────────────────────────────
    source_strong = _any_present(OBLIGATION_STRONG, original)
    if source_strong and not _any_present(OBLIGATION_STRONG, rewrite):
        weakened = _any_present(OBLIGATION_WEAK, rewrite)
        violations.append(
            Violation(
                "obligation",
                "a requirement lost its obligation force",
                ", ".join(source_strong),
                ", ".join(weakened) or "no obligation marker",
            )
        )

    # ── certainty ─────────────────────────────────────────────────────────────
    source_hedges = _any_present(CERTAINTY_HEDGES, original)
    if source_hedges:
        if not _any_present(CERTAINTY_HEDGES, rewrite):
            violations.append(
                Violation(
                    "certainty",
                    "a hedged statement became unqualified",
                    ", ".join(source_hedges),
                    "no hedge",
                )
            )
        added = [a for a in _any_present(CERTAINTY_ABSOLUTES, rewrite)
                 if not _present(a, original)]
        if added:
            violations.append(
                Violation("certainty", "the rewrite raised certainty", found=", ".join(added))
            )

    # ── proper names ──────────────────────────────────────────────────────────
    for name in dict.fromkeys(proper_names(original)):
        if not _present(name, rewrite):
            violations.append(Violation("name", f"proper name {name!r} was dropped", name))

    return PreservationReport(
        passed=not violations,
        violations=violations,
        checked={
            "numbers": len(source_numbers),
            "dates": len(source_dates),
            "protected_terms": len(set(protected)),
            "proper_names": len(set(proper_names(original))),
            "obligation_markers": len(source_strong),
            "certainty_hedges": len(source_hedges),
        },
    )


__all__ = ["PreservationReport", "Violation", "check", "numbers", "dates", "proper_names"]
