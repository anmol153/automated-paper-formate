from app.demo.sample_docs import DEMO_DOCUMENTS
from app.parsing.normalizer import parse_google_doc
from app.parsing.template_analyzer import analyze_template


def test_normalizes_document_level_formatting():
    doc = parse_google_doc(DEMO_DOCUMENTS["template"])
    assert doc.document.page_size.label == "A4"
    assert abs(doc.document.page_size.width_pt - 595.28) < 0.1
    assert doc.document.margins.top_pt == 72
    assert doc.document.columns == 2
    assert doc.document.orientation == "portrait"


def test_detects_structure_in_template():
    doc = parse_google_doc(DEMO_DOCUMENTS["template"])
    assert doc.find("title") is not None
    assert doc.find("authors") is not None
    assert doc.find("abstract") is not None
    assert doc.find("keywords") is not None
    heading_names = {h.name for h in doc.headings()}
    assert {"Introduction", "Methodology", "Results", "Conclusion", "References"} <= heading_names


def test_extracts_title_formatting():
    doc = parse_google_doc(DEMO_DOCUMENTS["template"])
    title = doc.find("title")
    assert title.format.font_family == "Times New Roman"
    assert title.format.font_size_pt == 16
    assert title.format.bold is True
    assert title.format.alignment == "center"


def test_template_rules_capture_expectations():
    rules = analyze_template(parse_google_doc(DEMO_DOCUMENTS["template"]))
    assert rules.document.page_size_label == "A4"
    assert rules.document.columns == 2
    assert rules.title.font_size_pt == 16
    assert rules.body.alignment == "justified"
    assert rules.keywords_required is True
    assert "Methodology" in rules.required_sections
    assert "Keywords" not in rules.required_sections


def test_paper_missing_keywords_and_methodology():
    doc = parse_google_doc(DEMO_DOCUMENTS["paper"])
    assert doc.find("keywords") is None
    heading_names = {h.name for h in doc.headings()}
    assert "Methodology" not in heading_names
