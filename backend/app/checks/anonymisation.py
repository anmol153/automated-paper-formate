"""Anonymisation checks for double-blind submission.

Each function turns one detection into a ``CheckResult`` with the evidence that
produced it, so an author can see *what* leaked, not just that something did.

The distinction that matters: a finding is only blocking when the rule set says
identity must be hidden. A conference that accepts non-anonymous submissions
should not be rejected by this module.
"""

from __future__ import annotations

import re

from app.models.facts import PaperFacts
from app.models.report import CheckResult
from app.models.rules import AnonymisationRule, Severity

_ACKNOWLEDGEMENT_ADVICE = (
    "Remove the acknowledgements section entirely for the blinded review copy. "
    "State that acknowledgements are omitted for anonymised review."
)
_FUNDING_ADVICE = (
    "Remove funding and grant-number statements. Replace with: "
    "'This work received no specific grant from any funding agency.'"
)
_METADATA_ADVICE = (
    "Strip identifying metadata before uploading. On macOS use File > Properties and clear "
    "Author/Title; on Windows use File > Info > Properties > Advanced Properties > Summary, "
    "then re-export the PDF. Alternatively export with 'Document Properties' disabled."
)
_AUTHOR_ADVICE = (
    "Remove the author names, affiliations and contact details from the manuscript, and replace "
    "them with the anonymous placeholder required by this template."
)


def _result(
    rule_id: str,
    name: str,
    ok: bool,
    severity: Severity,
    expected: str,
    actual: str,
    advice: str,
    evidence: str | None = None,
) -> CheckResult:
    return CheckResult(
        id=rule_id,
        name=name,
        category="anonymisation",
        status="passed" if ok else "failed",
        severity=severity,
        expected=expected,
        actual=actual,
        rule=rule_id,
        advice=None if ok else advice,
        evidence=evidence,
    )


def _na(rule_id: str, name: str, note: str) -> CheckResult:
    return CheckResult(
        id=rule_id,
        name=name,
        category="anonymisation",
        status="not_applicable",
        severity=Severity.BLOCKING,
        expected="n/a",
        actual="n/a",
        rule=rule_id,
        evidence=note,
    )


def _hits(values: list[str], limit: int = 3) -> str:
    shown = ", ".join(values[:limit])
    if len(values) > limit:
        shown += f" (+{len(values) - limit} more)"
    return shown


def check_anonymisation(rules: AnonymisationRule, facts: PaperFacts) -> list[CheckResult]:
    results: list[CheckResult] = []
    identity = facts.identity

    if not rules.required:
        return [
            CheckResult(
                id="anonymisation.enabled",
                name="Anonymised submission",
                category="anonymisation",
                status="not_applicable",
                severity=Severity.BLOCKING,
                expected="n/a",
                actual="n/a",
                rule="anonymisation.enabled",
                evidence="This template does not require anonymised submissions.",
            )
        ]

    if identity.author_block_present:
        _block_actual = "Author block present"
    elif identity.author_block_placeholder_only:
        _block_actual = "No author block (anonymous placeholder only)"
    else:
        _block_actual = "No author block"

    results.append(
        _result(
            "anonymisation.author_block",
            "Author names absent",
            not identity.author_block_present or rules.allow_author_block,
            Severity.BLOCKING,
            "No author block",
            _block_actual,
            _AUTHOR_ADVICE,
            evidence=identity.author_block_text or None,
        )
    )

    if rules.detect_emails:
        results.append(
            _result(
                "anonymisation.emails",
                "No email addresses",
                not identity.detected_emails,
                Severity.BLOCKING,
                "No email addresses",
                _hits(identity.detected_emails) or "None found",
                "Remove all email addresses, including those in footnotes and acknowledgements.",
                evidence="; ".join(identity.detected_emails[:5]) or None,
            )
        )

    if rules.detect_affiliations:
        results.append(
            _result(
                "anonymisation.affiliations",
                "No institutional affiliations",
                not identity.detected_affiliations,
                Severity.BLOCKING,
                "No affiliations",
                _hits(identity.detected_affiliations) or "None found",
                "Remove institution names, departments, laboratories and company names.",
                evidence="; ".join(a.strip()[:120] for a in identity.detected_affiliations[:3]) or None,
            )
        )

    if rules.detect_acknowledgements:
        results.append(
            _result(
                "anonymisation.acknowledgements",
                "No acknowledgements section",
                not identity.acknowledgement_present,
                Severity.BLOCKING,
                "No acknowledgements",
                "Acknowledgements found" if identity.acknowledgement_present else "None found",
                _ACKNOWLEDGEMENT_ADVICE,
                evidence=identity.acknowledgement_text or None,
            )
        )

    if rules.detect_funding_statements:
        results.append(
            _result(
                "anonymisation.funding",
                "No funding statements",
                not identity.funding_present,
                Severity.BLOCKING,
                "No funding information",
                "Funding statement found" if identity.funding_present else "None found",
                _FUNDING_ADVICE,
                evidence=identity.funding_text or None,
            )
        )

    if rules.detect_orcid:
        results.append(
            _result(
                "anonymisation.orcid",
                "No ORCID identifiers",
                not identity.detected_orcids,
                Severity.WARNING,
                "No ORCID iDs",
                _hits(identity.detected_orcids) or "None found",
                "Remove ORCID iDs, which resolve directly to an author identity.",
                evidence="; ".join(identity.detected_orcids[:5]) or None,
            )
        )

    if rules.detect_self_citation:
        count = identity.self_citation_count or 0
        ok = count == 0
        results.append(
            _result(
                "anonymisation.self_citation",
                "No identifying self-citations",
                ok,
                Severity.WARNING,
                "No first-person self-reference",
                f"{count} first-person self-reference(s)",
                "Rewrite self-citations in the third person, e.g. 'Smith et al. [12] proposed' "
                "instead of 'we previously proposed'.",
                evidence=None if ok else f"{count} occurrence(s) of phrases such as 'our previous work'",
            )
        )

    for field in rules.forbidden_metadata_fields:
        value = identity.metadata_leaks.get(field)
        if not value:
            continue
        if field == "producer":
            results.append(
                _result(
                    "anonymisation.metadata.producer",
                    f"Metadata scrubbed: {field}",
                    False,
                    Severity.ADVISORY,
                    "Empty or generic",
                    value[:120],
                    _METADATA_ADVICE,
                    evidence=f"{field} = {value[:120]}",
                )
            )
        else:
            results.append(
                _result(
                    f"anonymisation.metadata.{field}",
                    f"Metadata scrubbed: {field}",
                    False,
                    Severity.BLOCKING,
                    "Empty or generic",
                    value[:120],
                    _METADATA_ADVICE,
                    evidence=f"{field} = {value[:120]}",
                )
            )

    if rules.extra_forbidden_terms:
        full_text = _haystack(facts)
        found = [t for t in rules.extra_forbidden_terms if t and t.casefold() in full_text.casefold()]
        results.append(
            _result(
                "anonymisation.forbidden_terms",
                "No conference-specific identifying terms",
                not found,
                Severity.BLOCKING,
                "None of the configured terms present",
                _hits(found) or "None found",
                "Remove the identifying terms configured by the conference manager "
                "(for example funder names or project identifiers).",
                evidence="; ".join(found[:5]) or None,
            )
        )

    if rules.allow_anonymous_placeholder and not identity.anonymous_placeholder_present:
        results.append(
            CheckResult(
                id="anonymisation.placeholder",
                name="Anonymous placeholder present",
                category="anonymisation",
                status="passed",
                severity=Severity.ADVISORY,
                expected="A placeholder such as 'Anonymous Authors'",
                actual=(
                    "Placeholder present" if identity.anonymous_placeholder_present else "No placeholder"
                ),
                rule="anonymisation.placeholder",
                confidence="medium",
            )
        )

    return results


def _haystack(facts: PaperFacts) -> str:
    parts: list[str] = []
    if facts.structure.author_block_text:
        parts.append(facts.structure.author_block_text)
    if facts.identity.acknowledgement_text:
        parts.append(facts.identity.acknowledgement_text)
    if facts.identity.funding_text:
        parts.append(facts.identity.funding_text)
    if facts.structure.title_text:
        parts.append(facts.structure.title_text)
    return " ".join(parts)


def score_anonymisation(facts: PaperFacts) -> int:
    """0-100 heuristic used only for display and triage, never for rejection."""
    identity = facts.identity
    leaks = 0
    leaks += 3 if identity.author_block_present else 0
    leaks += 3 if identity.detected_emails else 0
    leaks += 2 if identity.detected_affiliations else 0
    leaks += 2 if identity.acknowledgement_present else 0
    leaks += 1 if identity.funding_present else 0
    leaks += 1 if identity.detected_orcids else 0
    leaks += 1 if any(k in ("author", "creator") for k in identity.metadata_leaks) else 0
    return max(0, 100 - min(100, leaks * 10))


__all__ = ["check_anonymisation", "score_anonymisation"]
