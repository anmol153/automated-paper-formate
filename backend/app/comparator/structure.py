from app.models.document import NormalizedDocument
from app.models.rules import TemplateRules
from app.models.report import CheckResult


def _presence_check(name: str, found: bool) -> CheckResult:
    return CheckResult(
        name=name,
        category="structure",
        status="passed" if found else "missing",
        expected="Present",
        actual="Present" if found else "Missing",
    )


def _section_found(name: str, paper: NormalizedDocument) -> bool:
    if name == "Abstract":
        return paper.find("abstract") is not None
    return any(h.name == name for h in paper.headings())


def compare_structure(rules: TemplateRules, paper: NormalizedDocument) -> list[CheckResult]:
    results: list[CheckResult] = []

    results.append(_presence_check("Title Present", paper.find("title") is not None))

    if rules.authors is not None:
        results.append(_presence_check("Authors Present", paper.find("authors") is not None))

    if rules.keywords_required:
        results.append(_presence_check("Keywords Present", paper.find("keywords") is not None))

    for name in rules.required_sections:
        results.append(_presence_check(f"{name} Section", _section_found(name, paper)))

    return results
