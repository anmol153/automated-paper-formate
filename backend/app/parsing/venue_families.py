"""Recognise well-known proceedings template families from their own layout.

Some venue requirements are *policy* rather than *geometry*: a page ceiling, an
abstract word budget, a keyword policy. None of that is recorded in a template
file -- the Springer LNCS author-instructions PDF is entirely about which ribbon
button to press and never mentions a page limit. Reading it as if it did would
mean inventing numbers, which the rest of this package deliberately refuses to
do.

What this module does instead is recognise a template family from measurable
signatures (page size, text-area dimensions, column count, body font, the
sections present) and then supply the family's *published* requirements as a
starting point for the manager to confirm.

Two rules keep this honest:

* measured geometry always wins -- the file is the authority for page size,
  margins, columns and typography, and the preset never overwrites it;
* a preset only fills fields that cannot be measured, and every preset carries
  the published source so a manager can check it against the current call for
  papers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.models.document import NormalizedDocument
from app.models.rules import RuleSet

_PT_PER_MM = 72 / 25.4


def _mm(points: float) -> float:
    return points / _PT_PER_MM


@dataclass(frozen=True)
class FamilyMatch:
    """A recognised template family and how closely the file matched it."""

    key: str
    label: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    preset: dict = field(default_factory=dict)
    source: str = ""


# --------------------------------------------------------------------------- #
# Springer LNCS / SPLNPROC
# --------------------------------------------------------------------------- #

# The LNCS text area is 122 x 193 mm on A4, giving 44 mm side margins and 52 mm
# top and bottom. These are the values in the official splnproc Word template.
LNCS_TEXT_WIDTH_MM = 122.0
LNCS_TEXT_HEIGHT_MM = 193.0
_LNCS_WIDTH_TOLERANCE_MM = 4.0
_LNCS_HEIGHT_TOLERANCE_MM = 6.0

#: Policy fields for Springer LNCS. Sourced from the Springer LNCS author
#: guidelines rather than from any template file -- confirm against the current
#: volume's call for papers before relying on the page ceiling.
LNCS_PRESET: dict = {
    "source": "Springer LNCS author guidelines (not derived from the uploaded file)",
    "policy": {
        "sections": {
            "abstract_required": True,
            "abstract_max_words": 250,
            "keywords_required": True,
            "min_reference_entries": None,
        },
        "pages": {
            "max_pages": 9,
            "count_references_toward_limit": True,
        },
        "anonymisation": {
            "required": False,
            "allow_author_block": True,
        },
    },
}

_LNCS_SIGNATURE_TEXT_HINTS = ("abstract", "keywords", "references")


def _looks_like_lncs(doc: NormalizedDocument) -> Optional[FamilyMatch]:
    info = doc.document
    evidence: list[str] = []
    score = 0.0
    total = 0.0

    def check(weight: float, ok: bool, note: str) -> None:
        nonlocal score, total
        total += weight
        if ok:
            score += weight
            evidence.append(note)

    check(0.30, info.page_size.label == "A4", "A4 page size")
    check(0.15, info.columns == 1, "single column")
    check(0.10, info.orientation == "portrait", "portrait")

    # The text area is the page minus the margins; LNCS is 122 x 193 mm.
    text_width_mm = _mm(info.page_size.width_pt - info.margins.left_pt - info.margins.right_pt)
    text_height_mm = _mm(info.page_size.height_pt - info.margins.top_pt - info.margins.bottom_pt)
    if abs(text_width_mm - LNCS_TEXT_WIDTH_MM) < _LNCS_WIDTH_TOLERANCE_MM:
        score += 0.20
        evidence.append(f"text area {text_width_mm:.0f} mm wide (LNCS is {LNCS_TEXT_WIDTH_MM:.0f})")
    if abs(text_height_mm - LNCS_TEXT_HEIGHT_MM) < _LNCS_HEIGHT_TOLERANCE_MM:
        score += 0.15
        evidence.append(f"text area {text_height_mm:.0f} mm tall (LNCS is {LNCS_TEXT_HEIGHT_MM:.0f})")
    total += 0.35

    has_abstract = doc.find("abstract") is not None
    has_keywords = any(b.name and b.name.casefold().startswith("keywords") for b in doc.sections)
    check(0.15, has_abstract, "abstract section present")
    check(0.10, has_keywords, "keywords section present")

    text = doc.full_text().casefold()
    check(0.10, any(h in text for h in _LNCS_SIGNATURE_TEXT_HINTS), "LNCS vocabulary present")

    confidence = score / total if total else 0.0
    if confidence < 0.75:
        return None
    return FamilyMatch(
        key="springer-lncs",
        label="Springer LNCS (visible authors)",
        confidence=round(confidence, 3),
        evidence=evidence,
        preset=LNCS_PRESET,
        source=LNCS_PRESET["source"],
    )


_FAMILY_DETECTORS = (_looks_like_lncs,)


def detect_family(doc: NormalizedDocument) -> Optional[FamilyMatch]:
    """Identify the template family, if the evidence is strong enough."""
    for detector in _FAMILY_DETECTORS:
        match = detector(doc)
        if match is not None:
            return match
    return None


def apply_preset(rules: RuleSet, match: FamilyMatch) -> RuleSet:
    """Fill in the policy fields a preset knows about.

    Only fields that cannot be measured from a document are touched. Geometry,
    columns, typography and margins are left exactly as inferred from the file.
    """
    policy = match.preset.get("policy", {})

    sections = policy.get("sections", {})
    if sections.get("abstract_required") and not rules.sections.abstract_required:
        rules.sections.abstract_required = True
    if sections.get("abstract_max_words") and not rules.sections.abstract_max_words:
        rules.sections.abstract_max_words = sections["abstract_max_words"]
    if sections.get("keywords_required") and not rules.sections.keywords_required:
        rules.sections.keywords_required = True
    if sections.get("min_reference_entries") and not rules.sections.min_reference_entries:
        rules.sections.min_reference_entries = sections["min_reference_entries"]

    pages = policy.get("pages", {})
    if pages.get("max_pages") and not rules.pages.max_pages:
        rules.pages.max_pages = pages["max_pages"]
    if "count_references_toward_limit" in pages:
        rules.pages.count_references_toward_limit = pages["count_references_toward_limit"]

    anonymisation = policy.get("anonymisation", {})
    if "required" in anonymisation and not rules.anonymisation.required:
        rules.anonymisation.required = anonymisation["required"]
    if "allow_author_block" in anonymisation:
        rules.anonymisation.allow_author_block = anonymisation["allow_author_block"]

    return rules


__all__ = [
    "FamilyMatch",
    "LNCS_PRESET",
    "apply_preset",
    "detect_family",
]
