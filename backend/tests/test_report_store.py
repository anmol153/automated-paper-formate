"""Tests for the report store."""

from __future__ import annotations

import tempfile
import pytest

from app.storage.report_store import ReportStore, ReportNotFound, reset_report_store


def make_submission_report(filename: str, score: int = 90, verdict: str = "accepted") -> dict:
    return {
        "template_id": "test-template",
        "template_name": "Test Template",
        "publisher": {"name": "Test Publisher"},
        "source": "upload",
        "papers": [
            {
                "filename": filename,
                "format": "pdf",
                "verdict": verdict,
                "score": score,
                "passed": 5,
                "failed": 0,
                "missing": 0,
                "not_applicable": 0,
                "blocking_reasons": [],
                "warnings": [],
                "results": [],
                "metadata": {"title": "Test Paper", "authors": ["Author One", "Author Two"]},
            }
        ],
        "accepted": 1 if verdict == "accepted" else 0,
        "rejected": 1 if verdict == "rejected" else 0,
        "needs_review": 1 if verdict == "needs_review" else 0,
        "generated_at": "2024-01-01T00:00:00Z",
    }


def make_comparison_report(filename: str, score: int = 100) -> dict:
    return {
        "score": score,
        "passed": 5,
        "failed": 0,
        "missing": 0,
        "results": [],
        "meta": {"template_title": "Template", "paper_title": "Paper"},
        "filename": filename,
        "metadata": {"title": "Comparison Paper", "authors": ["Author A"]},
    }


def test_report_store_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ReportStore(tmpdir)
        assert store.db_path.exists()


def test_save_and_get_submission_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        report = make_submission_report("paper1.pdf", score=95, verdict="accepted")
        store.save("paper1.pdf", report, kind="submission")

        retrieved = store.get("paper1.pdf")
        assert retrieved["template_id"] == "test-template"
        assert retrieved["papers"][0]["filename"] == "paper1.pdf"
        assert retrieved["papers"][0]["score"] == 95


def test_save_and_get_comparison_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        report = make_comparison_report("compare1.pdf", score=100)
        store.save("compare1.pdf", report, kind="comparison")

        retrieved = store.get("compare1.pdf")
        assert retrieved["score"] == 100
        assert retrieved["filename"] == "compare1.pdf"
        assert retrieved["metadata"]["title"] == "Comparison Paper"


def test_upsert_overwrites_by_filename():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        report1 = make_submission_report("paper.pdf", score=80, verdict="needs_review")
        store.save("paper.pdf", report1, kind="submission")

        report2 = make_submission_report("paper.pdf", score=100, verdict="accepted")
        store.save("paper.pdf", report2, kind="submission")

        retrieved = store.get("paper.pdf")
        assert retrieved["papers"][0]["score"] == 100
        assert retrieved["papers"][0]["verdict"] == "accepted"


def test_list_returns_summaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        store.save("paper1.pdf", make_submission_report("paper1.pdf", 90, "accepted"), "submission")
        store.save("paper2.pdf", make_comparison_report("paper2.pdf", 100), "comparison")

        summaries = store.list()
        assert len(summaries) == 2
        # Most recent first (paper2 was saved last)
        assert summaries[0]["filename"] == "paper2.pdf"
        assert summaries[1]["filename"] == "paper1.pdf"
        assert summaries[0]["score"] == 100
        assert summaries[1]["score"] == 90
        assert summaries[0]["verdict"] == "accepted"
        assert summaries[1]["verdict"] == "accepted"


def test_list_orders_by_updated_at_desc():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        store.save("first.pdf", make_submission_report("first.pdf", 50, "rejected"), "submission")
        store.save("second.pdf", make_submission_report("second.pdf", 90, "accepted"), "submission")

        summaries = store.list()
        # Second should be first (more recent)
        assert summaries[0]["filename"] == "second.pdf"
        assert summaries[1]["filename"] == "first.pdf"


def test_delete_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        store.save("paper.pdf", make_submission_report("paper.pdf"), "submission")
        store.delete("paper.pdf")

        with pytest.raises(ReportNotFound):
            store.get("paper.pdf")
        assert store.list() == []


def test_delete_nonexistent_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        with pytest.raises(ReportNotFound):
            store.delete("nonexistent.pdf")


def test_get_nonexistent_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        with pytest.raises(ReportNotFound):
            store.get("nonexistent.pdf")


def test_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        assert not store.exists("paper.pdf")
        store.save("paper.pdf", make_submission_report("paper.pdf"), "submission")
        assert store.exists("paper.pdf")


def test_summary_columns_populated_for_submission():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        report = make_submission_report("paper.pdf", score=85, verdict="needs_review")
        store.save("paper.pdf", report, kind="submission")

        summaries = store.list()
        s = summaries[0]
        assert s["paper_title"] == "Test Paper"
        assert s["authors"] == ["Author One", "Author Two"]
        assert s["format"] == "pdf"
        assert s["score"] == 85
        assert s["verdict"] == "needs_review"
        assert s["template_name"] == "Test Template"
        assert s["kind"] == "submission"


def test_summary_columns_populated_for_comparison():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        report = make_comparison_report("compare.pdf", score=100)
        store.save("compare.pdf", report, kind="comparison")

        summaries = store.list()
        s = summaries[0]
        assert s["paper_title"] == "Comparison Paper"
        assert s["authors"] == ["Author A"]
        assert s["format"] == ""
        assert s["score"] == 100
        assert s["verdict"] == "accepted"
        assert s["template_name"] == "Template"
        assert s["kind"] == "comparison"


def test_empty_filename_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        with pytest.raises(ValueError):
            store.save("", make_submission_report("x.pdf"), "submission")


def test_get_raw_returns_json_string():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = reset_report_store(tmpdir)
        report = make_submission_report("paper.pdf", score=95)
        store.save("paper.pdf", report, kind="submission")

        raw = store.get_raw("paper.pdf")
        assert isinstance(raw, str)
        assert '"score": 95' in raw