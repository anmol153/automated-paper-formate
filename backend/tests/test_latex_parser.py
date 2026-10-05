import pytest

from app.demo.sample_latex import latex_documents
from app.parsing.errors import LatexParseError
from app.parsing.latex_parser import parse_latex
from app.parsing.template_analyzer import analyze_template


@pytest.fixture(scope="module")
def parsed():
    template, paper = latex_documents()
    return parse_latex(template), parse_latex(paper)


def test_document_level_formatting(parsed):
    template, paper = parsed
    assert template.document.page_size.label == "A4"
    assert template.document.orientation == "portrait"
    assert template.document.columns == 2
    assert abs(template.document.margins.left_pt - 54) < 0.1
    assert paper.document.page_size.label == "Letter"
    assert paper.document.columns == 1
    assert paper.document.margins.top_pt == 72


def test_structure_detection(parsed):
    template, paper = parsed
    assert template.find("title") is not None
    assert template.find("authors") is not None
    assert template.find("abstract") is not None
    assert template.find("keywords") is not None

    heading_names = {h.name for h in template.headings()}
    assert {"Introduction", "Methodology", "Results", "Conclusion", "References"} <= heading_names

    assert paper.find("keywords") is None
    paper_headings = {h.name for h in paper.headings()}
    assert "Methodology" not in paper_headings


def test_title_formatting(parsed):
    template, _ = parsed
    title = template.find("title")
    assert (title.format.font_family or "").lower().startswith("times")
    assert title.format.bold is True
    assert title.format.alignment == "center"


def test_body_font_matches_documentclass_package(parsed):
    template, paper = parsed
    template_fonts = {b.format.font_family for b in template.sections if b.type == "body"}
    assert any("times" in (f or "").lower() for f in template_fonts)
    paper_fonts = {b.format.font_family for b in paper.sections if b.type == "body"}
    assert any("helvetica" in (f or "").lower() for f in paper_fonts)


def test_template_rules_capture_expectations(parsed):
    rules = analyze_template(parsed[0])
    assert rules.document.page_size_label == "A4"
    assert rules.document.columns == 2
    assert rules.title.alignment == "center"
    assert rules.keywords_required is True
    assert "Methodology" in rules.required_sections


def test_rejects_empty_source():
    with pytest.raises(LatexParseError):
        parse_latex("")
    with pytest.raises(LatexParseError):
        parse_latex(b"% just a comment\n")


def test_accepts_bytes_utf8():
    template, _ = latex_documents()
    parsed = parse_latex(template.encode("utf-8"))
    assert parsed.document.page_size.label == "A4"