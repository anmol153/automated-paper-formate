from app.models.document import NormalizedDocument
from app.models.rules import TemplateRules
from app.models.report import CheckResult
from app.parsing.structure import aggregate_formats

from .utils import build_check, compare_equal, compare_font, compare_size


def _format_checks(label: str, rule_format, paper_format) -> list[CheckResult]:
    results: list[CheckResult] = []
    comparisons: list[tuple[str, object, object, bool | None]] = [
        (
            f"{label} Font",
            rule_format.font_family,
            paper_format.font_family,
            compare_font(rule_format.font_family, paper_format.font_family),
        ),
        (
            f"{label} Font Size",
            rule_format.font_size_pt,
            paper_format.font_size_pt,
            compare_size(rule_format.font_size_pt, paper_format.font_size_pt),
        ),
    ]
    if rule_format.bold is not None:
        comparisons.append(
            (f"{label} Bold", rule_format.bold, paper_format.bold, compare_equal(rule_format.bold, paper_format.bold))
        )
    if rule_format.alignment is not None:
        comparisons.append(
            (
                f"{label} Alignment",
                rule_format.alignment.title() if rule_format.alignment else None,
                paper_format.alignment.title() if paper_format.alignment else None,
                compare_equal(rule_format.alignment, paper_format.alignment),
            )
        )
    for name, expected, actual, matched in comparisons:
        results.append(build_check(name, "typography", expected, actual, matched))
    return results


def _missing_checks(label: str, category: str, rule_format) -> list[CheckResult]:
    return [build_check(f"{label} Font", category, rule_format.font_family, None, None),
            build_check(f"{label} Font Size", category, rule_format.font_size_pt, None, None)]


def compare_typography(rules: TemplateRules, paper: NormalizedDocument) -> list[CheckResult]:
    results: list[CheckResult] = []

    title_block = paper.find("title")
    if rules.title is not None:
        if title_block:
            results.extend(_format_checks("Title", rules.title, title_block.format))
        else:
            results.extend(_missing_checks("Title", "typography", rules.title))

    abstract_block = paper.find("abstract")
    if rules.abstract is not None:
        if abstract_block:
            results.extend(_format_checks("Abstract", rules.abstract, abstract_block.format))
        else:
            results.append(
                build_check("Abstract Font Size", "typography", rules.abstract.font_size_pt, None, None)
            )

    body_blocks = paper.body_blocks(exclude_parents={"References"})
    if rules.body is not None:
        dominant_body = aggregate_formats([b.format for b in body_blocks]) if body_blocks else None
        if dominant_body:
            results.extend(_format_checks("Body", rules.body, dominant_body))
        else:
            results.extend(_missing_checks("Body", "typography", rules.body))

    heading_blocks = paper.headings()
    if rules.headings is not None:
        dominant_heading = aggregate_formats([b.format for b in heading_blocks]) if heading_blocks else None
        if dominant_heading:
            results.extend(_format_checks("Heading", rules.headings, dominant_heading))
        else:
            results.extend(_missing_checks("Heading", "typography", rules.headings))

    return results
