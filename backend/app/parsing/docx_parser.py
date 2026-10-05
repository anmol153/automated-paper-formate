"""DOCX parser: converts a Word .docx file (OOXML) into the shared NormalizedDocument model.

Only the standard library is used (zipfile + xml.etree), matching the project's
approach of emitting NormalizedDocument from structured sources. Styles, direct
formatting, section properties and table content are all read from the OOXML parts.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from app.models.document import (
    DocumentInfo,
    Margins,
    NormalizedDocument,
    PageSize,
    TextFormat,
)
from app.parsing.errors import DocxParseError
from app.parsing.normalizer import page_size_label
from app.parsing.page_estimate import estimate_pages
from app.parsing.structure import RawBlock, classify_blocks

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DC = "{http://purl.org/dc/elements/1.1/}"

_MARGIN_KEYS = {
    "top": "top_pt",
    "bottom": "bottom_pt",
    "left": "left_pt",
    "right": "right_pt",
}

_JC_MAP = {
    "start": "left",
    "left": "left",
    "center": "center",
    "end": "right",
    "right": "right",
    "both": "justified",
    "distribute": "justified",
    "justify": "justified",
}


def _bool_val(element) -> bool:
    value = element.get(f"{W}val")
    return value is None or value not in ("0", "false", "off")


def _twips_to_pt(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value) / 20.0, 2)
    except ValueError:
        return None


def _child(element, name: str):
    if element is None:
        return None
    return element.find(f"{W}{name}")


def _children(element, name: str):
    if element is None:
        return []
    return element.findall(f"{W}{name}")


def _rpr_dict(rpr) -> dict:
    result: dict = {}
    if rpr is None:
        return result
    fonts = _child(rpr, "rFonts")
    if fonts is not None:
        result["family"] = fonts.get(f"{W}ascii") or fonts.get(f"{W}hAnsi")
    size = _child(rpr, "sz")
    if size is not None:
        try:
            result["size"] = float(size.get(f"{W}val")) / 2.0
        except (TypeError, ValueError):
            pass
    bold = _child(rpr, "b")
    if bold is not None:
        result["bold"] = _bool_val(bold)
    italic = _child(rpr, "i")
    if italic is not None:
        result["italic"] = _bool_val(italic)
    return result


def _ppr_dict(ppr) -> dict:
    result: dict = {}
    if ppr is None:
        return result
    jc = _child(ppr, "jc")
    if jc is not None:
        result["jc"] = _JC_MAP.get(jc.get(f"{W}val"), jc.get(f"{W}val"))

    spacing = _child(ppr, "spacing")
    if spacing is not None:
        line = spacing.get(f"{W}line")
        rule = spacing.get(f"{W}lineRule")
        if line and rule in (None, "auto"):
            try:
                line_value = float(line)
                result["line_multiple"] = round(line_value / 240.0, 3)
            except (TypeError, ValueError):
                pass
        for attr, key in (
            ("before", "before_pt"),
            ("after", "after_pt"),
        ):
            value = _twips_to_pt(spacing.get(f"{W}{attr}"))
            if value is not None:
                result[key] = value

    ind = _child(ppr, "ind")
    if ind is not None:
        first = _twips_to_pt(ind.get(f"{W}firstLine"))
        if first is not None:
            hanging = _twips_to_pt(ind.get(f"{W}hanging")) or 0.0
            result["first_line_pt"] = max(first - hanging, 0.0)
        for attr, key in (("left", "left_pt"), ("right", "right_pt")):
            value = _twips_to_pt(ind.get(f"{W}{attr}"))
            if value is not None:
                result[key] = value
    return result


@dataclass
class StyleInfo:
    style_id: str
    name: str = ""
    based_on: str | None = None
    rpr: dict = field(default_factory=dict)
    ppr: dict = field(default_factory=dict)


def _parse_paragraph_style(style) -> StyleInfo:
    style_id = style.get(f"{W}styleId") or ""
    info = StyleInfo(style_id=style_id)
    name_el = _child(style, "name")
    if name_el is not None:
        info.name = name_el.get(f"{W}val") or ""
    based_on = _child(style, "basedOn")
    if based_on is not None:
        info.based_on = based_on.get(f"{W}val")
    info.rpr = _rpr_dict(_child(style, "rPr"))
    info.ppr = _ppr_dict(_child(style, "pPr"))
    return info


def _load_styles(styles_root) -> tuple[dict, dict, dict]:
    styles: dict[str, StyleInfo] = {}
    defaults: dict = {"rpr": {}, "ppr": {}}
    if styles_root is None:
        return styles, defaults["rpr"], defaults["ppr"]

    doc_defaults = _child(styles_root, "docDefaults")
    if doc_defaults is not None:
        rpr_default = _child(doc_defaults, "rPrDefault")
        if rpr_default is not None:
            defaults["rpr"] = _rpr_dict(_child(rpr_default, "rPr"))
        ppr_default = _child(doc_defaults, "pPrDefault")
        if ppr_default is not None:
            defaults["ppr"] = _ppr_dict(_child(ppr_default, "pPr"))

    for style in _children(styles_root, "style"):
        style_type = style.get(f"{W}type")
        if style_type == "paragraph":
            info = _parse_paragraph_style(style)
            styles[info.style_id] = info
    return styles, defaults["rpr"], defaults["ppr"]


def _effective_style(
    style_id: str | None, styles: dict[str, StyleInfo], default_rpr: dict, default_ppr: dict
) -> tuple[dict, dict]:
    chain: list[str] = []
    current = style_id if style_id else "Normal"
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        current = styles[current].based_on if current in styles else None

    rpr = dict(default_rpr)
    ppr = dict(default_ppr)
    for style_id_in_chain in reversed(chain):
        info = styles.get(style_id_in_chain)
        if info is None:
            continue
        rpr.update({k: v for k, v in info.rpr.items() if v is not None})
        ppr.update({k: v for k, v in info.ppr.items() if v is not None})
    return rpr, ppr


def _iter_runs_in_paragraph(paragraph) -> list:
    runs = []
    for child in paragraph:
        if child.tag == f"{W}r":
            runs.append(child)
        elif child.tag in (f"{W}hyperlink", f"{W}ins", f"{W}del", f"{W}moveFrom", f"{W}moveTo"):
            runs.extend(_iter_runs_in_paragraph(child))
        elif child.tag == f"{W}sdt":
            content = _child(child, "sdtContent")
            if content is not None:
                runs.extend(_iter_runs_in_paragraph(content))
    return runs


def _run_text(run) -> str:
    parts: list[str] = []
    for child in run:
        tag = child.tag
        if tag == f"{W}t":
            parts.append(child.text or "")
        elif tag == f"{W}tab":
            parts.append(" ")
        elif tag == f"{W}br":
            parts.append(" ")
        elif tag == f"{W}noBreakHyphen":
            parts.append("\u2011")
        elif tag == f"{W}instrText":
            parts.append(" ")
        elif tag == f"{W}r":
            parts.append(_run_text(child))
    return "".join(parts)


def _dominant(weighted) -> object | None:
    totals: dict[object, float] = {}
    for value, weight in weighted:
        if value is None:
            continue
        totals[value] = totals.get(value, 0.0) + weight
    if not totals:
        return None
    return max(totals.items(), key=lambda item: item[1])[0]


def _majority(weighted) -> bool | None:
    true_weight = sum(weight for value, weight in weighted if value)
    false_weight = sum(weight for value, weight in weighted if not value)
    if true_weight == 0 and false_weight == 0:
        return None
    return true_weight >= false_weight


def _build_block(
    paragraph, styles: dict[str, StyleInfo], default_rpr: dict, default_ppr: dict
) -> RawBlock | None:
    ppr = _child(paragraph, "pPr")
    style_id: str | None = None
    style_name = ""
    if ppr is not None:
        p_style = _child(ppr, "pStyle")
        if p_style is not None:
            style_id = p_style.get(f"{W}val")
            style_name = styles[style_id].name if style_id in styles else ""

    eff_rpr, eff_ppr = _effective_style(style_id, styles, default_rpr, default_ppr)
    if ppr is not None:
        direct = _ppr_dict(ppr)
        eff_ppr.update({key: value for key, value in direct.items() if value is not None})

    families: list[tuple[str | None, int]] = []
    sizes: list[tuple[float, int]] = []
    bolds: list[tuple[bool, int]] = []
    italics: list[tuple[bool, int]] = []
    text_parts: list[str] = []

    for run in _iter_runs_in_paragraph(paragraph):
        rpr = _child(run, "rPr")
        run_style = dict(eff_rpr)
        if rpr is not None:
            run_style.update({key: value for key, value in _rpr_dict(rpr).items() if value is not None})
        text = _run_text(run)
        weight = len(text)
        if not text:
            continue
        text_parts.append(text)
        families.append((run_style.get("family"), weight))
        size = run_style.get("size")
        if size is not None:
            sizes.append((float(size), weight))
        bolds.append((run_style.get("bold", False), weight))
        italics.append((run_style.get("italic", False), weight))

    text = re.sub(r"\s+", " ", " ".join(text_parts)).strip()
    if not text:
        return None

    alignment = eff_ppr.get("jc")
    line_multiple = eff_ppr.get("line_multiple")
    size_value = _dominant(sizes)
    fmt = TextFormat(
        font_family=_dominant(families),
        font_size_pt=round(float(size_value), 2) if size_value is not None else None,
        bold=_majority(bolds),
        italic=_majority(italics),
        alignment=alignment,
        line_spacing=round(float(line_multiple), 3) if line_multiple is not None else None,
        space_above_pt=eff_ppr.get("before_pt"),
        space_below_pt=eff_ppr.get("after_pt"),
        indent_first_line_pt=eff_ppr.get("first_line_pt"),
        indent_start_pt=eff_ppr.get("left_pt"),
        indent_end_pt=eff_ppr.get("right_pt"),
    )

    is_heading = style_name.lower().startswith("heading") or (style_id or "").lower().startswith("heading")
    named_style_type = "HEADING_1" if is_heading else "NORMAL_TEXT"
    return RawBlock(text=text, format=fmt, named_style_type=named_style_type)


def _iter_paragraphs(element, styles, default_rpr, default_ppr, blocks: list[RawBlock]) -> None:
    for child in element:
        if child.tag == f"{W}p":
            block = _build_block(child, styles, default_rpr, default_ppr)
            if block is not None:
                blocks.append(block)
        elif child.tag == f"{W}tbl":
            for row in _children(child, "tr"):
                for cell in _children(row, "tc"):
                    _iter_paragraphs(cell, styles, default_rpr, default_ppr, blocks)


def _sect_pr(body) -> ET.Element | None:
    last: ET.Element | None = None
    for el in body.iter(f"{W}sectPr"):
        last = el
    return last


def _core_title(core_root) -> str:
    if core_root is None:
        return ""
    title = core_root.find(f"{DC}title")
    return (title.text or "").strip() if title is not None else ""


def parse_docx(data: bytes) -> NormalizedDocument:
    if not data or data[:2] != b"PK":
        raise DocxParseError("Uploaded file is not a valid DOCX (missing ZIP header).")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DocxParseError(f"Could not open DOCX archive: {exc}") from exc

    try:
        document_part = archive.read("word/document.xml")
    except KeyError as exc:
        raise DocxParseError("The DOCX has no word/document.xml part.") from exc

    try:
        document_root = ET.fromstring(document_part)
    except ET.ParseError as exc:
        raise DocxParseError(f"Could not parse word/document.xml: {exc}") from exc

    styles_root = None
    try:
        styles_root = ET.fromstring(archive.read("word/styles.xml"))
    except (KeyError, ET.ParseError, OSError):
        styles_root = None

    core_root = None
    try:
        core_root = ET.fromstring(archive.read("docProps/core.xml"))
    except (KeyError, ET.ParseError, OSError):
        core_root = None

    styles, default_rpr, default_ppr = _load_styles(styles_root)

    body = _child(document_root, "body")
    if body is None:
        raise DocxParseError("The DOCX body is missing.")

    blocks: list[RawBlock] = []
    _iter_paragraphs(body, styles, default_rpr, default_ppr, blocks)
    if not blocks:
        raise DocxParseError("No readable text found in the DOCX.")

    sections = classify_blocks(blocks)

    sect = _sect_pr(body)
    width, height = 612.0, 792.0
    orientation = "portrait"
    margins = Margins(top_pt=72, bottom_pt=72, left_pt=72, right_pt=72)
    columns = 1
    column_spacing: float | None = None

    if sect is not None:
        pg_size = _child(sect, "pgSz")
        if pg_size is not None:
            width = float(pg_size.get(f"{W}w", 12240)) / 20.0
            height = float(pg_size.get(f"{W}h", 15840)) / 20.0
            if pg_size.get(f"{W}orient") == "landscape":
                orientation = "landscape"
                width, height = max(width, height), min(width, height)
        pg_mar = _child(sect, "pgMar")
        if pg_mar is not None:
            margins = Margins(
                top_pt=_twips_to_pt(pg_mar.get(f"{W}top")) or 72.0,
                bottom_pt=_twips_to_pt(pg_mar.get(f"{W}bottom")) or 72.0,
                left_pt=_twips_to_pt(pg_mar.get(f"{W}left")) or 72.0,
                right_pt=_twips_to_pt(pg_mar.get(f"{W}right")) or 72.0,
            )
        cols = _child(sect, "cols")
        if cols is not None:
            columns = max(1, int(cols.get(f"{W}num", 1)))
            spacing_value = _twips_to_pt(cols.get(f"{W}space"))
            if spacing_value is not None:
                column_spacing = spacing_value

    info = DocumentInfo(
        page_size=PageSize(
            width_pt=round(width, 2),
            height_pt=round(height, 2),
            label=page_size_label(width, height),
        ),
        margins=margins,
        orientation=orientation,
        columns=columns,
        column_spacing_pt=column_spacing,
        title=_core_title(core_root),
    )
    normalized = NormalizedDocument(document=info, sections=sections)
    info.page_count = estimate_pages(normalized)
    info.page_count_exact = False
    return normalized


__all__ = ["parse_docx", "DocxParseError"]