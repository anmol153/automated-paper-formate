from app.models.document import NormalizedDocument
from app.models.rules import CANONICAL_SECTION_ORDER, DocumentRule, TemplateRules
from app.parsing.structure import aggregate_formats

_EXCLUDED_FROM_BODY = {"References", "Acknowledgments", "Appendix"}


def analyze_template(doc: NormalizedDocument) -> TemplateRules:
    title_block = doc.find("title")
    authors_block = doc.find("authors")
    abstract_block = doc.find("abstract")

    heading_blocks = doc.headings()
    headings_format = aggregate_formats([b.format for b in heading_blocks]) if heading_blocks else None

    body_blocks = doc.body_blocks(exclude_parents=_EXCLUDED_FROM_BODY)
    body_format = aggregate_formats([b.format for b in body_blocks]) if body_blocks else None

    heading_names = {b.name for b in heading_blocks}
    required_sections = [
        name
        for name in CANONICAL_SECTION_ORDER
        if name != "Keywords" and name in heading_names
    ]

    return TemplateRules(
        source_title=doc.document.title,
        document=DocumentRule(
            page_size_label=doc.document.page_size.label,
            orientation=doc.document.orientation,
            columns=doc.document.columns,
            margins=doc.document.margins,
        ),
        title=title_block.format if title_block else None,
        authors=authors_block.format if authors_block else None,
        abstract=abstract_block.format if abstract_block else None,
        keywords_required=bool(doc.find("keywords")),
        required_sections=required_sections,
        headings=headings_format,
        body=body_format,
    )
