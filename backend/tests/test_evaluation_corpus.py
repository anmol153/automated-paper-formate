"""Regression tests for the evaluation corpus itself.

The evaluation is only meaningful if the fixtures and the engine are both
honest. These tests pin the three properties that make the report trustworthy:

1. the compliant baseline produces no findings, so detection numbers are not
   inflated by a control that is itself broken;
2. every planted flaw is actually detected;
3. the corpus exercises each of the three supported formats.
"""

from __future__ import annotations

import pytest

from app.evaluation.corpus import build_corpus, docx_fixture, evaluation_rules
from app.evaluation.runner import evaluate_fixtures


@pytest.fixture(scope="module")
def report():
    fixtures = build_corpus() + [docx_fixture()]
    return evaluate_fixtures(fixtures)


def test_corpus_covers_all_supported_formats():
    formats = {f.filename.rsplit(".", 1)[-1] for f in build_corpus() + [docx_fixture()]}
    assert {"pdf", "tex", "docx"} <= formats


def test_corpus_contains_an_intentionally_clean_fixture():
    """A control that is not actually clean would make every number meaningless."""
    assert any(not f.expected_flaws for f in build_corpus())


def test_compliant_baseline_produces_no_findings(report):
    outcomes = {o.name: o for o in report.outcomes}
    baseline = outcomes["compliant-baseline"]
    assert baseline.blocking == [], f"unexpected blocking findings: {baseline.blocking}"
    assert baseline.warnings == [], f"unexpected warnings: {baseline.warnings}"
    assert baseline.actual_verdict == "accepted"


def test_every_planted_flaw_is_detected(report):
    assert report.total_missed == 0, (
        "planted flaws the engine failed to detect: "
        f"{report.per_rule_misses or report.per_rule_detection}"
    )


def test_verdicts_match_manual_expectation(report):
    mismatches = [o.name for o in report.outcomes if not o.verdict_match]
    assert not mismatches, f"verdict disagreed with manual review for: {mismatches}"


def test_each_rule_under_test_fires_on_its_own_fixture(report):
    """A rule that never fires anywhere is not evidence of a working rule."""
    unexercised = [
        rid for rid, counts in report.per_rule_detection.items() if counts["detected"] == 0
    ]
    assert not unexercised, f"rules never exercised: {unexercised}"


def test_known_over_reporting_is_limited_to_metadata_title_and_producer(report):
    """Pins the current, deliberate limitations so new noise shows up as a failure.

    A document title and "Microsoft Word 16.0" do not identify an author, so
    flagging them as anonymisation leaks is over-reporting. Recorded here so
    that if it is ever tightened (or loosened further) the report says so.
    """
    assert set(report.per_rule_false_positives) <= {
        "anonymisation.metadata.producer",
        "anonymisation.metadata.title",
    }, f"new over-reporting: {report.per_rule_false_positives}"


def test_unparseable_file_still_reports_a_useful_reason():
    """A rejected file must tell the author what to do, not just that it failed."""
    from app.checks.submission import assess_paper

    paper = assess_paper(
        filename="readme.txt",
        data=b"just some text, not a manuscript",
        rules=evaluation_rules(),
    )
    assert paper.verdict == "rejected"
    assert paper.action_required
    assert "format" in paper.action_required.lower()
