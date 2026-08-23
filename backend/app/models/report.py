from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

CheckStatus = Literal["passed", "failed", "missing"]
Category = Literal["document", "typography", "paragraph", "structure"]

CATEGORIES = ("document", "typography", "paragraph", "structure")


class CheckResult(BaseModel):
    name: str
    category: Category
    status: CheckStatus
    expected: Any = None
    actual: Any = None
    section: Optional[str] = None
    detail: Optional[str] = None


class ComplianceReport(BaseModel):
    score: int
    passed: int
    failed: int
    missing: int
    results: list[CheckResult] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

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
