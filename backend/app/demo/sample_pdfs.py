"""Builds sample template/paper PDFs used by demo mode and tests."""

from __future__ import annotations

from functools import lru_cache

import pymupdf as fitz

TEMPLATE_WIDTH, TEMPLATE_HEIGHT = 595.28, 841.89
PAPER_WIDTH, PAPER_HEIGHT = 612.0, 792.0

_SENTENCE = (
    "The proposed approach evaluates formatting compliance by parsing the document model "
    "directly and comparing extracted rules against observed typography across all sections."
)


def _wrap(text: str, fontname: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            trial = f"{current} {word}".strip()
            if fitz.get_text_length(trial, fontname=fontname, fontsize=size) <= width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


class PdfBuilder:
    def __init__(self, width: float, height: float, margin_l: float, margin_r: float):
        self.doc = fitz.open()
        self.page = self.doc.new_page(width=width, height=height)
        self.margin_l = margin_l
        self.content_w = width - margin_l - margin_r
        self.y = 64.0

    def text(self, content, fontname, size, *, align="left", indent=0.0, leading=None,
             space_below=0.0, width=None, x=None):
        leading = leading if leading is not None else size * 1.25
        width = width if width is not None else self.content_w
        x = x if x is not None else self.margin_l
        for raw_line in _wrap(content, fontname, size, width - indent):
            text_width = fitz.get_text_length(raw_line, fontname=fontname, fontsize=size)
            if align == "center":
                offset = (width - text_width) / 2
            elif align == "right":
                offset = width - text_width
            else:
                offset = indent
            self.page.insert_text(
                (x + offset, self.y + size * 0.85),
                raw_line,
                fontname=fontname,
                fontsize=size,
            )
            self.y += leading
        self.y += space_below

    def columns(self, left_text, right_text, fontname, size, *, gap=24.0):
        column_w = (self.content_w - gap) / 2
        start_y = self.y
        deepest = self.y
        for start_x, body in ((self.margin_l, left_text), (self.margin_l + column_w + gap, right_text)):
            y = start_y
            for line in _wrap(body, fontname, size, column_w):
                self.page.insert_text((start_x, y + size * 0.85), line,
                                      fontname=fontname, fontsize=size)
                y += size * 1.25
            deepest = max(deepest, y)
        self.y = deepest + 8.0


def build_template_pdf() -> bytes:
    b = PdfBuilder(TEMPLATE_WIDTH, TEMPLATE_HEIGHT, margin_l=54, margin_r=54)

    b.text("Sample Journal Paper Template", "Times-Bold", 16, align="center", space_below=6)
    b.text("Jane Doe, John Smith\nExample University, Example City", "Times-Roman", 11,
           align="center", space_below=18)
    b.text("Abstract", "Times-Bold", 10, space_below=2)
    b.text(_SENTENCE + " " + _SENTENCE, "Times-Roman", 10, space_below=18)
    b.text("Keywords—format checking, templates, compliance", "Times-Roman", 10, space_below=24)

    column_body = (_SENTENCE + " ")[:230].strip()
    for section in ("INTRODUCTION", "METHODOLOGY", "RESULTS", "CONCLUSION", "REFERENCES"):
        b.text(section, "Times-Bold", 10, space_below=8)
        if section == "REFERENCES":
            b.text("[1] A. Author, B. Author, Some Paper, Venue 2024.\n"
                   "[2] C. Author, Another Paper, Venue 2025.", "Times-Roman", 9, space_below=6)
        else:
            b.columns(column_body, column_body, "Times-Roman", 10)
    return b.doc.tobytes()


def build_paper_pdf() -> bytes:
    b = PdfBuilder(PAPER_WIDTH, PAPER_HEIGHT, margin_l=72, margin_r=72)

    b.text("Deep Learning for Format Compliance Checking", "Helvetica-Bold", 14,
           align="center", space_below=6)
    b.text("Alice Lee, Bob Chen\nState University, Springfield", "Helvetica", 11,
           align="center", space_below=16)
    b.text("ABSTRACT", "Helvetica-Bold", 12, space_below=3)
    b.text(_SENTENCE + " " + _SENTENCE, "Helvetica", 11, space_below=10)
    b.text("1. Introduction", "Helvetica-Bold", 11, space_below=3)
    b.text(_SENTENCE + " " + _SENTENCE, "Helvetica", 11, space_below=8)
    b.text("Prior systems rely on heuristics over rendered pages instead of structured models.",
           "Helvetica", 11, space_below=12)
    b.text("Results", "Helvetica-Bold", 11, space_below=3)
    b.text(_SENTENCE + " " + _SENTENCE, "Helvetica", 11, space_below=12)
    b.text("Conclusion", "Helvetica-Bold", 11, space_below=3)
    b.text("Automated compliance checking saves reviewers time and helps authors fix issues early.",
           "Helvetica", 11, space_below=12)
    b.text("References", "Helvetica-Bold", 11, space_below=3)
    b.text("[1] X. Yang, Format Matters, Journal of Documents, 2024.", "Helvetica", 10)
    return b.doc.tobytes()


@lru_cache(maxsize=1)
def demo_documents() -> tuple[bytes, bytes]:
    return build_template_pdf(), build_paper_pdf()
