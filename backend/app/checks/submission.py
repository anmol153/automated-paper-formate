"""Batch submission processing.

Takes many papers, checks each against one rule set, and returns one
``SubmissionReport``. The batch is deliberately fault-tolerant: a file that
cannot be parsed, or that is not a paper at all, becomes a rejected entry with
an explanatory reason instead of aborting the whole submission.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from app.checks.engine import assess
from app.models.facts import PaperFacts
from app.models.report import CheckResult, PaperAssessment, SubmissionReport
from app.models.rules import RuleSet, Severity
from app.parsing.errors import ParseError
from app.parsing.fact_extractor import build_facts
from app.parsing.pipeline import SUPPORTED_FORMATS, normalize_document, sniff_format

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 200


def _rejected_file_assessment(
    filename: str,
    detail: str,
    severity: Severity = Severity.BLOCKING,
) -> PaperAssessment:
    result = CheckResult(
        id="file.ingest",
        name="File could not be processed",
        category="file",
        status="failed",
        severity=severity,
        expected="A readable PDF, LaTeX or Word file",
        actual=detail,
        rule="file.ingest",
        advice=detail,
        evidence=f"filename={filename}",
    )
    return PaperAssessment(
        filename=filename,
        format="unknown",
        verdict="rejected",
        score=0,
        failed=1,
        blocking_reasons=[result],
        results=[result],
        summary_line=f"Rejected — {detail}",
        action_required=detail,
    )


def assess_paper(
    rules: RuleSet,
    data: bytes,
    filename: str,
    author_supplied: Optional[dict[str, Any]] = None,
) -> PaperAssessment:
    """Parse and assess one paper, converting failures into a clear rejection."""
    if not data:
        return _rejected_file_assessment(filename, "The uploaded file is empty.")

    fmt = sniff_format(data, filename)
    if fmt == "unknown":
        return _rejected_file_assessment(
            filename,
            f"'{filename}' is not a recognised format. Supported formats: "
            f"{', '.join('.' + f for f in SUPPORTED_FORMATS)}.",
        )

    try:
        doc = normalize_document(data, filename)
    except ParseError as exc:
        return _rejected_file_assessment(filename, str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected parse failure for %s", filename)
        return _rejected_file_assessment(
            filename, f"The file could not be parsed ({type(exc).__name__})."
        )

    facts = build_facts(data, filename, doc, fmt, author_supplied=author_supplied)
    return assess(rules, facts)


def assess_batch(
    rules: RuleSet,
    papers: Sequence[tuple[str, bytes]],
    source: str = "upload",
    author_supplied_by_file: Optional[dict[str, dict[str, Any]]] = None,
) -> SubmissionReport:
    """Assess every (filename, bytes) pair and summarise the verdicts."""
    if len(papers) > MAX_BATCH_SIZE:
        papers = papers[:MAX_BATCH_SIZE]

    supplied = author_supplied_by_file or {}
    assessments = [
        assess_paper(rules, data, name, supplied.get(name))
        for name, data in papers
    ]

    accepted, rejected, review = SubmissionReport.tally(assessments)
    return SubmissionReport(
        template_id=rules.template_id,
        template_name=rules.name,
        publisher=rules.publisher,
        source=source,
        papers=assessments,
        accepted=accepted,
        rejected=rejected,
        needs_review=review,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


__all__ = ["assess_batch", "assess_paper", "MAX_BATCH_SIZE"]
