from __future__ import annotations

from typing import Optional

from app.models.document import (
    Alignment,
    DocumentInfo,
    Margins,
    NormalizedDocument,
    PageSize,
    SectionBlock,
    TextFormat,
)
from app.parsing.structure import RawBlock, classify_blocks

EMU_PER_PT = 12700.0

_PAGE_SIZE_TABLE = [
    ("A5", 419.53, 595.28),
    ("A4", 595.28, 841.89),
    ("Letter", 612.0, 792.0),
    ("Legal", 612.0, 1008.0),
    ("Tabloid", 792.0, 1224.0),
    ("Executive", 522.0, 756.0),
]

_ALIGNMENT_MAP = {
    "START": "left",
    "CENTER": "center",
    "END": "right",
    "JUSTIFIED": "justified",
}


def to_pt(quantity: dict | None) -> Optional[float]:
    if not isinstance(quantity, dict):
        return None
    magnitude = quantity.get("magnitude")
    if magnitude is None:
        return None
    magnitude = float(magnitude)
    if quantity.get("unit") == "EMU":
        magnitude /= EMU_PER_PT
    return round(magnitude, 3)


def _page_size_label(width: float, height: float) -> str | None:
    return page_size_label(width, height)


def page_size_label(width: float, height: float) -> str | None:
    for label, std_w, std_h in _PAGE_SIZE_TABLE:
        tolerance = 2.0
        if abs(width - std_w) <= tolerance and abs(height - std_h) <= tolerance:
            return label
        if abs(width - std_h) <= tolerance and abs(height - std_w) <= tolerance:
            return label
    return None


def _alignment(value: str | None) -> Alignment | None:
    return _ALIGNMENT_MAP.get(value)


def _collect_named_text_styles(doc: dict) -> dict[str, dict]:
    styles: dict[str, dict] = {}
    for style_entry in doc.get("namedStyles", {}).get("styles", []):
        named = style_entry.get("namedStyle")
        if named and named.get("namedStyleType"):
            styles[named["namedStyleType"]] = named.get("textStyle", {}) or {}
    return styles


def _merge_run_style(base: dict, run_style: dict) -> dict:
    merged = dict(base)
    merged.update({k: v for k, v in run_style.items() if v is not None})
    return merged


def _run_weighted_values(runs: list[tuple[str, str]], key: str):
    return [(style.get(key), len(text)) for text, style in runs if text]


def _dominant(weighted) -> object | None:
    totals: dict[object, float] = {}
    for value, weight in weighted:
        if value is None:
            continue
        totals[value] = totals.get(value, 0.0) + weight
    if not totals:
        return None
    return max(totals.items(), key=lambda item: item[1])[0]


def _majority_bool(weighted) -> bool | None:
    true_weight = sum(w for v, w in weighted if v is True)
    false_weight = sum(w for v, w in weighted if v is False)
    if true_weight == 0 and false_weight == 0:
        return None
    return true_weight >= false_weight


def _paragraph_format(paragraph: dict, named_styles: dict[str, dict]) -> tuple[TextFormat, str | None]:
    p_style = paragraph.get("paragraphStyle", {}) or {}
    named_style_type = p_style.get("namedStyleType") or "NORMAL_TEXT"
    base_text_style = named_styles.get(named_style_type, {})

    runs: list[tuple[str, str]] = []
    for element in paragraph.get("elements", []):
        text_run = element.get("textRun")
        if not text_run:
            continue
        content = (text_run.get("content") or "").replace("\n", " ").replace("\x0b", " ").strip()
        if content:
            runs.append((content, _merge_run_style(base_text_style, text_run.get("textStyle", {}) or {})))

    fonts = _run_weighted_values(runs, "fontFamily")
    sizes = [
        ((style.get("fontSize") or {}).get("magnitude"), len(text))
        for text, style in runs
        if isinstance((style.get("fontSize") or {}).get("magnitude"), (int, float))
    ]
    bolds = _run_weighted_values(runs, "bold")
    italics = _run_weighted_values(runs, "italic")

    line_spacing = p_style.get("lineSpacing")

    fmt = TextFormat(
        font_family=_dominant(fonts),
        font_size_pt=round(float(_dominant(sizes)), 2) if _dominant(sizes) is not None else None,
        bold=_majority_bool(bolds),
        italic=_majority_bool(italics),
        alignment=_alignment(p_style.get("alignment")),
        line_spacing=round(line_spacing / 100.0, 3) if line_spacing else None,
        space_above_pt=to_pt(p_style.get("spaceAbove")),
        space_below_pt=to_pt(p_style.get("spaceBelow")),
        indent_first_line_pt=to_pt(p_style.get("indentFirstLine")),
        indent_start_pt=to_pt(p_style.get("indentStart")),
        indent_end_pt=to_pt(p_style.get("indentEnd")),
    )
    return fmt, named_style_type


def _iter_paragraphs(element: dict, named_styles: dict[str, dict]) -> list[RawBlock]:
    blocks: list[RawBlock] = []
    if "paragraph" in element:
        paragraph = element["paragraph"]
        fmt, style_type = _paragraph_format(paragraph, named_styles)
        text_parts = []
        for sub in paragraph.get("elements", []):
            run = sub.get("textRun")
            if run:
                text_parts.append(run.get("content") or "")
        text = " ".join("".join(text_parts).split())
        if text:
            blocks.append(RawBlock(text=text, format=fmt, named_style_type=style_type))
    elif "table" in element:
        for row in element["table"].get("tableRows", []):
            for cell in row.get("tableCells", []):
                for child in cell.get("content", []):
                    blocks.extend(_iter_paragraphs(child, named_styles))
    return blocks


def parse_google_doc(doc: dict) -> NormalizedDocument:
    doc_style = doc.get("documentStyle", {}) or {}
    page_size_raw = doc_style.get("pageSize", {}) or {}
    width_pt = to_pt(page_size_raw.get("width")) or 0.0
    height_pt = to_pt(page_size_raw.get("height")) or 0.0

    margins = Margins(
        top_pt=to_pt(doc_style.get("marginTop")) or 0.0,
        bottom_pt=to_pt(doc_style.get("marginBottom")) or 0.0,
        left_pt=to_pt(doc_style.get("marginLeft")) or 0.0,
        right_pt=to_pt(doc_style.get("marginRight")) or 0.0,
    )

    columns = 1
    column_spacing: float | None = None
    column_props = doc_style.get("columnProperties")
    if isinstance(column_props, dict) and column_props.get("count"):
        columns = int(column_props["count"])
        column_spacing = to_pt(column_props.get("spacing"))
    for element in doc.get("body", {}).get("content", []):
        section_break = element.get("sectionBreak")
        if not section_break:
            continue
        section_style = section_break.get("sectionStyle", {}) or {}
        props_list = section_style.get("columnProperties")
        if isinstance(props_list, list) and props_list:
            columns = max(columns, len(props_list))
            spacing = to_pt(props_list[0].get("spacing"))
            column_spacing = spacing if spacing is not None else column_spacing
        elif isinstance(section_style.get("columns"), int):
            columns = max(columns, section_style["columns"])

    orientation = "landscape" if width_pt > height_pt else "portrait"

    info = DocumentInfo(
        page_size=PageSize(
            width_pt=round(width_pt, 2),
            height_pt=round(height_pt, 2),
            label=_page_size_label(width_pt, height_pt),
        ),
        margins=margins,
        orientation=orientation,
        columns=columns,
        column_spacing_pt=column_spacing,
        title=doc.get("title", "") or "",
    )

    named_styles = _collect_named_text_styles(doc)
    raw_blocks: list[RawBlock] = []
    for element in doc.get("body", {}).get("content", []):
        raw_blocks.extend(_iter_paragraphs(element, named_styles))

    sections = classify_blocks(raw_blocks)
    return NormalizedDocument(document=info, sections=sections)
