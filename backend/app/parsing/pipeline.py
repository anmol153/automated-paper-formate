from __future__ import annotations

import re

from app.comparator.comparator import run_comparison
from app.models.document import NormalizedDocument
from app.models.report import ComplianceReport
from app.parsing.docx_parser import parse_docx
from app.parsing.errors import ParseError, PdfParseError
from app.parsing.fact_extractor import extract_paper_metadata
from app.parsing.latex_parser import parse_latex
from app.parsing.pdf_parser import parse_pdf
from app.parsing.template_analyzer import analyze_template


def normalize_pdf(data: bytes) -> NormalizedDocument:
    return parse_pdf(data)


_EXTENSION_FORMATS = {
    "tex": "latex",
    "latex": "latex",
    "ltx": "latex",
    "docx": "docx",
    "pdf": "pdf",
}

SUPPORTED_FORMATS = ("pdf", "latex", "docx")


def format_of(filename: str | None) -> str:
    """Map a filename to a format, or ``unknown`` when the extension is not one
    this system can parse. Never guesses: an unrecognised extension used to be
    treated as PDF, which let a .txt upload reach the PDF parser."""
    name = (filename or "").casefold()
    if "." not in name:
        return "unknown"
    return _EXTENSION_FORMATS.get(name.rsplit(".", 1)[-1], "unknown")


def sniff_format(data: bytes, filename: str | None = None) -> str:
    """Detect a format from content, using the filename only as a tie-breaker.

    Content wins so that a mislabelled upload is still parsed correctly, and a
    file that matches nothing is reported as ``unknown`` rather than being fed
    to the PDF parser and failing with a confusing message.
    """
    head = data[:2048] if data else b""
    if head[:5] == b"%PDF-":
        return "pdf"
    if head[:2] == b"PK":
        return "docx"

    extension_format = format_of(filename)
    if extension_format in ("latex",):
        return "latex"

    if data:
        try:
            sample = data.decode("utf-8", errors="replace")
        except Exception:
            sample = ""
        # Only structural markers count. Matching a bare \section or \title is not
        # enough: documentation *about* LaTeX contains those inside code samples,
        # which made a plain README.md get parsed as a LaTeX manuscript. A real
        # manuscript declares a document class or a document body.
        if re.search(r"\\documentclass\b|\\begin\s*\{document\}", sample):
            return "latex"
    if extension_format in ("docx", "pdf"):
        return extension_format
    return "unknown"


def normalize_document(data: bytes, filename: str | None = None) -> NormalizedDocument:
    fmt = sniff_format(data, filename)
    if fmt == "latex":
        return parse_latex(data)
    if fmt == "docx":
        return parse_docx(data)
    if fmt == "pdf":
        return parse_pdf(data)
    raise ParseError(
        f"Could not determine the format of '{filename or 'the uploaded file'}'. "
        f"Supported formats: PDF (.pdf), LaTeX (.tex, .latex, .ltx) and Word (.docx)."
    )


def compare_files(
    template_data: bytes,
    template_name: str | None,
    paper_data: bytes,
    paper_name: str | None,
) -> ComplianceReport:
    template = normalize_document(template_data, template_name)
    paper = normalize_document(paper_data, paper_name)
    rules = analyze_template(template)
    report = run_comparison(rules, paper)
    report.filename = paper_name or "paper"
    report.metadata = extract_paper_metadata(paper)
    return report


def compare_documents(template_data: bytes, paper_data: bytes) -> ComplianceReport:
    return compare_files(template_data, None, paper_data, None)


__all__ = [
    "SUPPORTED_FORMATS",
    "format_of",
    "sniff_format",
    "normalize_document",
    "normalize_pdf",
    "compare_documents",
    "compare_files",
    "ParseError",
    "PdfParseError",
]