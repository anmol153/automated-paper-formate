from app.models.document import NormalizedDocument
from app.models.rules import TemplateRules
from app.models.report import CheckResult
from app.parsing.structure import aggregate_formats

from .utils import build_check, compare_close, fmt_pt


def compare_paragraph(rules: TemplateRules, paper: NormalizedDocument) -> list[CheckResult]:
    results: list[CheckResult] = []
    rule = rules.body
    if rule is None:
        return results

    body_blocks = paper.body_blocks(exclude_parents={"References"})
    dominant = aggregate_formats([b.format for b in body_blocks]) if body_blocks else None

    if rule.line_spacing is not None:
        actual_spacing = dominant.line_spacing if dominant else None
        results.append(
            build_check(
                "Body Line Spacing",
                "paragraph",
                f"{rule.line_spacing:g}",
                f"{actual_spacing:g}" if actual_spacing is not None else None,
                compare_close(actual_spacing, rule.line_spacing, tolerance=0.01),
            )
        )

    if rule.indent_first_line_pt is not None:
        actual_indent = dominant.indent_first_line_pt if dominant else None
        results.append(
            build_check(
                "Body First-Line Indent",
                "paragraph",
                fmt_pt(rule.indent_first_line_pt),
                fmt_pt(actual_indent) if actual_indent is not None else "Not specified",
                compare_close(actual_indent, rule.indent_first_line_pt, tolerance=2.0),
            )
        )

    if rule.space_below_pt is not None:
        actual_space = dominant.space_below_pt if dominant else None
        results.append(
            build_check(
                "Body Paragraph Spacing",
                "paragraph",
                fmt_pt(rule.space_below_pt),
                fmt_pt(actual_space) if actual_space is not None else "Not specified",
                compare_close(actual_space, rule.space_below_pt, tolerance=2.0),
            )
        )

    return results
