"""Check results, per-paper assessment and batch submission reports.

Status semantics matter for the reported score:

``passed``           the requirement was evaluated and the paper satisfies it
``failed``           evaluated and the paper violates it
``missing``          the paper omits something the template requires
``not_applicable``   the rule is switched off, or the fact could not be measured
                     for this input format (e.g. paragraph spacing in a PDF)

``not_applicable`` is excluded from the score denominator. Treating an
unmeasurable property as a failure — the earlier behaviour — systematically
penalises formats the parser cannot measure rather than papers that are wrong.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.facts import PaperFacts
from app.models.rules import PublisherDetails, Severity


class PaperMetadata(BaseModel):
    """Structured paper metadata for display in reports."""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    author_block: str = ""
    emails: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    orcids: list[str] = Field(default_factory=list)

CheckStatus = Literal["passed", "failed", "missing", "not_applicable"]
Category = Literal[
    "document",  # legacy template-vs-paper checks
    "file", "page", "layout", "typography", "paragraph", "structure", "anonymisation", "policy",
]
Verdict = Literal["accepted", "rejected", "needs_review"]

CATEGORIES = (
    "document", "file", "page", "layout", "typography", "paragraph", "structure",
    "anonymisation", "policy",
)

_SCORED = ("passed", "failed", "missing")


class CheckResult(BaseModel):
    id: str = Field("", description="Stable rule identifier; empty for legacy template checks.")
    name: str
    category: Category
    status: CheckStatus
    severity: Severity = Severity.WARNING
    expected: Any = None
    actual: Any = None
    rule: str = ""
    advice: Optional[str] = None
    evidence: Optional[str] = None
    confidence: str = "high"


class ComplianceReport(BaseModel):
    score: int
    passed: int
    failed: int
    missing: int
    results: list[CheckResult] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    filename: str = ""
    metadata: Optional[PaperMetadata] = None

    @staticmethod
    def build(results: list[CheckResult], meta: dict[str, Any] | None = None) -> "ComplianceReport":
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        missing = sum(1 for r in results if r.status == "missing")
        total = passed + failed + missing
        score = round(100 * passed / total) if total else 0
        return ComplianceReport(
            score=score,
            passed=passed,
            failed=failed,
            missing=missing,
            results=results,
            meta=meta or {},
        )


class PaperAssessment(BaseModel):
    """The verdict for one paper against one publisher template."""

    filename: str
    format: str
    verdict: Verdict = "needs_review"
    score: int = 0
    passed: int = 0
    failed: int = 0
    missing: int = 0
    not_applicable: int = 0
    blocking_reasons: list[CheckResult] = Field(default_factory=list)
    warnings: list[CheckResult] = Field(default_factory=list)
    results: list[CheckResult] = Field(default_factory=list)
    facts: Optional[PaperFacts] = None
    metadata: Optional[PaperMetadata] = None
    summary_line: str = ""
    action_required: Optional[str] = None


class SubmissionReport(BaseModel):
    """A batch of papers checked against one template."""

    template_id: str = ""
    template_name: str = ""
    publisher: PublisherDetails = Field(default_factory=PublisherDetails)
    source: str = "upload"
    papers: list[PaperAssessment] = Field(default_factory=list)
    accepted: int = 0
    rejected: int = 0
    needs_review: int = 0
    generated_at: str = ""

    @staticmethod
    def tally(papers: list[PaperAssessment]) -> tuple[int, int, int]:
        accepted = sum(1 for p in papers if p.verdict == "accepted")
        rejected = sum(1 for p in papers if p.verdict == "rejected")
        review = sum(1 for p in papers if p.verdict == "needs_review")
        return accepted, rejected, review


__all__ = [
    "CATEGORIES",
    "Category",
    "CheckResult",
    "CheckStatus",
    "ComplianceReport",
    "PaperAssessment",
    "PaperMetadata",
    "SubmissionReport",
    "Verdict",
]
