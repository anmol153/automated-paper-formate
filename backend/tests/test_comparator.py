from app.comparator.comparator import run_comparison
from app.comparator.utils import build_check, compare_font, compare_size
from app.demo.sample_docs import DEMO_DOCUMENTS
from app.models.document import Margins, NormalizedDocument, PageSize
from app.models.report import ComplianceReport
from app.models.rules import DocumentRule, TemplateRules
from app.parsing.normalizer import parse_google_doc
from app.parsing.template_analyzer import analyze_template


def test_font_comparison_is_case_insensitive():
    assert compare_font("Times New Roman", "times new roman") is True
    assert compare_font("Times New Roman", "Arial") is False
    assert compare_font(None, "Arial") is None


def test_size_comparison_tolerance():
    assert compare_size(10.0, 10.0) is True
    assert compare_size(10.0, 11.0) is False
    assert compare_size(None, 11.0) is None


def test_build_check_statuses():
    assert build_check("X", "typography", 1, 1, True).status == "passed"
    assert build_check("X", "typography", 1, 2, False).status == "failed"
    assert build_check("X", "typography", 1, None, None).status == "missing"


def test_demo_report_counts_and_score():
    template = analyze_template(parse_google_doc(DEMO_DOCUMENTS["template"]))
    paper = parse_google_doc(DEMO_DOCUMENTS["paper"])
    report = run_comparison(template, paper)

    total = report.passed + report.failed + report.missing
    assert total == len(report.results)
    assert report.score == round(100 * report.passed / total)
    assert report.failed > 0 and report.passed > 0

    statuses = {r.status for r in report.results}
    assert statuses <= {"passed", "failed", "missing"}

    categories = {r.category for r in report.results}
    assert categories == {"document", "typography", "paragraph", "structure"}


def test_missing_sections_reported():
    template = analyze_template(parse_google_doc(DEMO_DOCUMENTS["template"]))
    paper = parse_google_doc(DEMO_DOCUMENTS["paper"])
    report = run_comparison(template, paper)

    missing_names = {r.name for r in report.results if r.status == "missing"}
    assert any("Keywords" in n for n in missing_names)
    assert any("Methodology" in n for n in missing_names)


def _doc_with(page_size: PageSize, columns: int) -> NormalizedDocument:
    return NormalizedDocument(
        document={
            "page_size": page_size.model_dump(),
            "margins": {"top_pt": 72, "bottom_pt": 72, "left_pt": 54, "right_pt": 54},
            "columns": columns,
            "orientation": "portrait",
        },
        sections=[],
    )


def test_document_checks_match_and_mismatch():
    from app.comparator.document import compare_document

    rule = DocumentRule(
        page_size_label="A4",
        orientation="portrait",
        columns=2,
        margins=Margins(top_pt=72, bottom_pt=72, left_pt=54, right_pt=54),
    )
    same = _doc_with(PageSize(width_pt=595.28, height_pt=841.89), 2)
    results = {r.name: r for r in compare_document(rule, same)}
    assert all(r.status == "passed" for r in results.values())

    other = _doc_with(PageSize(width_pt=612, height_pt=792, label="Letter"), 1)
    results = {r.name: r for r in compare_document(rule, other)}
    assert results["Page Size"].status == "failed"
    assert results["Columns"].status == "failed"
    assert results["Orientation"].status == "passed"


def test_empty_results_score_zero():
    report = ComplianceReport.build([])
    assert report.score == 0
    assert report.passed == 0 and report.failed == 0 and report.missing == 0
