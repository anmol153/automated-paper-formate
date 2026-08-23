from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.document import NormalizedDocument
from app.models.report import ComplianceReport
from app.models.rules import TemplateRules

from .document import compare_document
from .paragraph import compare_paragraph
from .structure import compare_structure
from .typography import compare_typography


def run_comparison(template_rules: TemplateRules, paper: NormalizedDocument) -> ComplianceReport:
    results: list = []
    results.extend(compare_document(template_rules.document, paper))
    results.extend(compare_typography(template_rules, paper))
    results.extend(compare_paragraph(template_rules, paper))
    results.extend(compare_structure(template_rules, paper))

    meta: dict[str, Any] = {
        "template_title": template_rules.source_title,
        "paper_title": paper.document.title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return ComplianceReport.build(results=results, meta=meta)
