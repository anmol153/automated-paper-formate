"""Extracted facts about a submitted paper.

The normalised document captures what the *template* comparison needs, which is a
narrow slice of what a human format-checker looks at. ``PaperFacts`` is the wide
slice: everything the configurable rules can be evaluated against, plus the raw
evidence behind each detection so a manual reviewer can verify a finding.

Every count that depends on heuristics is reported alongside the confidence of
the extraction that produced it, because a "0 figures" reading from a PDF is far
less trustworthy than the same reading from LaTeX source.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Confidence = Literal["exact", "high", "medium", "low", "unknown"]


class FileFacts(BaseModel):
    filename: str = ""
    extension: str = ""
    format: str = ""
    size_bytes: int = 0
    sha256: str = ""
    author_supplied_name: Optional[str] = None
    author_supplied_email: Optional[str] = None
    author_supplied_track: Optional[str] = None


class LayoutFacts(BaseModel):
    page_count: Optional[int] = None
    page_count_exact: bool = False
    page_count_confidence: Confidence = "unknown"
    page_size_label: Optional[str] = None
    width_pt: Optional[float] = None
    height_pt: Optional[float] = None
    orientation: str = "portrait"
    columns: int = 1
    column_spacing_pt: Optional[float] = None
    margins_pt: dict[str, float] = Field(default_factory=dict)
    margins_confidence: Confidence = "unknown"


class TypographyFacts(BaseModel):
    fonts_used: dict[str, int] = Field(default_factory=dict)
    dominant_font: Optional[str] = None
    body_font: Optional[str] = None
    body_font_size_pt: Optional[float] = None
    title_font_size_pt: Optional[float] = None
    heading_font_size_pt: Optional[float] = None
    heading_levels: dict[str, float] = Field(default_factory=dict)
    line_spacing: Optional[float] = None
    alignment_distribution: dict[str, int] = Field(default_factory=dict)
    first_line_indent_pt: Optional[float] = None
    space_above_pt: Optional[float] = None
    space_below_pt: Optional[float] = None
    distinct_body_font_sizes: list[float] = Field(default_factory=list)
    out_of_vocabulary_fonts: list[str] = Field(default_factory=list)


class StructureFacts(BaseModel):
    sections_present: list[str] = Field(default_factory=list)
    headings: list[dict[str, Any]] = Field(default_factory=list)
    numbered_headings: list[str] = Field(default_factory=list)
    missing_canonical_sections: list[str] = Field(default_factory=list)
    has_abstract: bool = False
    abstract_word_count: Optional[int] = None
    abstract_truncated: bool = False
    has_keywords: bool = False
    keyword_count: Optional[int] = None
    keywords: list[str] = Field(default_factory=list)
    title_present: bool = False
    title_text: str = ""
    author_block_present: bool = False
    author_block_text: str = ""
    author_block_placeholder_only: bool = False
    reference_entry_count: Optional[int] = None
    reference_count_confidence: Confidence = "unknown"
    body_word_count: int = 0
    total_word_count: int = 0


class AssetFacts(BaseModel):
    figures: int = 0
    tables: int = 0
    equations: int = 0
    algorithms: int = 0
    listings: int = 0
    footnotes: int = 0
    bibliography_items: int = 0
    confidence: Confidence = "unknown"


class IdentityFacts(BaseModel):
    author_block_present: bool = False
    author_block_text: str = ""
    author_block_placeholder_only: bool = False
    detected_person_names: list[str] = Field(default_factory=list)
    detected_emails: list[str] = Field(default_factory=list)
    detected_urls: list[str] = Field(default_factory=list)
    detected_orcids: list[str] = Field(default_factory=list)
    detected_affiliations: list[str] = Field(default_factory=list)
    acknowledgement_present: bool = False
    acknowledgement_text: str = ""
    funding_present: bool = False
    funding_text: str = ""
    self_citation_count: Optional[int] = None
    anonymous_placeholder_present: bool = False
    metadata_leaks: dict[str, str] = Field(default_factory=dict)
    anonymisation_score: Optional[int] = None
    notes: list[str] = Field(default_factory=list)


class LatexFacts(BaseModel):
    document_class: Optional[str] = None
    class_options: list[str] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)
    font_packages: list[str] = Field(default_factory=list)
    geometry_options: dict[str, str] = Field(default_factory=dict)
    linespread: Optional[float] = None
    parindent: Optional[str] = None
    has_maketitle: bool = False
    title_macro: Optional[str] = None
    author_macro: Optional[str] = None
    bibliography_style: Optional[str] = None
    has_anonymous_package: bool = False
    explicit_page_break_commands: int = 0
    unresolved_includes: list[str] = Field(default_factory=list)
    inline_math_spans: int = 0
    display_math_spans: int = 0


class DocxFacts(BaseModel):
    template_name: Optional[str] = None
    application: Optional[str] = None
    app_version: Optional[str] = None
    last_modified_by: Optional[str] = None
    revision: Optional[int] = None
    core_title: Optional[str] = None
    embedded_image_count: int = 0
    has_comments: bool = False
    has_track_changes: bool = False
    default_style_font: Optional[str] = None
    default_style_size_pt: Optional[float] = None


class PdfFacts(BaseModel):
    page_count: int = 0
    metadata: dict[str, str] = Field(default_factory=dict)
    has_javascript: bool = False
    has_embedded_files: bool = False
    has_form_fields: bool = False
    is_encrypted: bool = False
    page_labels: list[int] = Field(default_factory=list)


class PaperFacts(BaseModel):
    """Everything the rule engine can consult about one submitted paper."""

    file: FileFacts = Field(default_factory=FileFacts)
    layout: LayoutFacts = Field(default_factory=LayoutFacts)
    typography: TypographyFacts = Field(default_factory=TypographyFacts)
    structure: StructureFacts = Field(default_factory=StructureFacts)
    assets: AssetFacts = Field(default_factory=AssetFacts)
    identity: IdentityFacts = Field(default_factory=IdentityFacts)
    latex: Optional[LatexFacts] = None
    docx: Optional[DocxFacts] = None
    pdf: Optional[PdfFacts] = None
    parser: str = ""
    parse_warnings: list[str] = Field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "format": self.file.format,
            "pages": self.layout.page_count,
            "pages_exact": self.layout.page_count_exact,
            "words": self.structure.total_word_count,
            "body_font": self.typography.body_font,
            "body_size": self.typography.body_font_size_pt,
            "sections": len(self.structure.sections_present),
            "figures": self.assets.figures,
            "tables": self.assets.tables,
            "references": self.structure.reference_entry_count,
        }


__all__ = [
    "AssetFacts",
    "Confidence",
    "DocxFacts",
    "FileFacts",
    "IdentityFacts",
    "LatexFacts",
    "LayoutFacts",
    "PaperFacts",
    "PdfFacts",
    "StructureFacts",
    "TypographyFacts",
]
