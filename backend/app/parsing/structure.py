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

# Springer/LNCS and most numeric styles print an unnumbered bibliography with
# no "References" heading, so a heading-based rule finds nothing. A reference
# entry instead starts with surnames and initials -- "Author, F.:" or
# "Smith, J., Doe, A.:" -- and usually carries a year.
_REFERENCE_ENTRY_PATTERN = re.compile(
    r"^[A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+)?,"
    r"(?:\s*[A-Z]\.(?:\s*[A-Z]\.)*|"
    r"(?:\s+[A-Z][\w'’\-]+,\s*[A-Z]\.)+)"
    r"[^:]{0,120}:"
)
_REFERENCE_YEAR_PATTERN = re.compile(r"(\(?(?:19|20)\d{2}[a-z]?\)?)")

_MIN_REFERENCE_ENTRIES = 2

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


def looks_like_reference_entry(text: str) -> bool:
    """Whether a block reads like a bibliography entry rather than prose."""
    stripped = text.strip()
    if not stripped or len(stripped) > 600:
        return False
    # Prose sentences end with a full stop and rarely open with "Surname, A.:".
    if not _REFERENCE_ENTRY_PATTERN.match(stripped):
        return False
    return bool(_REFERENCE_YEAR_PATTERN.search(stripped))


def _find_reference_start(blocks: list[RawBlock]) -> int:
    """Index of the first block of a trailing bibliography, or ``len(blocks)``.

    A run of at least ``_MIN_REFERENCE_ENTRIES`` consecutive reference-shaped
    blocks near the end of the document is treated as the bibliography, with
    everything after it counted as references too.
    """
    run = 0
    for index in range(len(blocks) - 1, -1, -1):
        if looks_like_reference_entry(blocks[index].text):
            run += 1
            if run >= _MIN_REFERENCE_ENTRIES:
                # Walk back over any extra entries that continue the run.
                start = index
                while start - 1 >= 0 and looks_like_reference_entry(blocks[start - 1].text):
                    start -= 1
                return start
        else:
            run = 0
    return len(blocks)


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
    reference_start = _find_reference_start(blocks)

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

        if index >= reference_start and not canonical:
            # Trailing bibliography with no "References" heading: everything
            # from here on is a reference entry.
            sections.append(SectionBlock(type="references", text=block.text, format=block.format))
            index += 1
            continue

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


def aggregate_formats(formats: list[TextFormat], weights: list[int] | None = None) -> TextFormat:
    """The most representative format across a set of blocks.

    ``weights`` lets a caller express how much each block matters. Template
    inference passes text length, because a proceedings template contains many
    short 9pt captions, references and footnotes that outnumber the body blocks
    while carrying a fraction of their text -- counting blocks alone reads a
    Springer LNCS template as a 9pt paper when its body is 10pt.
    """
    if weights is None:
        weights = [1] * len(formats)

    def mode(values):
        counts: dict[object, float] = {}
        for value, weight in zip(values, weights):
            if value is None or weight <= 0:
                continue
            counts[value] = counts.get(value, 0.0) + weight
        return max(counts.items(), key=lambda item: item[1])[0] if counts else None

    def majority_bool(values):
        weighted: list[tuple[object, int]] = [
            (v, w) for v, w in zip(values, weights) if v is not None and w > 0
        ]
        if not weighted:
            return None
        trues = sum(w for v, w in weighted if v)
        falses = sum(w for v, w in weighted if not v)
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
