from typing import Optional

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
