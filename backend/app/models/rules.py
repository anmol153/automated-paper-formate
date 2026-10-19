"""Configurable submission rule set.

A ``RuleSet`` is what a conference manager configures once, at setup, and what
every subsequent submission is checked against. Rules are split into groups so
the rule editor can render one panel per group:

* ``file_type``     — accepted extensions, size ceiling, source-vs-PDF policy
* ``pages``         — page limit, page size, orientation, columns, margins
* ``sections``      — required sections, abstract/keywords, reference count
* ``anonymisation`` — identity leakage checks
* ``typography``    — per-element font family / size / weight / alignment
* ``paragraph``     — spacing and indentation of body text

Every rule field is optional. ``None`` means "this publisher does not care",
which the engine reports as ``not_applicable`` rather than as a failure — the
difference matters when a rule cannot be measured for a given input format.

``TemplateRules`` at the bottom is the older, narrower model used by the
template-vs-paper comparison path; it is kept for backwards compatibility.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.document import Margins, TextFormat

CANONICAL_SECTION_ORDER = (
    "Abstract",
    "Keywords",
    "Introduction",
    "Related Work",
    "Methodology",
    "Results",
    "Conclusion",
    "References",
)


class Severity(str, Enum):
    """How much a failed check matters to the accept/reject decision."""

    BLOCKING = "blocking"
    WARNING = "warning"
    ADVISORY = "advisory"


class DecisionRule(BaseModel):
    """How per-check severities combine into one verdict."""

    blocking_severity: Severity = Severity.BLOCKING
    reject_if_any_blocking: bool = True
    reject_if_any_warning: bool = False
    min_score_to_accept: Optional[int] = Field(
        None, description="Optional overall-score floor; 0-100. None disables the floor."
    )


class PublisherDetails(BaseModel):
    """Contact and identity information shown to authors alongside results."""

    publisher_name: str = ""
    conference_name: str = ""
    contact_email: str = ""
    support_url: str = ""
    deadline: Optional[str] = None
    notes_for_authors: str = ""


class FileTypeRule(BaseModel):
    accepted_extensions: list[str] = Field(default_factory=lambda: ["pdf"])
    max_file_size_mb: Optional[float] = 20.0
    require_exactly_one_paper_per_submission: bool = True
    reject_if_extension_not_accepted: bool = True
    reject_if_extension_missing: bool = True
    allow_source_upload: bool = True
    require_source_when_pdf_given: bool = False

    def accepts(self, extension: str | None) -> bool:
        if not extension:
            return False
        return extension.casefold().lstrip(".") in {
            e.casefold().lstrip(".") for e in self.accepted_extensions
        }


class PageRule(BaseModel):
    max_pages: Optional[int] = None
    min_pages: Optional[int] = None
    count_references_toward_limit: bool = True
    page_size_label: Optional[str] = None
    orientation: Optional[Literal["portrait", "landscape"]] = None
    columns: Optional[int] = None
    margins: Optional[Margins] = None
    margin_tolerance_pt: float = 2.0
    # Applied when the page count had to be estimated rather than measured.
    estimate_tolerance_pages: int = 1


class SectionRule(BaseModel):
    required_sections: list[str] = Field(default_factory=list)
    forbid_sections: list[str] = Field(default_factory=list)
    abstract_required: bool = True
    abstract_max_words: Optional[int] = None
    keywords_required: bool = False
    min_reference_entries: Optional[int] = None
    allow_section_numbering: bool = True
    require_canonical_heading_names: bool = False


class AnonymisationRule(BaseModel):
    required: bool = False
    allow_author_block: bool = False
    allow_anonymous_placeholder: bool = True
    detect_emails: bool = True
    detect_affiliations: bool = True
    detect_acknowledgements: bool = True
    detect_self_citation: bool = False
    detect_file_metadata: bool = True
    detect_pdf_metadata: bool = True
    detect_funding_statements: bool = True
    detect_orcid: bool = True
    extra_forbidden_terms: list[str] = Field(default_factory=list)
    forbidden_metadata_fields: list[str] = Field(
        default_factory=lambda: ["author", "creator", "producer", "title", "subject", "keywords"]
    )


class ToleranceRule(BaseModel):
    font_family: bool = True
    font_size_pt: float = 0.51
    line_spacing: float = 0.01
    indent_pt: float = 2.0
    space_pt: float = 2.0
    min_font_size_pt: Optional[float] = None
    max_font_size_pt: Optional[float] = None
    allowed_font_families: list[str] = Field(default_factory=list)


class TypographyRule(BaseModel):
    title: Optional[TextFormat] = None
    authors: Optional[TextFormat] = None
    abstract: Optional[TextFormat] = None
    headings: Optional[TextFormat] = None
    body: Optional[TextFormat] = None
    tolerance: ToleranceRule = Field(default_factory=ToleranceRule)


class ParagraphRule(BaseModel):
    line_spacing: Optional[float] = None
    indent_first_line_pt: Optional[float] = None
    space_above_pt: Optional[float] = None
    space_below_pt: Optional[float] = None
    require_justified_body: bool = False
    require_uniform_alignment: bool = False
    max_alignment_mismatches: int = 0
    indent_tolerance_pt: float = 2.0
    space_tolerance_pt: float = 2.0
    line_spacing_tolerance: float = 0.01


class RuleSet(BaseModel):
    """A complete, validated configuration for one publisher template."""

    template_id: str = ""
    name: str = "Untitled template"
    description: str = ""
    source_template_filename: Optional[str] = None
    publisher: PublisherDetails = Field(default_factory=PublisherDetails)

    file_type: FileTypeRule = Field(default_factory=FileTypeRule)
    pages: PageRule = Field(default_factory=PageRule)
    sections: SectionRule = Field(default_factory=SectionRule)
    anonymisation: AnonymisationRule = Field(default_factory=AnonymisationRule)
    typography: TypographyRule = Field(default_factory=TypographyRule)
    paragraph: ParagraphRule = Field(default_factory=ParagraphRule)
    decision: DecisionRule = Field(default_factory=DecisionRule)

    def accepted_extension_list(self) -> list[str]:
        return sorted({e.casefold().lstrip(".") for e in self.file_type.accepted_extensions})


class DocumentRule(BaseModel):
    page_size_label: Optional[str] = None
    orientation: Optional[str] = None
    columns: Optional[int] = None
    margins: Optional[Margins] = None


class TemplateRules(BaseModel):
    source_title: str = ""
    document: DocumentRule
    title: Optional[TextFormat] = None
    authors: Optional[TextFormat] = None
    abstract: Optional[TextFormat] = None
    keywords_required: bool = False
    required_sections: list[str] = Field(default_factory=list)
    headings: Optional[TextFormat] = None
    body: Optional[TextFormat] = None


__all__ = [
    "AnonymisationRule",
    "CANONICAL_SECTION_ORDER",
    "DecisionRule",
    "DocumentRule",
    "FileTypeRule",
    "PageRule",
    "ParagraphRule",
    "PublisherDetails",
    "RuleSet",
    "SectionRule",
    "Severity",
    "TemplateRules",
    "ToleranceRule",
    "TypographyRule",
]
