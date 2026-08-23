from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Alignment = Literal["left", "center", "right", "justified"]
Orientation = Literal["portrait", "landscape"]


class Quantity(BaseModel):
    magnitude: float
    unit: str = "PT"


class PageSize(BaseModel):
    width_pt: float
    height_pt: float
    label: Optional[str] = None


class Margins(BaseModel):
    top_pt: float
    bottom_pt: float
    left_pt: float
    right_pt: float


class DocumentInfo(BaseModel):
    page_size: PageSize
    margins: Margins
    orientation: Orientation = "portrait"
    columns: int = 1
    column_spacing_pt: Optional[float] = None
    title: str = ""


class TextFormat(BaseModel):
    font_family: Optional[str] = None
    font_size_pt: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    alignment: Optional[Alignment] = None
    line_spacing: Optional[float] = Field(None, description="Multiple of single spacing, e.g. 1.15")
    space_above_pt: Optional[float] = None
    space_below_pt: Optional[float] = None
    indent_first_line_pt: Optional[float] = None
    indent_start_pt: Optional[float] = None
    indent_end_pt: Optional[float] = None

    def non_null_attributes(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


SectionType = Literal["title", "authors", "abstract", "keywords", "heading", "body", "references"]


class SectionBlock(BaseModel):
    type: SectionType
    name: Optional[str] = None
    text: str = ""
    format: TextFormat = TextFormat()


class NormalizedDocument(BaseModel):
    document: DocumentInfo
    sections: list[SectionBlock] = Field(default_factory=list)

    def find(self, section_type: SectionType) -> Optional[SectionBlock]:
        for block in self.sections:
            if block.type == section_type:
                return block
        return None

    def headings(self) -> list["SectionBlock"]:
        return [b for b in self.sections if b.type == "heading"]

    def body_blocks(self, exclude_parents: set[str] | None = None) -> list["SectionBlock"]:
        excluded = exclude_parents or set()
        return [
            b
            for b in self.sections
            if b.type == "body" and (b.name is None or b.name not in excluded)
        ]
