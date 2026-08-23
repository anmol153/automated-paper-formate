from __future__ import annotations

from app.comparator.comparator import run_comparison
from app.models.document import NormalizedDocument
from app.models.report import ComplianceReport
from app.parsing.pdf_parser import PdfParseError, parse_pdf
from app.parsing.template_analyzer import analyze_template


def normalize_pdf(data: bytes) -> NormalizedDocument:
    return parse_pdf(data)


def compare_documents(template_data: bytes, paper_data: bytes) -> ComplianceReport:
    template = normalize_pdf(template_data)
    paper = normalize_pdf(paper_data)
    rules = analyze_template(template)
    return run_comparison(rules, paper)


__all__ = ["normalize_pdf", "compare_documents", "PdfParseError"]
