"""Revision diff evidence, snapshot selection, privacy and bounded extraction."""
import fitz
import pytest

from app import auth
from app.parsing.errors import ParseError
from app.services import revision_diff

from .test_phase1_security import PAPER, password_hash, world  # noqa: F401
from .test_phase2_revisions import create_paper, upload
from .test_phase3_collaboration import assign


BETTER = PAPER.replace(b"A paper.", br"\begin{abstract}A clear abstract.\end{abstract}An improved paper.")


@pytest.fixture
def schema4_world(monkeypatch, request):
    from app.storage import migrate
    monkeypatch.setattr(migrate, "MIGRATIONS", tuple(item for item in migrate.MIGRATIONS if item[0] <= 4))
    return request.getfixturevalue("world")


def pair(w, data=BETTER):
    base, first = create_paper(w)
    response = upload(w.client("author"), base, first, data)
    assert response.status_code == 201, response.text
    return base, first, response.json()


def compare(w, base, first, second, actor="author", **params):
    return w.client(actor).get(base + "/revision-comparison", params={
        "base_revision_id": first["revision_id"], "target_revision_id": second["revision_id"], **params,
    })


def test_real_text_properties_and_findings_compare_without_mutating_history(world):
    w = world
    base, first, second = pair(w)
    conn = w.submissions._connect()
    tables = ("paper_revisions", "revision_checks", "issues", "security_events", "paper_events", "notifications")
    before = {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")] for table in tables}
    response = compare(w, base, first, second, include_text=True)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["base"]["number"] == 1 and result["target"]["number"] == 2
    assert result["text"]["status"] == "available" and not result["text"]["identical"]
    lines = [line for hunk in result["text"]["hunks"] for line in hunk["lines"]]
    assert any(line["kind"] == "removed" and "A paper." in line["text"] for line in lines)
    assert any(line["kind"] == "added" and "improved paper" in line["text"] for line in lines)
    assert result["formatting"]["summary"]["resolved"] >= 1
    resolved = next(f for f in result["formatting"]["findings"] if f["state"] == "resolved")
    assert resolved["after"]["status"] == "passed" and resolved["base_issue_ids"]
    assert any(f["key"] == "structure.total_word_count" and f["state"] == "changed" for f in result["properties"]["fields"])
    assert "storage_key" not in response.text and "rules_json" not in response.text
    for table in tables:
        assert before[table] == [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]


def test_comparison_direction_and_same_revision_are_explicit(world):
    base, first, second = pair(world)
    reverse = compare(world, base, second, first, include_text=True).json()
    assert reverse["base"]["number"] == 2 and reverse["target"]["number"] == 1
    assert reverse["formatting"]["summary"]["newly_reported"] >= 1
    same = compare(world, base, first, first, include_text=True).json()
    assert same["same_file"] and same["text"]["identical"] and same["text"]["hunks"] == []


def test_source_comment_edit_does_not_claim_text_change(world):
    base, first, second = pair(world, PAPER + b"\n% only source comments changed")
    result = compare(world, base, first, second, include_text=True).json()
    assert not result["same_file"] and result["text"]["identical"]


def test_comparison_works_on_active_schema_four_without_formal_review_migration(schema4_world):
    w = schema4_world
    base, first, second = pair(w)
    assert w.submissions._connect().execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 4
    result = compare(w, base, first, second, include_text=True)
    assert result.status_code == 200 and result.json()["formatting"]["status"] == "available"
    assert w.submissions._connect().execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 4


@pytest.mark.parametrize("actor", ["other", "unassigned", "outsider"])
def test_comparison_does_not_leak_other_papers(world, actor, monkeypatch):
    base, first, second = pair(world)
    def forbidden(*args):
        pytest.fail("Unauthorized request reached text processing")
    monkeypatch.setattr(revision_diff, "compare_text", forbidden)
    assert compare(world, base, first, second, actor, include_text=True).status_code == 404


def test_readers_and_reviewers_can_compare_but_revocation_removes_access(world):
    w = world
    base, first, second = pair(w)
    sid = base.rsplit("/", 1)[1]
    w.submissions._connect().execute("INSERT INTO submission_collaborators VALUES (?,?,0)", (sid, "coauthor"))
    assert compare(w, base, first, second, "coauthor").status_code == 200
    assignment = assign(w, base)
    assert compare(w, base, first, second, "reviewer", include_text=True).status_code == 200
    assert w.client("chair").delete(base + "/assignments/" + assignment["assignment_id"]).status_code == 204
    assert compare(w, base, first, second, "reviewer", include_text=True).status_code == 404


def test_cross_paper_revision_and_check_ids_are_rejected(world):
    w = world
    base, first, second = pair(w)
    other, other_revision = create_paper(w, PAPER + b"\n% another paper")
    foreign_check = w.client("author").get(other + f"/revisions/{other_revision['revision_id']}/checks").json()[0]
    assert compare(w, base, first, other_revision).status_code == 404
    assert compare(w, base, first, second, base_run_id=foreign_check["run_id"]).status_code == 404
    first_check = w.client("author").get(base + f"/revisions/{first['revision_id']}/checks").json()[0]
    assert compare(w, base, first, second, target_run_id=first_check["run_id"]).status_code == 404


def test_failed_latest_check_is_not_silently_replaced_and_prior_runs_can_be_pinned(world, monkeypatch):
    from app.api import revision_routes
    w = world
    base, first, second = pair(w)
    initial = compare(w, base, first, second).json()
    def fail(*args):
        raise ParseError("private parser information")
    monkeypatch.setattr(revision_routes, "evaluate_document", fail)
    failed = w.client("author").post(base + "/check-compliance").json()
    latest = compare(w, base, first, second).json()
    assert latest["target"]["check"]["run_id"] == failed["run_id"]
    assert latest["formatting"]["status"] == latest["properties"]["status"] == "unavailable"
    pinned = compare(w, base, first, second, base_run_id=initial["base"]["check"]["run_id"],
                     target_run_id=initial["target"]["check"]["run_id"]).json()
    assert pinned == initial


def test_report_only_comparison_does_not_read_or_parse_files(world, monkeypatch):
    base, first, second = pair(world)
    def forbidden(*args):
        pytest.fail("Report comparison must not parse files")
    monkeypatch.setattr(revision_diff, "compare_text", forbidden)
    assert compare(world, base, first, second).json()["text"]["status"] == "not_requested"


@pytest.mark.parametrize("failure", ["missing", "tampered", "parser"])
def test_text_failure_retains_saved_comparisons_without_exposing_internal_details(world, monkeypatch, failure):
    w = world
    base, first, second = pair(w)
    row = w.submissions._connect().execute("SELECT * FROM paper_revisions WHERE revision_id=?", (first["revision_id"],)).fetchone()
    path = w.tmp_path / "private" / row["storage_key"]
    if failure == "missing":
        path.unlink()
    elif failure == "tampered":
        path.write_bytes(b"corrupted private content")
    else:
        def fail(*args):
            raise RuntimeError("private parser information")
        monkeypatch.setattr(revision_diff, "normalize_document", fail)
    response = compare(w, base, first, second, include_text=True)
    result = response.json()
    assert response.status_code == 200 and result["text"]["status"] == "unavailable"
    assert result["formatting"]["status"] == result["properties"]["status"] == "available"
    assert "private parser information" not in response.text and str(path) not in response.text


@pytest.mark.parametrize("limit,value", [("MAX_TEXT_CHARS", 5), ("MAX_TEXT_LINES", 1), ("MAX_LINE_CHARS", 4), ("MAX_HUNKS", 0)])
def test_text_limits_are_explicit_instead_of_silently_truncating(world, monkeypatch, limit, value):
    base, first, second = pair(world)
    monkeypatch.setattr(revision_diff, limit, value)
    result = compare(world, base, first, second, include_text=True).json()
    assert result["text"]["status"] == "limit_exceeded" and result["text"]["hunks"] == []
    assert result["formatting"]["status"] == "available"


def check(results, **changes):
    return {"engine_version": "test-1", "status": "failed", "assessment": {"format": "latex", "results": results}, **changes}


def finding(rule, status, **changes):
    return {"id": rule, "name": rule, "status": status, "severity": "warning", **changes}


def test_findings_require_a_pass_to_resolve_and_keep_severity_changes():
    before = check([finding("resolved", "failed"), finding("remaining", "missing"), finding("unmeasured", "failed"),
                    finding("removed", "failed"), finding("new", "passed")])
    after = check([finding("resolved", "passed"), finding("remaining", "failed", severity="blocking"),
                   finding("unmeasured", "not_applicable"), finding("new", "failed")])
    result = revision_diff.compare_findings(before, after, same_rules=True)
    assert result["summary"] == {"resolved": 1, "remaining": 1, "not_evaluated": 2, "newly_reported": 1}
    assert "severity" in next(f for f in result["findings"] if f["rule_id"] == "remaining")["changed_fields"]


@pytest.mark.parametrize("ids", [["", "second"], ["duplicate", "duplicate"]])
def test_unstable_finding_ids_do_not_generate_unreliable_matches(ids):
    old = check([finding(i, "failed") for i in ids])
    assert revision_diff.compare_findings(old, old, same_rules=True)["status"] == "unavailable"


def test_engine_template_and_format_changes_are_visible():
    old = check([finding("rule", "failed")])
    new = check([finding("rule", "passed")], engine_version="test-2")
    new["assessment"]["format"] = "pdf"
    result = revision_diff.compare_findings(old, new, same_rules=False)
    assert len(result["warnings"]) == 3 and result["summary"]["resolved"] == 1


def test_unavailable_property_is_not_assumed_to_be_zero():
    old = check([], assessment={"facts": {"layout": {"page_count": None}, "assets": {"figures": 0}}})
    new = check([], assessment={"facts": {"layout": {"page_count": 4}, "assets": {"figures": 1}}})
    fields = {f["key"]: f for f in revision_diff.compare_properties(old, new)["fields"]}
    assert fields["layout.page_count"]["state"] == "unavailable"
    assert fields["assets.figures"]["state"] == "changed" and fields["assets.figures"]["before"] == 0


def test_text_comparison_does_not_claim_full_pdf_coverage_beyond_parser_limit(tmp_path):
    from app.security.files import PrivateFiles
    with fitz.open() as doc:
        for _ in range(61):
            doc.new_page().insert_text((72, 72), "A paper page.")
        data = doc.tobytes()
    key, digest = PrivateFiles(tmp_path).put(data)
    row = {"storage_key": key, "sha256": digest, "size_bytes": len(data), "filename": "paper.pdf"}
    result = revision_diff.compare_text(tmp_path, row, row)
    assert result["status"] == "limit_exceeded" and "60 pages" in result["reason"]


@pytest.mark.parametrize("fmt", ["pdf", "docx"])
def test_existing_pdf_and_docx_parsers_support_text_comparison(tmp_path, fmt):
    from app.demo.sample_docx import build_paper_docx
    from app.demo.sample_pdfs import build_paper_pdf
    from app.security.files import PrivateFiles
    data = build_paper_pdf() if fmt == "pdf" else build_paper_docx()
    key, digest = PrivateFiles(tmp_path).put(data)
    row = {"storage_key": key, "sha256": digest, "size_bytes": len(data), "filename": "paper." + fmt}
    result = revision_diff.compare_text(tmp_path, row, row)
    assert result["status"] == "available" and result["identical"]


def test_text_comparison_throttles_without_disabling_saved_report_comparison(world):
    w = world
    base, first, second = pair(w)
    # Authenticate before setting the shared application rate bucket.
    w.client("author")
    conn = w.users._connect()
    conn.execute("INSERT OR REPLACE INTO request_limits(bucket,attempts,resets_at) VALUES (?,60,strftime('%s','now')+3600)",
                 (auth.digest("revision-text-comparison:author"),))
    assert compare(w, base, first, second, include_text=True).status_code == 429
    assert compare(w, base, first, second).status_code == 200


def test_permission_is_rechecked_after_extraction(world, monkeypatch):
    w = world
    base, first, second = pair(w)
    assign(w, base)
    original = revision_diff.compare_text
    def revoke_after(*args):
        result = original(*args)
        w.conferences.remove_member(w.conf.conference_id, "reviewer")
        return result
    monkeypatch.setattr(revision_diff, "compare_text", revoke_after)
    assert compare(w, base, first, second, "reviewer", include_text=True).status_code == 404
