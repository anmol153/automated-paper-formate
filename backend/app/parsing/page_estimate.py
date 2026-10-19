"""Page-count estimation for source formats (LaTeX, DOCX).

A rendered page count is only available for PDFs, where the renderer has already
paginated the document. Source formats must be estimated from a text-layout
model, so these numbers are approximate and are always reported with
``page_count_exact=False``.

The model is deliberately simple and explicit about its assumptions:

* average glyph advance is a fixed fraction of the point size (proportional faces)
* baseline skip is ``font_size * BASELINE_FACTOR * line_spacing``
* a block occupies ``ceil(chars / chars_per_line)`` lines, at least one
* the first page is not discounted for a title block, since vertical whitespace
  that a real renderer would place above the title is not modelled
"""

from __future__ import annotations

import math

from app.models.document import Margins, NormalizedDocument, PageSize, TextFormat

BASELINE_FACTOR = 1.2
PROPORTIONAL_ADVANCE = 0.5
MONOSPACE_ADVANCE = 0.6

_MONOSPACE_HINTS = ("courier", "consolas", "menlo", "monaco", "mono")


def _advance_ratio(font_family: str | None) -> float:
    if font_family and any(hint in font_family.casefold() for hint in _MONOSPACE_HINTS):
        return MONOSPACE_ADVANCE
    return PROPORTIONAL_ADVANCE


def _line_height_pt(font_size_pt: float, line_spacing: float | None) -> float:
    spacing = line_spacing if line_spacing and line_spacing > 0 else 1.0
    return max(font_size_pt, 1.0) * BASELINE_FACTOR * spacing


def _block_lines(text: str, usable_width_pt: float, font: TextFormat, default_size_pt: float) -> int:
    if not text.strip():
        return 1
    size = font.font_size_pt or default_size_pt
    per_line = usable_width_pt / (_advance_ratio(font.font_family) * max(size, 1.0))
    return max(1, math.ceil(len(text) / max(per_line, 8.0)))


def estimate_pages(
    doc: NormalizedDocument,
    font_size_pt: float = 10.0,
    line_spacing: float | None = None,
) -> int:
    """Estimate the rendered page count of a source-format document."""
    page: PageSize = doc.document.page_size
    margins: Margins = doc.document.margins

    usable_width = page.width_pt - margins.left_pt - margins.right_pt
    usable_height = page.height_pt - margins.top_pt - margins.bottom_pt
    if usable_width <= 0 or usable_height <= 0:
        return 1

    body_sizes = [
        b.format.font_size_pt
        for b in doc.sections
        if b.type == "body" and b.format.font_size_pt
    ]
    effective_size = _dominant(body_sizes) or font_size_pt
    effective_spacing = _dominant(
        [b.format.line_spacing for b in doc.sections if b.format.line_spacing]
    ) or line_spacing

    line_height = _line_height_pt(effective_size, effective_spacing)
    lines_per_page = max(1.0, usable_height / line_height)

    total_lines = 0
    for block in doc.sections:
        total_lines += _block_lines(block.text, usable_width, block.format, effective_size)

    return max(1, math.ceil(total_lines / lines_per_page))


def _dominant(values: list[float]) -> float | None:
    if not values:
        return None
    counts: dict[float, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


__all__ = ["estimate_pages", "BASELINE_FACTOR"]
