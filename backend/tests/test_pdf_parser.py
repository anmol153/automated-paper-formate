import pytest

from app.demo.sample_pdfs import demo_documents
from app.parsing.pdf_parser import PdfParseError, clean_font_name, parse_pdf


@pytest.fixture(scope="module")
def parsed():
    template_bytes, paper_bytes = demo_documents()
    return parse_pdf(template_bytes), parse_pdf(paper_bytes)


def test_clean_font_name():
    assert clean_font_name("ABCDEF+TimesNewRomanPSMT") == "Times New Roman"
    assert clean_font_name("Arial-BoldMT") == "Arial"
    assert clean_font_name("Helvetica") == "Helvetica"
    assert clean_font_name("Times-Roman") == "Times Roman"
    assert clean_font_name(None) is None


def test_document_level_formatting(parsed):
    template, paper = parsed
    assert template.document.page_size.label == "A4"
    assert template.document.orientation == "portrait"
    assert template.document.columns == 2
    assert paper.document.page_size.label == "Letter"
    assert paper.document.columns == 1
    assert template.document.margins.left_pt == pytest.approx(54, abs=6)
    assert template.document.margins.top_pt == pytest.approx(64, abs=8)


def test_structure_detection_in_pdfs(parsed):
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


def test_title_formatting_from_pdf(parsed):
    template, _ = parsed
    title = template.find("title")
    assert "times" in (title.format.font_family or "").lower()
    assert title.format.font_size_pt == 16.0
    assert title.format.bold is True
    assert title.format.alignment == "center"


def test_body_font_detection(parsed):
    _, paper = parsed
    body_blocks = [b for b in paper.sections if b.type == "body"]
    assert body_blocks
    fonts = {(b.format.font_family or "").lower() for b in body_blocks}
    assert any("helvetica" in f for f in fonts)


def test_rejects_non_pdf_bytes():
    with pytest.raises(PdfParseError):
        parse_pdf(b"this is definitely not a pdf")


def test_rejects_empty_data():
    with pytest.raises(PdfParseError):
        parse_pdf(b"")
