"""Column-layout detection for real-world proceedings templates.

A one-column paper can contain a two-column *table* -- the Springer LNCS
author-instructions PDF is one -- and that table must not make the whole
document look two-column. These tests pin the document-level decision.
"""

from __future__ import annotations

import pymupdf
import pytest

from app.parsing.errors import PdfParseError
from app.parsing.pdf_parser import parse_pdf

A4 = pymupdf.paper_rect("a4")


def _pdf_with_pages(build) -> bytes:
    doc = pymupdf.open()
    build(doc)
    data = doc.tobytes()
    doc.close()
    return data


def _single_column_page(page, top=60, bottom=780):
    """One full-width line of body text per row."""
    y = top
    while y < bottom:
        page.insert_text((60, y), "Body text spanning the full width of the measure.", fontsize=9, fontname="helv")
        y += 13


def _two_column_page(page, top=60, bottom=780):
    # The right column must start clear of the parser's midpoint tolerance
    # (A4 half-width is 297.5pt, tolerance 12pt), i.e. at x >= 310.
    for x in (60, 320):
        y = top
        while y < bottom:
            page.insert_text((x, y), "Body text in one column of the page.", fontsize=9, fontname="helv")
            y += 13


def _table_page(page):
    """A sparse page whose only two-column content is a small table."""
    for y in (60, 75):
        page.insert_text((60, y), "Button", fontsize=9, fontname="helv")
        page.insert_text((320, y), "Effect", fontsize=9, fontname="helv")


def test_fully_single_column_document():
    data = _pdf_with_pages(lambda d: [_single_column_page(d.new_page(width=A4.width, height=A4.height)) for _ in range(4)])
    assert parse_pdf(data).document.columns == 1


def test_fully_two_column_document():
    data = _pdf_with_pages(lambda d: [_two_column_page(d.new_page(width=A4.width, height=A4.height)) for _ in range(4)])
    assert parse_pdf(data).document.columns == 2


def test_single_column_paper_with_one_two_column_table_page():
    """The regression that matters: an embedded table must not flip the document.

    A real case is Springer's SPLNPROC Technical Instructions PDF, whose ninth
    page is a two-column button/effect table inside single-column prose.
    """
    def build(doc):
        for _ in range(8):
            _single_column_page(doc.new_page(width=A4.width, height=A4.height))
        _two_column_page(doc.new_page(width=A4.width, height=A4.height))

    assert parse_pdf(_pdf_with_pages(build)).document.columns == 1


def test_a_short_table_page_cannot_outvote_the_body():
    """A few table rows are noise even if they land on a sparse page."""

    def build(doc):
        for _ in range(6):
            _two_column_page(doc.new_page(width=A4.width, height=A4.height))
        # one sparse page whose only two-column content is a couple of rows
        page = doc.new_page(width=A4.width, height=A4.height)
        _table_page(page)
        _single_column_page(page, top=200, bottom=760)

    assert parse_pdf(_pdf_with_pages(build)).document.columns == 2


def test_a_blank_document_reports_no_text_rather_than_guessing():
    """A scanned PDF has no geometry to measure; say so instead of inventing it."""
    data = _pdf_with_pages(lambda d: d.new_page(width=A4.width, height=A4.height))
    with pytest.raises(PdfParseError, match="No extractable text"):
        parse_pdf(data)
