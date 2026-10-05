"""Infer a ``RuleSet`` from a publisher template file.

This is the "import" half of the manager workflow: the conference manager
uploads their real template, the measurable formatting properties are read off
it, and the result is handed to the rule editor pre-filled. Anything that
cannot be measured from a document (a page limit, a minimum reference count, a
double-blind policy) stays unset for the manager to decide — inference never
invents a policy.
"""

from __future__ import annotations

import re

from app.models.document import NormalizedDocument, TextFormat
from app.models.rules import (
    AnonymisationRule,
    FileTypeRule,
    PageRule,
    ParagraphRule,
    PublisherDetails,
    RuleSet,
    SectionRule,
    ToleranceRule,
    TypographyRule,
)
from app.parsing.structure import aggregate_formats
from app.parsing.template_analyzer import analyze_template
from app.parsing.venue_families import (
    LNCS_PRESET,
    FamilyMatch,
    apply_preset,
    detect_family,
)

_KNOWN_FAMILIES = [
    FamilyMatch(
        key="springer-lncs",
        label="Springer LNCS (visible authors)",
        confidence=0.0,
        preset=LNCS_PRESET,
        source=LNCS_PRESET["source"],
    )
]

_EXCLUDED_FROM_BODY = {
    "References",
    "Acknowledgments",
    "Appendix",
    "Acknowledgment",
    "Acknowledgements",
    "Disclosure Of Interests",
    "Conflict Of Interest",
    "Competing Interests",
    "Ethical Standards",
    "Ethics Statement",
    "Author Contributions",
}

# A caption is not body text. Springer styles set captions smaller than the
# body, and a template is mostly captions and back matter, so leaving them in
# pulls the inferred body size down.
_CAPTION_PATTERN = re.compile(
    r"^\s*(table|tab\.|fig\.|figure|algorithm|listing|scheme|chart)\s*\.?\s*\d+",
    re.IGNORECASE,
)

# LNCS back matter is a run-in bold lead ("Acknowledgments. A third level
# heading...") rather than a heading, so it has to be matched on the text.
_BACKMATTER_LEAD_PATTERN = re.compile(
    r"^\s*(acknowledg(e)?ments?|disclosure of interests?|competing interests?|"
    r"conflict of interests?|ethical standards?|author contributions?)\s*[.:]",
    re.IGNORECASE,
)


def _is_caption_or_backmatter(text: str) -> bool:
    return bool(_CAPTION_PATTERN.match(text) or _BACKMATTER_LEAD_PATTERN.match(text))


def _body_format(doc: NormalizedDocument) -> TextFormat | None:
    """The dominant body format, weighted by how much text each block carries.

    Weighting matters: a proceedings template is full of short captions,
    references and footnotes set smaller than the body, and counting blocks
    equally lets those win and mis-state the body size.
    """
    blocks = [
        b
        for b in doc.body_blocks(exclude_parents=_EXCLUDED_FROM_BODY)
        if b.format and not _is_caption_or_backmatter(b.text)
    ]
    if not blocks:
        return None
    weights = [max(len(b.text.strip()), 1) for b in blocks]
    return aggregate_formats([b.format for b in blocks], weights)


def _heading_format(doc: NormalizedDocument) -> TextFormat | None:
    blocks = doc.headings()
    return aggregate_formats([b.format for b in blocks]) if blocks else None


def _infer_anonymisation(doc: NormalizedDocument) -> AnonymisationRule:
    """Guess whether the template itself is blinded.

    A template carrying author names, emails or affiliations is a non-blinded
    exemplar, so the manager most likely wants visible authors. This only sets a
    starting point; the rule editor still shows it for confirmation.
    """
    text = doc.full_text()
    leaks_identity = (
        doc.find("authors") is not None
        or "@" in text
        or any(
            hint in text.casefold()
            for hint in ("university", "institute", "department", "laborator")
        )
    )
    return AnonymisationRule(
        required=not leaks_identity,
        allow_author_block=leaks_identity,
        allow_anonymous_placeholder=not leaks_identity,
        detect_self_citation=not leaks_identity,
    )


def infer_ruleset_from_template(
    doc: NormalizedDocument,
    template_name: str,
    description: str = "",
) -> RuleSet:
    """Build a pre-filled RuleSet from a parsed template document.

    Measured properties (page size, margins, columns, typography) always come
    from the file. If the template is recognised as a known venue family, the
    family's *published* policy -- page ceiling, abstract budget, keyword policy
    -- is filled in as well, because none of that is recorded in a template.
    """
    analysed = analyze_template(doc)

    pages = PageRule(
        page_size_label=doc.document.page_size.label,
        orientation=doc.document.orientation,
        columns=doc.document.columns,
        margins=doc.document.margins,
    )

    body = _body_format(doc)
    paragraph = ParagraphRule(
        line_spacing=body.line_spacing if body else None,
        indent_first_line_pt=body.indent_first_line_pt if body else None,
        space_above_pt=body.space_above_pt if body else None,
        space_below_pt=body.space_below_pt if body else None,
    )

    typography = TypographyRule(
        title=analysed.title,
        authors=analysed.authors,
        abstract=analysed.abstract,
        headings=_heading_format(doc),
        body=body,
        tolerance=ToleranceRule(
            allowed_font_families=[body.font_family] if body and body.font_family else [],
            min_font_size_pt=(body.font_size_pt - 0.5) if body and body.font_size_pt else None,
            max_font_size_pt=(body.font_size_pt + 0.5) if body and body.font_size_pt else None,
        ),
    )

    sections = SectionRule(
        required_sections=[name for name in analysed.required_sections if name != "References"],
        abstract_required=doc.find("abstract") is not None,
        keywords_required=analysed.keywords_required,
    )

    file_type = FileTypeRule(
        accepted_extensions=["pdf"],
        allow_source_upload=True,
    )

    publisher = PublisherDetails(
        conference_name=doc.document.title or template_name,
    )

    family = detect_family(doc)
    rules = RuleSet(
        name=template_name.rsplit(".", 1)[0] if template_name else "Imported template",
        description=description or f"Rules imported from '{template_name}'.",
        source_template_filename=template_name,
        publisher=publisher,
        file_type=file_type,
        pages=pages,
        sections=sections,
        anonymisation=_infer_anonymisation(doc),
        typography=typography,
        paragraph=paragraph,
    )

    if family is not None:
        apply_preset(rules, family)
        rules.description = (
            f"{rules.description} Recognised as {family.label} "
            f"(confidence {family.confidence:.0%}); policy defaults from {family.source}. "
            "Confirm the page limit against the current call for papers."
        )

    return rules


def rule_schema() -> dict:
    """Machine-readable description of every configurable field.

    The rule editor renders itself from this instead of hard-coding field lists,
    so adding a rule field in Python is enough to expose it in the UI.
    """
    return {
        "severities": ["blocking", "warning", "advisory"],
        "statuses": ["passed", "failed", "missing", "not_applicable"],
        "groups": [
            {
                "key": "file_type",
                "label": "Accepted files",
                "fields": [
                    {"path": "file_type.accepted_extensions", "type": "list[str]",
                     "help": "Extensions authors may upload, e.g. pdf, tex, docx."},
                    {"path": "file_type.max_file_size_mb", "type": "number",
                     "help": "Maximum upload size in megabytes."},
                    {"path": "file_type.allow_source_upload", "type": "bool",
                     "help": "Allow LaTeX/Word sources in addition to PDF."},
                    {"path": "file_type.reject_if_extension_not_accepted", "type": "bool",
                     "help": "Reject (true) or warn (false) on an unaccepted extension."},
                    {"path": "file_type.require_source_when_pdf_given", "type": "bool",
                     "help": "Also require the LaTeX source alongside the PDF."},
                ],
            },
            {
                "key": "pages",
                "label": "Page limit and layout",
                "fields": [
                    {"path": "pages.max_pages", "type": "number",
                     "help": "Hard page ceiling. Leave blank for no limit."},
                    {"path": "pages.min_pages", "type": "number", "help": "Minimum pages."},
                    {"path": "pages.estimate_tolerance_pages", "type": "number",
                     "help": "Slack applied when the page count had to be estimated."},
                    {"path": "pages.count_references_toward_limit", "type": "bool",
                     "help": "Whether references count against the limit."},
                    {"path": "pages.page_size_label", "type": "select",
                     "options": ["A4", "A5", "Letter", "Legal", "Tabloid", "Executive"]},
                    {"path": "pages.orientation", "type": "select",
                     "options": ["portrait", "landscape"]},
                    {"path": "pages.columns", "type": "number", "help": "1 or 2."},
                    {"path": "pages.margin_tolerance_pt", "type": "number",
                     "help": "Permitted margin deviation in points."},
                ],
            },
            {
                "key": "sections",
                "label": "Required sections",
                "fields": [
                    {"path": "sections.required_sections", "type": "list[str]",
                     "options": ["Abstract", "Introduction", "Related Work", "Methodology",
                                 "Results", "Conclusion", "References", "Acknowledgments",
                                 "Appendix", "Limitations", "Ethics Statement"],
                     "help": "Synonyms such as 'Background' or 'Evaluation' are accepted."},
                    {"path": "sections.forbid_sections", "type": "list[str]"},
                    {"path": "sections.abstract_required", "type": "bool"},
                    {"path": "sections.abstract_max_words", "type": "number"},
                    {"path": "sections.keywords_required", "type": "bool"},
                    {"path": "sections.min_reference_entries", "type": "number"},
                    {"path": "sections.require_canonical_heading_names", "type": "bool"},
                ],
            },
            {
                "key": "anonymisation",
                "label": "Anonymisation (double-blind)",
                "fields": [
                    {"path": "anonymisation.required", "type": "bool",
                     "help": "Turn on all identity checks below."},
                    {"path": "anonymisation.allow_author_block", "type": "bool"},
                    {"path": "anonymisation.detect_emails", "type": "bool"},
                    {"path": "anonymisation.detect_affiliations", "type": "bool"},
                    {"path": "anonymisation.detect_acknowledgements", "type": "bool"},
                    {"path": "anonymisation.detect_funding_statements", "type": "bool"},
                    {"path": "anonymisation.detect_orcid", "type": "bool"},
                    {"path": "anonymisation.detect_self_citation", "type": "bool"},
                    {"path": "anonymisation.extra_forbidden_terms", "type": "list[str]",
                     "help": "Extra identifying strings, e.g. a funder name or project number."},
                ],
            },
            {
                "key": "typography",
                "label": "Typography",
                "fields": [
                    {"path": "typography.body.font_family", "type": "text"},
                    {"path": "typography.body.font_size_pt", "type": "number"},
                    {"path": "typography.title.font_family", "type": "text"},
                    {"path": "typography.title.font_size_pt", "type": "number"},
                    {"path": "typography.title.bold", "type": "bool"},
                    {"path": "typography.heading.font_family", "type": "text"},
                    {"path": "typography.heading.font_size_pt", "type": "number"},
                    {"path": "typography.heading.bold", "type": "bool"},
                    {"path": "typography.abstract.font_size_pt", "type": "number"},
                    {"path": "typography.tolerance.allowed_font_families", "type": "list[str]",
                     "help": "When set, any of these fonts is accepted instead of a single family."},
                    {"path": "typography.tolerance.min_font_size_pt", "type": "number"},
                    {"path": "typography.tolerance.max_font_size_pt", "type": "number"},
                    {"path": "typography.tolerance.font_size_pt", "type": "number",
                     "help": "Permitted font-size deviation in points."},
                ],
            },
            {
                "key": "paragraph",
                "label": "Paragraph spacing",
                "fields": [
                    {"path": "paragraph.line_spacing", "type": "number",
                     "help": "Multiple of single spacing, e.g. 1.15."},
                    {"path": "paragraph.first_line_indent_pt", "type": "number"},
                    {"path": "paragraph.space_above_pt", "type": "number"},
                    {"path": "paragraph.space_below_pt", "type": "number"},
                    {"path": "paragraph.require_justified_body", "type": "bool"},
                    {"path": "paragraph.require_uniform_alignment", "type": "bool"},
                ],
            },
            {
                "key": "decision",
                "label": "Decision policy",
                "fields": [
                    {"path": "decision.reject_if_any_blocking", "type": "bool",
                     "help": "Reject the submission if any blocking rule fails."},
                    {"path": "decision.reject_if_any_warning", "type": "bool",
                     "help": "Treat warnings as fatal."},
                    {"path": "decision.min_score_to_accept", "type": "number",
                     "help": "Overall-score floor, 0-100. Blank disables it."},
                ],
            },
            {
                "key": "publisher",
                "label": "Publisher details (shown to authors)",
                "fields": [
                    {"path": "publisher.publisher_name", "type": "text"},
                    {"path": "publisher.conference_name", "type": "text"},
                    {"path": "publisher.contact_email", "type": "text"},
                    {"path": "publisher.support_url", "type": "text"},
                    {"path": "publisher.deadline", "type": "text"},
                    {"path": "publisher.notes_for_authors", "type": "textarea"},
                ],
            },
        ],
        "templates": [
            {
                "name": "IEEE two-column (anonymous)",
                "rules": {
                    "file_type": {"accepted_extensions": ["pdf"], "allow_source_upload": True},
                    "pages": {"max_pages": 8, "page_size_label": "Letter", "orientation": "portrait",
                              "columns": 2},
                    "sections": {
                        "required_sections": ["Abstract", "Introduction", "Conclusion"],
                        "keywords_required": True,
                        "min_reference_entries": 5,
                    },
                    "anonymisation": {"required": True, "detect_self_citation": True},
                    "typography": {
                        "body": {"font_family": "Times New Roman", "font_size_pt": 10},
                        "title": {"font_size_pt": 24},
                        "headings": {"font_size_pt": 10, "bold": True},
                    },
                    "paragraph": {"line_spacing": 1.0},
                },
            },
            {
                "name": "ACM single-column (anonymous)",
                "rules": {
                    "file_type": {"accepted_extensions": ["pdf"]},
                    "pages": {"max_pages": 9, "page_size_label": "Letter", "columns": 2},
                    "sections": {
                        "required_sections": ["Abstract", "Introduction", "Conclusion"],
                        "abstract_max_words": 150,
                        "keywords_required": True,
                    },
                    "anonymisation": {"required": True},
                    "typography": {
                        "body": {"font_family": "Libertine", "font_size_pt": 9},
                        "headings": {"font_size_pt": 9, "bold": True},
                    },
                    "paragraph": {"line_spacing": 1.0},
                },
            },
            {
                "name": "Springer LNCS (visible authors)",
                "note": "Page ceiling and abstract budget come from the Springer LNCS "
                        "author guidelines, not from any template file. Confirm both "
                        "against the current volume's call for papers.",
                "rules": {
                    "file_type": {"accepted_extensions": ["pdf", "tex", "docx"],
                                  "allow_source_upload": True},
                    "pages": {"max_pages": 9, "page_size_label": "A4", "orientation": "portrait",
                              "columns": 1,
                              "margins": {"top_pt": 147.4, "bottom_pt": 147.4,
                                          "left_pt": 124.7, "right_pt": 124.7}},
                    "sections": {
                        "required_sections": ["Abstract", "Introduction", "Conclusion", "References"],
                        "abstract_required": True,
                        "abstract_max_words": 250,
                        "keywords_required": True,
                    },
                    "anonymisation": {"required": False, "allow_author_block": True},
                    "typography": {
                        "body": {"font_family": "Times New Roman", "font_size_pt": 10},
                        "title": {"font_size_pt": 14, "bold": True},
                        "headings": {"font_size_pt": 10, "bold": True},
                    },
                    "paragraph": {"line_spacing": 1.0},
                },
            },
        ],
        "families": [
            {
                "key": match.key,
                "label": match.label,
                "source": match.source,
            }
            for match in _KNOWN_FAMILIES
        ],
    }


__all__ = ["infer_ruleset_from_template", "rule_schema"]
