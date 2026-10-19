import pytest

from app.demo.sample_docx import demo_docx
from app.parsing.docx_parser import parse_docx
from app.parsing.errors import DocxParseError
from app.parsing.template_analyzer import analyze_template


@pytest.fixture(scope="module")
def parsed():
    template, paper = demo_docx()
    return parse_docx(template), parse_docx(paper)


def test_document_level_formatting(parsed):
    template, paper = parsed
    assert template.document.page_size.label == "A4"
    assert template.document.orientation == "portrait"
    assert template.document.columns == 2
    assert abs(template.document.margins.left_pt - 54) < 0.1
    assert template.document.margins.top_pt == 72
    assert template.document.title == "Sample Journal Paper Template"
    assert paper.document.page_size.label == "Letter"
    assert paper.document.columns == 1


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
    assert (title.format.font_family or "").lower() == "times new roman"
    assert title.format.font_size_pt == 16
    assert title.format.bold is True
    assert title.format.alignment == "center"


def test_body_formatting(parsed):
    _, paper = parsed
    body_blocks = [b for b in paper.sections if b.type == "body"]
    assert body_blocks
    fonts = {(b.format.font_family or "").lower() for b in body_blocks}
    assert "arial" in fonts
    assert body_blocks[0].format.font_size_pt == 11
    assert body_blocks[0].format.line_spacing == pytest.approx(1.15)


def test_template_rules_capture_expectations(parsed):
    rules = analyze_template(parsed[0])
    assert rules.document.page_size_label == "A4"
    assert rules.document.columns == 2
    assert rules.title.font_size_pt == 16
    assert rules.keywords_required is True
    assert "Methodology" in rules.required_sections


def test_rejects_non_docx_bytes():
    with pytest.raises(DocxParseError):
        parse_docx(b"this is not a docx")
    with pytest.raises(DocxParseError):
        parse_docx(b"")