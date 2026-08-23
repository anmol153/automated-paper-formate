"""PDF parser: converts PDF bytes into the shared NormalizedDocument model.

Formatting (fonts, sizes, bold/italic, geometry) comes from PyMuPDF's text
model; regex-based classification of *what a block is* lives in structure.py,
mirroring the Google Docs pipeline.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

import pymupdf as fitz

from app.models.document import (
    DocumentInfo,
    Margins,
    NormalizedDocument,
    PageSize,
    TextFormat,
)
from app.parsing.normalizer import page_size_label
from app.parsing.structure import RawBlock, classify_blocks, match_canonical_section

MAX_PAGES = 60

_BOLD_FLAG = 16
_ITALIC_FLAG = 2
_MID_TOLERANCE = 12.0
_MIN_COLUMN_LINES = 5


class PdfParseError(ValueError):
    pass


@dataclass
class SpanInfo:
    text: str
    size: float
    font: str
    bold: bool
    italic: bool


@dataclass
class LineInfo:
    x0: float
    y0: float
    x1: float
    y1: float
    baseline: float
    spans: list[SpanInfo] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)

    def dominant_size(self) -> float | None:
        weighted = [(s.size, len(s.text)) for s in self.spans if s.text.strip()]
        weighted = [(v, w) for v, w in weighted if v > 0]
        if not weighted:
            return None
        totals: dict[float, float] = {}
        for value, weight in weighted:
            totals[value] = totals.get(value, 0.0) + weight
        return max(totals.items(), key=lambda item: item[1])[0]


@dataclass
class BlockInfo:
    lines: list[LineInfo]
    page_index: int
    page_width: float
    page_height: float


_STYLE_SUFFIX_RE = re.compile(
    r"(bolditalic|italicbold|boldoblique|obliquebold|semibold|extralight|psmt|ps$|mt|std|pro|"
    r"bold|light|book|medium|regular|oblique|italic)$",
    re.IGNORECASE,
)


def clean_font_name(name: str | None) -> str | None:
    if not name:
        return None
    base = name.split("+")[-1]
    base = re.sub(r"[-_]+", "", base)
    while True:
        stripped = _STYLE_SUFFIX_RE.sub("", base)
        if stripped == base or not stripped:
            break
        base = stripped
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    if not spaced:
        return None
    return spaced.title() if spaced.isupper() or spaced.islower() else spaced


def _extract_spans(raw_span: dict) -> SpanInfo:
    font = raw_span.get("font", "") or ""
    flags = int(raw_span.get("flags") or 0)
    lowered = font.lower()
    size = float(raw_span.get("size") or 0.0)
    return SpanInfo(
        text=raw_span.get("text", "") or "",
        size=size,
        font=font,
        bold=bool(flags & _BOLD_FLAG) or "bold" in lowered,
        italic=bool(flags & _ITALIC_FLAG) or "italic" in lowered or "oblique" in lowered,
    )


def _extract_page_blocks(page: fitz.Page, page_index: int) -> list[BlockInfo]:
    data = page.get_text("dict")
    blocks: list[BlockInfo] = []
    for raw_block in data.get("blocks", []):
        if raw_block.get("type") != 0:
            continue
        lines: list[LineInfo] = []
        for raw_line in raw_block.get("lines", []):
            spans = [_extract_spans(s) for s in raw_line.get("spans", [])]
            spans = [s for s in spans if s.text.strip()]
            if not spans:
                continue
            bbox = raw_line.get("bbox")
            origin = raw_line["spans"][0].get("origin") if raw_line.get("spans") else None
            baseline = float(origin[1]) if origin else float(bbox[3])
            lines.append(
                LineInfo(
                    x0=float(bbox[0]),
                    y0=float(bbox[1]),
                    x1=float(bbox[2]),
                    y1=float(bbox[3]),
                    baseline=baseline,
                    spans=spans,
                )
            )
        if not lines:
            continue
        lines.sort(key=lambda line: line.y0)
        blocks.append(
            BlockInfo(
                lines=lines,
                page_index=page_index,
                page_width=float(page.rect.width),
                page_height=float(page.rect.height),
            )
        )
    return blocks


@dataclass
class Layout:
    columns: int = 1
    regions_by_page: dict[int, list[tuple[float, float]]] = field(default_factory=dict)
    band_top_by_page: dict[int, float] = field(default_factory=dict)
    margins: Margins = field(
        default_factory=lambda: Margins(top_pt=0, bottom_pt=0, left_pt=0, right_pt=0)
    )


def _page_groups(blocks: list[BlockInfo]) -> dict[int, list[BlockInfo]]:
    grouped: dict[int, list[BlockInfo]] = {}
    for block in blocks:
        grouped.setdefault(block.page_index, []).append(block)
    return grouped


def _analyze_layout(blocks: list[BlockInfo]) -> Layout:
    layout = Layout()
    pages = _page_groups(blocks)

    lefts: list[float] = []
    rights: list[float] = []
    tops: list[float] = []
    bottoms: list[float] = []

    for page_index, page_blocks in pages.items():
        lines = [line for block in page_blocks for line in block.lines]
        if not lines:
            continue
        width = page_blocks[0].page_width
        height = page_blocks[0].page_height
        mid = width / 2.0

        left_lines = [line for line in lines if line.x1 <= mid - _MID_TOLERANCE]
        right_lines = [line for line in lines if line.x0 >= mid + _MID_TOLERANCE]
        crossing = [line for line in lines if line.x0 < mid and line.x1 > mid]

        two_column = (
            len(left_lines) >= _MIN_COLUMN_LINES
            and len(right_lines) >= _MIN_COLUMN_LINES
            and len(crossing) <= 0.25 * (len(left_lines) + len(right_lines) + len(crossing))
        )

        if two_column:
            layout.columns = 2
            layout.regions_by_page[page_index] = [
                (min(line.x0 for line in left_lines), max(line.x1 for line in left_lines)),
                (min(line.x0 for line in right_lines), max(line.x1 for line in right_lines)),
            ]
            layout.band_top_by_page[page_index] = min(
                min(line.y0 for line in left_lines), min(line.y0 for line in right_lines)
            )
        else:
            layout.regions_by_page[page_index] = [
                (min(line.x0 for line in lines), max(line.x1 for line in lines))
            ]

        lefts.append(min(line.x0 for line in lines))
        rights.append(max(line.x1 for line in lines))
        tops.append(min(line.y0 for line in lines))
        bottoms.append(max(line.y1 for line in lines))

    def clamp(value: float) -> float:
        return round(max(0.0, min(value, 200.0)), 1)

    if lefts:
        first_width = pages[min(pages)][0].page_width
        first_height = pages[min(pages)][0].page_height
        layout.margins = Margins(
            top_pt=clamp(statistics.median(tops)),
            bottom_pt=clamp(first_height - statistics.median(bottoms)),
            left_pt=clamp(statistics.median(lefts)),
            right_pt=clamp(first_width - statistics.median(rights)),
        )
    return layout


def _region_for_block(block: BlockInfo, layout: Layout) -> tuple[float, float]:
    regions = layout.regions_by_page.get(block.page_index) or []
    if not regions:
        return (0.0, block.page_width)
    band_top = layout.band_top_by_page.get(block.page_index)
    if band_top is not None and max(line.y1 for line in block.lines) <= band_top - 2.0:
        return (min(r[0] for r in regions), max(r[1] for r in regions))
    if len(regions) == 1:
        return regions[0]
    center = sum((line.x0 + line.x1) / 2 for line in block.lines) / len(block.lines)
    for x0, x1 in regions:
        if x0 <= center <= x1:
            return (x0, x1)
    nearest = min(regions, key=lambda r: min(abs(center - r[0]), abs(center - r[1])))
    return nearest


def _infer_alignment(lines: list[LineInfo], region: tuple[float, float]) -> str | None:
    bx0, bx1 = region
    col_width = bx1 - bx0
    if col_width < 30:
        return None

    col_mid = (bx0 + bx1) / 2.0
    centers = [(line.x0 + line.x1) / 2 for line in lines]
    widths = [line.x1 - line.x0 for line in lines]
    if all(abs(c - col_mid) <= 10.0 for c in centers) and max(widths) <= col_width * 0.92:
        return "center"

    lgaps = [line.x0 - bx0 for line in lines]
    rgaps = [bx1 - line.x1 for line in lines]
    med_l = statistics.median(lgaps)
    med_r = statistics.median(rgaps)

    fill = statistics.median([(line.x1 - line.x0) / col_width for line in lines])
    if med_l <= 3.0 and med_r <= 3.0 and len(lines) >= 3 and fill > 0.85:
        return "justified"
    if med_l <= 3.0:
        return "left"
    if med_r <= 3.0 and med_l > 10.0:
        return "right"
    return None


def _infer_line_spacing(lines: list[LineInfo]) -> float | None:
    if len(lines) < 2:
        return None
    ordered = sorted(lines, key=lambda line: line.baseline)
    deltas = [
        b.baseline - a.baseline
        for a, b in zip(ordered, ordered[1:])
        if b.baseline > a.baseline
    ]
    sizes = [line.dominant_size() for line in ordered]
    sizes = [s for s in sizes if s]
    if not deltas or not sizes:
        return None
    ratio = statistics.median(deltas) / statistics.median(sizes)
    if not 0.5 < ratio < 4.0:
        return None
    return round(ratio, 2)


def _infer_first_line_indent(lines: list[LineInfo], alignment: str | None) -> float | None:
    if alignment not in ("left", "justified") or len(lines) < 2:
        return None
    rest_edge = min(line.x0 for line in lines[1:])
    diff = lines[0].x0 - rest_edge
    return round(diff, 1) if diff > 3.0 else 0.0


def _weighted(values: list[tuple[object, int]]) -> object | None:
    totals: dict[object, int] = {}
    for value, weight in values:
        if value is None or value == "":
            continue
        totals[value] = totals.get(value, 0) + weight
    if not totals:
        return None
    return max(totals.items(), key=lambda item: item[1])[0]


def _majority_bool(values: list[tuple[bool, int]]) -> bool | None:
    true_w = sum(w for v, w in values if v)
    false_w = sum(w for v, w in values if not v)
    if true_w == 0 and false_w == 0:
        return None
    return true_w >= false_w


_KEYWORDS_PREFIX_RE = re.compile(r"^(keywords?|index\s+terms)\s*[—–·:\-.]", re.IGNORECASE)


def _block_text(block: BlockInfo) -> str:
    return re.sub(r"\s+", " ", " ".join(line.text.strip() for line in block.lines)).strip()


def build_raw_blocks(blocks: list[BlockInfo], layout: Layout) -> list[RawBlock]:
    body_sizes: list[float] = []
    for block in blocks:
        for line in block.lines:
            if len(line.text.split()) >= 12:
                size = line.dominant_size()
                if size:
                    body_sizes.append(size)
    median_body_size = statistics.median(body_sizes) if body_sizes else None

    raw: list[RawBlock] = []
    for block in blocks:
        region = _region_for_block(block, layout)
        alignment = _infer_alignment(block.lines, region)
        line_spacing = _infer_line_spacing(block.lines)
        indent = _infer_first_line_indent(block.lines, alignment)

        fonts = []
        sizes = []
        bolds = []
        italics = []
        for line in block.lines:
            for span in line.spans:
                weight = max(len(span.text), 1)
                fonts.append((clean_font_name(span.font), weight))
                sizes.append((round(span.size, 2), weight))
                bolds.append((span.bold, weight))
                italics.append((span.italic, weight))

        fmt = TextFormat(
            font_family=_weighted(fonts),
            font_size_pt=_weighted(sizes),
            bold=_majority_bool(bolds),
            italic=_majority_bool(italics),
            alignment=alignment,
            line_spacing=line_spacing,
            indent_first_line_pt=indent,
        )

        text = _block_text(block)
        if not text:
            continue

        is_heading_like = (
            len(text) <= 90
            and len(text.split()) <= 12
            and not text.rstrip().endswith((".", ",", ";"))
            and (
                fmt.bold is True
                or (median_body_size and fmt.font_size_pt and fmt.font_size_pt >= median_body_size * 1.2)
            )
        )
        named_style = "HEADING_1" if is_heading_like else "NORMAL_TEXT"

        first_line_text = block.lines[0].text.strip()
        stripped_first = re.sub(r"^(\d+(\.\d+)*[.)]?|[IVXLCDM]+[.)]?)\s+", "", first_line_text).strip()
        splits_heading = (
            len(block.lines) > 1
            and (
                match_canonical_section(stripped_first) is not None
                or bool(_KEYWORDS_PREFIX_RE.match(stripped_first))
            )
            and not _KEYWORDS_PREFIX_RE.match(text)
        )

        if splits_heading and len(block.lines) > 1:
            head_fmt = TextFormat(
                font_family=clean_font_name(block.lines[0].spans[0].font),
                font_size_pt=block.lines[0].dominant_size(),
                bold=any(span.bold for span in block.lines[0].spans),
                alignment=alignment,
            )
            raw.append(RawBlock(text=first_line_text, format=head_fmt, named_style_type=named_style))

            remaining_lines = block.lines[1:]
            body_region = _region_for_block(block, layout)
            body_alignment = _infer_alignment(remaining_lines, body_region)
            body_fmt = TextFormat(
                font_family=fmt.font_family,
                font_size_pt=fmt.font_size_pt,
                italic=fmt.italic,
                alignment=body_alignment,
                line_spacing=line_spacing,
                indent_first_line_pt=None,
            )
            raw.append(
                RawBlock(
                    text=re.sub(r"\s+", " ", " ".join(l.text.strip() for l in remaining_lines)).strip(),
                    format=body_fmt,
                    named_style_type="NORMAL_TEXT",
                )
            )
            continue

        raw.append(RawBlock(text=text, format=fmt, named_style_type=named_style))

    return [b for b in raw if b.text]


def parse_pdf(data: bytes) -> NormalizedDocument:
    if not data or not data.lstrip()[:5] == b"%PDF-":
        raise PdfParseError("Uploaded file is not a valid PDF.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PdfParseError(f"Could not open PDF: {exc}") from exc

    if doc.needs_pass:
        raise PdfParseError("PDF is password protected.")

    blocks: list[BlockInfo] = []
    for page_index, page in enumerate(doc):
        if page_index >= MAX_PAGES:
            break
        blocks.extend(_extract_page_blocks(page, page_index))

    if not blocks:
        raise PdfParseError(
            "No extractable text found. The PDF may be scanned images, which are not supported yet."
        )

    layout = _analyze_layout(blocks)
    sections = classify_blocks(build_raw_blocks(blocks, layout))

    first = doc[0]
    width = float(first.rect.width)
    height = float(first.rect.height)
    info = DocumentInfo(
        page_size=PageSize(width_pt=round(width, 2), height_pt=round(height, 2), label=page_size_label(width, height)),
        margins=layout.margins,
        orientation="landscape" if width > height else "portrait",
        columns=layout.columns,
        title=(doc.metadata or {}).get("title") or "",
    )
    return NormalizedDocument(document=info, sections=sections)
