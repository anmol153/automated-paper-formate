from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.document import SectionBlock, TextFormat


@dataclass
class RawBlock:
    text: str
    format: TextFormat
    named_style_type: str | None = None

    @property
    def is_heading_style(self) -> bool:
        return bool(self.named_style_type and self.named_style_type.startswith("HEADING_"))


_NUMBERING_PREFIX_RE = re.compile(r"^(\d+(\.\d+)*[.)]?|[IVXLCDM]+[.)]?)\s+", re.IGNORECASE)

_SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "Abstract": re.compile(r"^(abstract|summary)\b[:.\s]*$", re.IGNORECASE),
    "Introduction": re.compile(r"^(introduction|background)\b", re.IGNORECASE),
    "Related Work": re.compile(r"^(related\s+works?|literature\s+(review|survey))\b", re.IGNORECASE),
    "Methodology": re.compile(
        r"^(methods?|methodology|materials?\s+and\s+methods?|experimental(s|\s+(setup|section|design))?"
        r"|system\s+(design|architecture|model)|proposed\s+(method|approach|scheme)|approach)\b",
        re.IGNORECASE,
    ),
    "Results": re.compile(
        r"^(results?(\s*(and|&)\s*discussion)?|discussion|evaluation|experiments?(al\s+results)?|analysis)\b",
        re.IGNORECASE,
    ),
    "Conclusion": re.compile(r"^(conclusions?|concluding\s+remarks?|final\s+remarks?)\b", re.IGNORECASE),
    "References": re.compile(r"^(references|bibliography|works\s+cited)\b[:.\s]*$", re.IGNORECASE),
}

_KEYWORDS_PATTERN = re.compile(r"^(keywords?|index\s+terms)\s*[—–·:\-.]", re.IGNORECASE)

_MAX_AUTHORS_CHARS = 400
_MAX_CAPS_HEADING_CHARS = 90


def _strip_numbering(text: str) -> str:
    return _NUMBERING_PREFIX_RE.sub("", text).strip()


def match_canonical_section(text: str) -> str | None:
    candidate = _strip_numbering(text)
    for canonical, pattern in _SECTION_PATTERNS.items():
        if pattern.match(candidate):
            return canonical
    return None


def _is_caps_heading(text: str) -> bool:
    return (
        len(text) <= _MAX_CAPS_HEADING_CHARS
        and text.isupper()
        and any(ch.isalpha() for ch in text)
    )


def classify_blocks(blocks: list[RawBlock]) -> list[SectionBlock]:
    sections: list[SectionBlock] = []
    if not blocks:
        return sections

    index = 0
    first = blocks[0]
    first_canonical = match_canonical_section(first.text)
    if first_canonical != "Abstract":
        sections.append(SectionBlock(type="title", text=first.text, format=first.format))
        index = 1

    author_chunks: list[RawBlock] = []
    while index < len(blocks):
        block = blocks[index]
        if match_canonical_section(block.text) or _KEYWORDS_PATTERN.match(_strip_numbering(block.text)):
            break
        if len(block.text) > _MAX_AUTHORS_CHARS or block.is_heading_style:
            break
        author_chunks.append(block)
        index += 1
    if author_chunks:
        sections.append(
            SectionBlock(
                type="authors",
                text=" ".join(b.text for b in author_chunks),
                format=author_chunks[0].format,
            )
        )

    current_section: str | None = None
    abstract_buffer: list[TextFormat] = []
    abstract_texts: list[str] = []

    def flush_abstract() -> None:
        nonlocal abstract_buffer, abstract_texts
        if abstract_buffer:
            sections.append(
                SectionBlock(
                    type="abstract",
                    text=" ".join(abstract_texts)[:2000],
                    format=aggregate_formats(abstract_buffer),
                )
            )
            abstract_buffer, abstract_texts = [], []

    while index < len(blocks):
        block = blocks[index]
        stripped = _strip_numbering(block.text)
        canonical = match_canonical_section(block.text)

        if canonical:
            flush_abstract()
            sections.append(SectionBlock(type="heading", name=canonical, text=block.text, format=block.format))
            current_section = canonical
            index += 1
            continue

        keyword_match = _KEYWORDS_PATTERN.match(stripped)
        if keyword_match:
            flush_abstract()
            keyword_text = stripped[keyword_match.end():].strip(" :.—-")
            sections.append(
                SectionBlock(type="keywords", name="Keywords", text=keyword_text, format=block.format)
            )
            current_section = "Keywords"
            index += 1
            continue

        if block.is_heading_style or _is_caps_heading(block.text):
            flush_abstract()
            name = block.text.title() if block.text.isupper() else block.text
            sections.append(SectionBlock(type="heading", name=name, text=block.text, format=block.format))
            current_section = name
            index += 1
            continue

        if current_section == "Abstract":
            abstract_buffer.append(block.format)
            abstract_texts.append(block.text)
            index += 1
            continue

        sections.append(SectionBlock(type="body", name=current_section, text=block.text, format=block.format))
        index += 1

    flush_abstract()
    return sections


def aggregate_formats(formats: list[TextFormat]) -> TextFormat:
    def mode(values):
        counts: dict[object, int] = {}
        for v in values:
            if v is not None:
                counts[v] = counts.get(v, 0) + 1
        return max(counts.items(), key=lambda item: item[1])[0] if counts else None

    def majority_bool(values):
        present = [v for v in values if v is not None]
        if not present:
            return None
        trues = sum(1 for v in present if v)
        falses = len(present) - trues
        return trues >= falses

    return TextFormat(
        font_family=mode([f.font_family for f in formats]),
        font_size_pt=mode([f.font_size_pt for f in formats]),
        bold=majority_bool([f.bold for f in formats]),
        italic=majority_bool([f.italic for f in formats]),
        alignment=mode([f.alignment for f in formats]),
        line_spacing=mode([f.line_spacing for f in formats]),
        space_above_pt=mode([f.space_above_pt for f in formats]),
        space_below_pt=mode([f.space_below_pt for f in formats]),
        indent_first_line_pt=mode([f.indent_first_line_pt for f in formats]),
        indent_start_pt=mode([f.indent_start_pt for f in formats]),
        indent_end_pt=mode([f.indent_end_pt for f in formats]),
    )
