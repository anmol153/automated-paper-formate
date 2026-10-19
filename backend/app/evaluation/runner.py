"""Automated evaluation of the compliance engine against a labelled corpus.

The point of this module is to answer one question honestly: when a conference
manager would have rejected a paper by hand, does the system reach the same
conclusion for the same reasons?

Method
------
1. Run every fixture in the corpus through the same code path the API uses
   (``assess_paper``), so the evaluation cannot drift from production.
2. For each fixture, compare the *rule ids* the system failed against the rule
   ids the fixture was deliberately built to violate.
3. Report three independent numbers:
     - detection rate  (flaws we planted that we caught)
     - false negatives  (planted flaws the system missed, by rule)
     - false positives  (failures on the clean baseline, and on rules we did
                         not plant)
4. Compare the overall accept/reject verdict with the ground-truth verdict,
   because a submission is rejected or not regardless of which rule fired.

Run with ``python -m app.evaluation.runner``.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from app.checks.submission import assess_paper
from app.evaluation.corpus import Fixture, build_corpus, docx_fixture, evaluation_rules


@dataclass
class FixtureOutcome:
    name: str
    filename: str
    description: str
    expected_verdict: str
    actual_verdict: str
    verdict_match: bool
    expected_flaw_ids: list[str]
    detected_flaw_ids: list[str]
    missed_flaw_ids: list[str]
    unexpected_flaw_ids: list[str]
    blocking: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    not_applicable: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    total_fixtures: int
    verdict_agreement: float
    detection_rate: float
    total_planted: int
    total_detected: int
    total_missed: int
    clean_baseline_clean: bool
    per_rule_detection: dict[str, dict[str, int]]
    per_rule_misses: dict[str, int]
    per_rule_false_positives: dict[str, int]
    outcomes: list[FixtureOutcome]


# --------------------------------------------------------------------------- #
# running
# --------------------------------------------------------------------------- #


def _feed(fixture: Fixture):
    """Push a fixture through the real ingest path and return its assessment.

    Using the production entry point rather than a private helper is deliberate:
    an evaluation that reimplements the pipeline tests the wrong thing.
    """
    return assess_paper(
        filename=fixture.filename,
        data=fixture.data,
        rules=evaluation_rules(),
    )


def evaluate_fixtures(fixtures: Iterable[Fixture]) -> EvaluationReport:
    fixtures = list(fixtures)
    outcomes: list[FixtureOutcome] = []
    planted_counter: Counter[str] = Counter()
    detected_counter: Counter[str] = Counter()

    for fixture in fixtures:
        paper = _feed(fixture)

        # "missing" counts as a detection: an absent required section is a
        # violation, and the engine deliberately distinguishes it from a
        # measured-and-wrong section rather than calling both "failed".
        failed = {
            r.rule for r in paper.results if r.status in ("failed", "missing")
        }
        blocking = sorted(
            {r.rule for r in paper.results if r.severity == "blocking" and r.status in ("failed", "missing")}
        )
        warnings = sorted(
            {r.rule for r in paper.results if r.severity == "warning" and r.status in ("failed", "missing")}
        )
        na = sorted({r.rule for r in paper.results if r.status == "not_applicable"})

        expected = {f.rule_id for f in fixture.expected_flaws}
        detected = expected & failed
        missed = expected - failed
        unexpected = failed - expected

        for rid in expected:
            planted_counter[rid] += 1
        for rid in detected:
            detected_counter[rid] += 1

        outcomes.append(
            FixtureOutcome(
                name=fixture.name,
                filename=fixture.filename,
                description=fixture.description,
                expected_verdict=fixture.expected_verdict,
                actual_verdict=paper.verdict,
                verdict_match=paper.verdict == fixture.expected_verdict,
                expected_flaw_ids=sorted(expected),
                detected_flaw_ids=sorted(detected),
                missed_flaw_ids=sorted(missed),
                unexpected_flaw_ids=sorted(unexpected),
                blocking=blocking,
                warnings=warnings,
                not_applicable=na,
                notes=[paper.summary_line, paper.action_required or ""],
            )
        )

    total_planted = sum(planted_counter.values())
    total_detected = sum(detected_counter.values())
    total_missed = total_planted - total_detected

    per_rule_detection = {
        rid: {"planted": planted_counter[rid], "detected": detected_counter.get(rid, 0)}
        for rid in sorted(planted_counter)
    }
    per_rule_misses = dict(
        sorted(
            Counter(
                rid for o in outcomes for rid in o.missed_flaw_ids
            ).items(),
            key=lambda kv: -kv[1],
        )
    )
    per_rule_false_positives = dict(
        sorted(
            Counter(
                rid for o in outcomes for rid in o.unexpected_flaw_ids
            ).items(),
            key=lambda kv: -kv[1],
        )
    )

    baseline = next((o for o in outcomes if not o.expected_flaw_ids), None)
    baseline_clean = bool(baseline and not baseline.blocking and not baseline.warnings)

    verdict_agreement = (
        statistics.fmean(1.0 if o.verdict_match else 0.0 for o in outcomes) if outcomes else 0.0
    )
    detection_rate = (total_detected / total_planted) if total_planted else 1.0

    return EvaluationReport(
        total_fixtures=len(outcomes),
        verdict_agreement=round(verdict_agreement, 4),
        detection_rate=round(detection_rate, 4),
        total_planted=total_planted,
        total_detected=total_detected,
        total_missed=total_missed,
        clean_baseline_clean=baseline_clean,
        per_rule_detection=per_rule_detection,
        per_rule_misses=per_rule_misses,
        per_rule_false_positives=per_rule_false_positives,
        outcomes=outcomes,
    )


def run() -> EvaluationReport:
    fixtures = build_corpus() + [docx_fixture()]
    return evaluate_fixtures(fixtures)


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #

VERDICT_MARK = {True: "OK  ", False: "MISS"}


def render_text(report: EvaluationReport) -> str:
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add("COMPLIANCE ENGINE EVALUATION")
    add("=" * 78)
    add(f"fixtures              : {report.total_fixtures}")
    add(f"verdict agreement     : {report.verdict_agreement:.1%} with manual expectation")
    add(f"flaw detection rate   : {report.detection_rate:.1%} "
        f"({report.total_detected}/{report.total_planted} planted flaws caught)")
    add(f"planted flaws missed  : {report.total_missed}")
    add(f"clean baseline clean  : {'yes' if report.clean_baseline_clean else 'NO'}")
    add("")

    add("-" * 78)
    add("PER FIXTURE")
    add("-" * 78)
    for o in report.outcomes:
        add(f"[{VERDICT_MARK[o.verdict_match]}] {o.name}  ({o.filename})")
        add(f"        expected={o.expected_verdict:<13} actual={o.actual_verdict:<13} "
            f"planted={len(o.expected_flaw_ids)} caught={len(o.detected_flaw_ids)}")
        if o.missed_flaw_ids:
            add(f"        MISSED   : {', '.join(o.missed_flaw_ids)}")
        if o.unexpected_flaw_ids:
            add(f"        EXTRA    : {', '.join(o.unexpected_flaw_ids)}")
    add("")

    add("-" * 78)
    add("PER RULE DETECTION")
    add("-" * 78)
    for rid, counts in report.per_rule_detection.items():
        mark = "ok " if counts["planted"] == counts["detected"] else "GAP"
        add(f"  [{mark}] {rid:<42} {counts['detected']}/{counts['planted']}")
    add("")

    if report.per_rule_false_positives:
        add("-" * 78)
        add("RULES THAT FIRED WITHOUT A PLANTED CAUSE (over-reporting)")
        add("-" * 78)
        for rid, n in report.per_rule_false_positives.items():
            add(f"  {rid:<44} {n}x")
        add("")

    if report.per_rule_misses:
        add("-" * 78)
        add("RULES THAT NEVER FIRED WHEN THEY SHOULD HAVE (blind spots)")
        add("-" * 78)
        for rid, n in report.per_rule_misses.items():
            add(f"  {rid:<44} missed {n}x")
        add("")

    add("=" * 78)
    return "\n".join(lines)


def write_json(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")


if __name__ == "__main__":
    _report = run()
    print(render_text(_report))
    out = Path(__file__).resolve().parents[3] / "evaluation_report.json"
    write_json(_report, out)
    print(f"machine-readable report written to {out}")
    sys.exit(0 if _report.verdict_agreement == 1.0 and _report.clean_baseline_clean else 1)
