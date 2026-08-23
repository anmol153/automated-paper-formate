from app.models.document import NormalizedDocument
from app.models.rules import DocumentRule
from app.models.report import CheckResult

from .utils import build_check, fmt_pt


def _page_label(doc: NormalizedDocument) -> str:
    page = doc.document.page_size
    return page.label or f"{page.width_pt:g} x {page.height_pt:g} pt"


def _margins_dict(doc: NormalizedDocument) -> dict[str, str]:
    m = doc.document.margins
    return {
        "top": fmt_pt(m.top_pt),
        "bottom": fmt_pt(m.bottom_pt),
        "left": fmt_pt(m.left_pt),
        "right": fmt_pt(m.right_pt),
    }


def compare_document(rule: DocumentRule, paper: NormalizedDocument) -> list[CheckResult]:
    results: list[CheckResult] = []

    if rule.page_size_label:
        expected_label = rule.page_size_label
        actual_label = _page_label(paper)
        std_w, std_h = _dimensions_for_label(expected_label)
        matched = expected_label.lower() == actual_label.lower() or (
            abs(paper.document.page_size.width_pt - std_w) <= 2
            and abs(paper.document.page_size.height_pt - std_h) <= 2
        )
        results.append(build_check("Page Size", "document", expected_label, actual_label, matched))

    if rule.orientation:
        results.append(
            build_check("Orientation", "document", rule.orientation.title(), paper.document.orientation.title(),
                        rule.orientation == paper.document.orientation)
        )

    if rule.columns is not None:
        results.append(
            build_check("Columns", "document", rule.columns, paper.document.columns,
                        rule.columns == paper.document.columns)
        )

    if rule.margins is not None:
        expected = {
            "top": fmt_pt(rule.margins.top_pt),
            "bottom": fmt_pt(rule.margins.bottom_pt),
            "left": fmt_pt(rule.margins.left_pt),
            "right": fmt_pt(rule.margins.right_pt),
        }
        actual = _margins_dict(paper)
        all_match = all(abs(a - b) <= 2 for a, b in zip(
            [rule.margins.top_pt, rule.margins.bottom_pt, rule.margins.left_pt, rule.margins.right_pt],
            [paper.document.margins.top_pt, paper.document.margins.bottom_pt,
             paper.document.margins.left_pt, paper.document.margins.right_pt],
        ))
        results.append(build_check("Margins", "document", expected, actual, all_match))

    return results


_STANDARD_DIMENSIONS = {
    "a5": (419.53, 595.28),
    "a4": (595.28, 841.89),
    "letter": (612.0, 792.0),
    "legal": (612.0, 1008.0),
}


def _dimensions_for_label(label: str) -> tuple[float, float]:
    return _STANDARD_DIMENSIONS.get(label.strip().lower(), (0.0, 0.0))
