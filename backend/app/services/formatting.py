"""One parsing/fact-extraction/assessment service shared by both upload paths."""
from app.checks.engine import assess
from app.parsing.fact_extractor import build_facts
from app.parsing.pipeline import normalize_document
from app.security.files import validate_document

# Bump when extraction or rule semantics change; stored with every report.
ENGINE_VERSION = "paper-format-0.4.0-revisions-1"


def evaluate_document(rules, data, filename, author_supplied=None):
    fmt = validate_document(data, filename)
    doc = normalize_document(data, filename)
    facts = build_facts(data, filename, doc, fmt, author_supplied=author_supplied)
    return assess(rules, facts)


def validation_status(assessment):
    if assessment.blocking_reasons:
        return "failed"
    if not any(r.status != "not_applicable" for r in assessment.results):
        return "unable_to_validate"
    if any(r.status in {"failed", "missing"} for r in assessment.results):
        return "passed_with_warnings"
    return "passed"
