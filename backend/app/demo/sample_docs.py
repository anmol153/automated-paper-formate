"""Raw Google Docs API-shaped sample documents used by demo mode and tests."""

from __future__ import annotations


def _run(text: str, *, family=None, size=None, bold=None, italic=None) -> dict:
    style: dict = {}
    if family:
        style["fontFamily"] = family
    if size is not None:
        style["fontSize"] = {"magnitude": size, "unit": "POINT"}
    if bold is not None:
        style["bold"] = bold
    if italic is not None:
        style["italic"] = italic
    return {"textRun": {"content": text, "textStyle": style}}


def _para(
    *runs: dict,
    named_style: str = "NORMAL_TEXT",
    alignment: str | None = None,
    line_spacing: int | None = None,
    space_below: float | None = None,
    space_above: float | None = None,
    indent_first_line: float | None = None,
) -> dict:
    pstyle: dict = {"namedStyleType": named_style}
    if alignment:
        pstyle["alignment"] = alignment
    if line_spacing:
        pstyle["lineSpacing"] = line_spacing
    if space_above is not None:
        pstyle["spaceAbove"] = {"magnitude": space_above, "unit": "PT"}
    if space_below is not None:
        pstyle["spaceBelow"] = {"magnitude": space_below, "unit": "PT"}
    if indent_first_line is not None:
        pstyle["indentFirstLine"] = {"magnitude": indent_first_line, "unit": "PT"}
    elements = list(runs) if runs else [_run("")]
    return {"paragraph": {"paragraphStyle": pstyle, "elements": elements}}


def _section_break(columns: int, spacing_pt: float) -> dict:
    return {
        "sectionBreak": {
            "sectionStyle": {
                "columnProperties": [
                    {"width": {"magnitude": 200, "unit": "PT"}, "spacing": {"magnitude": spacing_pt, "unit": "PT"}}
                ]
                * columns,
                "columnSeparatorStyle": "NONE",
            }
        }
    }


def _doc(title: str, document_style: dict, children: list[dict], columns: int = 1) -> dict:
    return {
        "title": title,
        "documentId": f"demo-{abs(hash(title)) % 10_000_000}",
        "documentStyle": document_style,
        "namedStyles": {
            "styles": [
                {
                    "namedStyle": {
                        "namedStyleType": "NORMAL_TEXT",
                        "textStyle": {"fontFamily": document_style.get("_default_font", "Arial")},
                    }
                }
            ]
        },
        "body": {"content": [*children, _section_break(columns, 18)]},
    }


def template_document() -> dict:
    style = {
        "pageSize": {
            "width": {"magnitude": 595.28, "unit": "PT"},
            "height": {"magnitude": 841.89, "unit": "PT"},
        },
        "marginTop": {"magnitude": 72, "unit": "PT"},
        "marginBottom": {"magnitude": 72, "unit": "PT"},
        "marginLeft": {"magnitude": 54, "unit": "PT"},
        "marginRight": {"magnitude": 54, "unit": "PT"},
        "_default_font": "Times New Roman",
    }
    content = [
        _para(_run("Sample Journal Paper Template", family="Times New Roman", size=16, bold=True),
              alignment="CENTER", space_below=12),
        _para(_run("Jane Doe, John Smith", family="Times New Roman", size=11),
              _run("\nExample University, Example City", family="Times New Roman", size=10, italic=True),
              alignment="CENTER", space_below=18),
        _para(_run("Abstract", family="Times New Roman", size=10, bold=True)),
        _para(
            _run(
                "This template defines the expected formatting for submissions. It specifies a two-column "
                "A4 layout with Times New Roman throughout.",
                family="Times New Roman", size=10,
            ),
            alignment="JUSTIFIED", line_spacing=100, indent_first_line=14,
        ),
        _para(
            _run("Keywords", family="Times New Roman", size=10, bold=True),
            _run("—format checking, templates, compliance", family="Times New Roman", size=10),
        ),
        _para(_run("INTRODUCTION", family="Times New Roman", size=10, bold=True), space_below=6),
        _para(
            _run(
                "Submissions must follow the layout described here. The introduction motivates the work "
                "and summarizes contributions.",
                family="Times New Roman", size=10,
            ),
            alignment="JUSTIFIED", line_spacing=100, indent_first_line=14,
        ),
        _para(_run("METHODOLOGY", family="Times New Roman", size=10, bold=True), space_below=6),
        _para(
            _run(
                "The method section explains the approach, materials, and evaluation setup used in the study.",
                family="Times New Roman", size=10,
            ),
            alignment="JUSTIFIED", line_spacing=100, indent_first_line=14,
        ),
        _para(_run("RESULTS", family="Times New Roman", size=10, bold=True), space_below=6),
        _para(
            _run(
                "The results section reports experimental findings together with tables and figures where "
                "appropriate.",
                family="Times New Roman", size=10,
            ),
            alignment="JUSTIFIED", line_spacing=100, indent_first_line=14,
        ),
        _para(_run("CONCLUSION", family="Times New Roman", size=10, bold=True), space_below=6),
        _para(
            _run(
                "The conclusion restates the contribution and outlines directions for future work in this area.",
                family="Times New Roman", size=10,
            ),
            alignment="JUSTIFIED", line_spacing=100, indent_first_line=14,
        ),
        _para(_run("REFERENCES", family="Times New Roman", size=10, bold=True), space_below=6),
        _para(_run("[1] A. Author, B. Author, Some Paper, Venue 2024.", family="Times New Roman", size=9)),
        _para(_run("[2] C. Author, Another Paper, Venue 2025.", family="Times New Roman", size=9)),
    ]
    return _doc("Sample Journal Paper Template", style, content, columns=2)


def paper_document() -> dict:
    style = {
        "pageSize": {
            "width": {"magnitude": 612, "unit": "PT"},
            "height": {"magnitude": 792, "unit": "PT"},
        },
        "marginTop": {"magnitude": 72, "unit": "PT"},
        "marginBottom": {"magnitude": 72, "unit": "PT"},
        "marginLeft": {"magnitude": 72, "unit": "PT"},
        "marginRight": {"magnitude": 72, "unit": "PT"},
        "_default_font": "Arial",
    }
    content = [
        _para(_run("Deep Learning for Format Compliance Checking", family="Arial", size=14, bold=True),
              alignment="CENTER", space_below=12),
        _para(_run("Alice Lee, Bob Chen", family="Arial", size=12),
              _run("\nState University, Springfield", family="Arial", size=10, italic=True),
              alignment="CENTER", space_below=16),
        _para(_run("ABSTRACT", family="Arial", size=12, bold=True), space_below=6),
        _para(
            _run(
                "We study whether research papers comply with venue formatting requirements automatically "
                "using deterministic parsing of cloud document APIs. Our prototype compares normalized "
                "documents against extracted rules and reports violations.",
                family="Arial", size=11,
            ),
            alignment="START", line_spacing=115,
        ),
        _para(_run("1. Introduction", family="Arial", size=11, bold=True), space_below=6),
        _para(
            _run(
                "Formatting requirements are tedious to verify manually. We introduce a pipeline that "
                "parses documents and compares them against journal templates.",
                family="Arial", size=11,
            ),
            alignment="START", line_spacing=115,
        ),
        _para(
            _run(
                "Prior systems rely on heuristics over PDFs. In contrast, we operate on the structured "
                "document model directly, which preserves typography faithfully.",
                family="Arial", size=11,
            ),
            alignment="START", line_spacing=115,
        ),
        _para(_run("Results", family="Arial", size=11, bold=True), space_below=6),
        _para(
            _run(
                "On a corpus of fifty papers the system reaches high agreement with manual review and "
                "produces actionable per-requirement diagnostics for authors.",
                family="Arial", size=11,
            ),
            alignment="START", line_spacing=115,
        ),
        _para(_run("Conclusion", family="Arial", size=11, bold=True), space_below=6),
        _para(
            _run(
                "Automated compliance checking saves reviewers time and helps authors fix issues early "
                "before submission deadlines arrive.",
                family="Arial", size=11,
            ),
            alignment="START", line_spacing=115,
        ),
        _para(_run("References", family="Arial", size=11, bold=True), space_below=6),
        _para(_run("[1] X. Yang, Format Matters, Journal of Documents, 2024.", family="Arial", size=10)),
    ]
    return _doc("Deep Learning for Format Compliance Checking", style, content)


DEMO_DOCUMENTS = {
    "template": template_document(),
    "paper": paper_document(),
}
