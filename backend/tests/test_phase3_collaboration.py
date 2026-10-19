"""Lifecycle, confidentiality, historical identity and collaboration regressions."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.api import collaboration_routes
from app.models.rules import RuleSet

from .test_phase1_security import PAPER, password_hash, world  # noqa: F401
from .test_phase2_revisions import create_paper, upload


def move(client, base, target, reason="Test action", **overrides):
    current = client.get(base + "/workflow").json()
    return client.post(base + "/transitions", json={"target_status": target, "expected_status": current["status"],
        "expected_revision_id": current["revision_id"], "reason": reason, **overrides})


def thread(client, base, **kwargs):
    result = client.post(base + "/conversation", json={"body": "A paper comment", **kwargs})
    assert result.status_code == 201, result.text
    return result.json()


def assign(w, base):
    result = w.client("chair").post(base + "/review", json="reviewer")
    assert result.status_code == 201, result.text
    return result.json()


def test_formatting_gate_lifecycle_and_explicit_resubmission(world):
    w = world
    chair, author = w.client("chair"), w.client("author")
    policy = f"/api/v1/conferences/{w.conf.conference_id}/workflow"
    assert chair.put(policy, json={"formatting_gate": "block_errors"}).status_code == 200
    base, first = create_paper(w)
    assert author.get(base).json()["status"] == "draft"
    assert not author.get(base + "/workflow").json()["eligible"]
    assert move(author, base, "submitted").status_code == 409
    assert chair.post(base + "/review", json="reviewer").status_code == 409
    assert author.put(policy, json={"formatting_gate": "allow_issues"}).status_code == 403
    assert chair.put(policy, json={"formatting_gate": "allow_issues"}).status_code == 200
    assert move(author, base, "submitted").status_code == 200
    assign(w, base)
    assert author.get(base).json()["status"] == "under_review"
    assert upload(author, base, first).status_code == 409
    assert move(chair, base, "changes_requested", reason="").status_code == 422
    assert move(chair, base, "changes_requested", reason="Please revise the explanation").status_code == 200
    assert move(author, base, "submitted").status_code == 409
    second = upload(author, base, first)
    assert second.status_code == 201, second.text
    assert author.get(base).json()["status"] == "changes_requested"
    assert move(author, base, "submitted").status_code == 200
    assert move(chair, base, "under_review").status_code == 200
    assert move(chair, base, "accepted", reason="Accepted after revision").status_code == 200
    assert author.get(base + "/workflow").json()["decision_reason"] == "Accepted after revision"
    assert move(chair, base, "submitted").status_code == 409
    assert upload(author, base, second.json(), PAPER + b"\n% too late").status_code == 409


def test_block_errors_allows_warnings_and_draft_opt_in(world):
    w = world
    rules = RuleSet(name="Warnings")
    rules.file_type.accepted_extensions = ["tex"]
    rules.sections.abstract_max_words = 1
    w.versions.save(rules, w.conf.conference_id)
    policy = f"/api/v1/conferences/{w.conf.conference_id}/workflow"
    w.client("chair").put(policy, json={"formatting_gate": "block_errors"})
    paper = PAPER.replace(b"A paper.", br"\begin{abstract}Two words.\end{abstract}A paper.")
    base, _ = create_paper(w, paper)
    info = w.client("author").get(base + "/workflow").json()
    assert info["formatting_status"] == "passed_with_warnings"
    assert info["eligible"] and info["status"] == "submitted"
    response = w.client("author").post(f"/api/v1/conferences/{w.conf.conference_id}/submissions",
        files={"file": ("draft.tex", paper)}, data={"submit_for_review": "false"})
    assert response.status_code == 201 and response.json()["status"] == "draft"


def test_transition_rejects_stale_status_revision_and_invalid_edges(world):
    w = world
    base, first = create_paper(w)
    author, chair = w.client("author"), w.client("chair")
    assert move(chair, base, "accepted").status_code == 409
    assert move(author, base, "withdrawn", expected_status="draft").status_code == 409
    second = upload(author, base, first)
    assert second.status_code == 201
    assert move(author, base, "withdrawn", expected_revision_id=first["revision_id"]).status_code == 409
    assert move(author, base, "withdrawn").status_code == 200
    assert author.get(base + "/workflow").json()["actions"] == []
    assert move(chair, base, "submitted").status_code == 409
    assert author.get(base + f"/revisions/{first['revision_id']}/file").content == PAPER


def test_status_compatibility_endpoint_does_not_bypass_state_machine(world):
    base, _ = create_paper(world)
    assert world.client("chair").patch(base, json="accepted").status_code == 409
    assert world.client("author").patch(base, json="accepted").status_code == 403


def test_review_assignment_revocation_and_reassignment(world):
    w = world
    base, _ = create_paper(w)
    first = assign(w, base)
    reviewer = w.client("reviewer")
    assert reviewer.get(base).status_code == 200
    assert w.client("author").delete(base + "/assignments/" + first["assignment_id"]).status_code == 403
    assert w.client("chair").delete(base + "/assignments/" + first["assignment_id"]).status_code == 204
    assert reviewer.get(base).status_code == 404
    second = assign(w, base)
    assert first["assignment_id"] != second["assignment_id"]
    assert reviewer.get(base).status_code == 200
    assert w.client("author").get(base + "/workflow").json()["assignments"] == []


def test_collaborator_grants_cannot_escalate_and_revocation_removes_private_access(world):
    w = world
    base, first = create_paper(w)
    author, coauthor = w.client("author"), w.client("coauthor")
    assert author.put(base + "/collaborators", json={"user_id": "outsider", "can_edit": True}).status_code == 400
    assert author.put(base + "/collaborators", json={"user_id": "coauthor"}).status_code == 200
    assert coauthor.get(base).status_code == 200
    assert upload(coauthor, base, first).status_code == 403
    assert coauthor.put(base + "/collaborators", json={"user_id": "other", "can_edit": True}).status_code == 403
    assert author.put(base + "/collaborators", json={"user_id": "coauthor", "can_edit": True}).status_code == 200
    assert upload(coauthor, base, first).status_code == 201
    assert move(coauthor, base, "withdrawn").status_code == 403
    assert author.delete(base + "/collaborators/coauthor").status_code == 204
    for path in ["", "/revisions", "/conversation", "/activity", "/collaborators"]:
        assert coauthor.get(base + path).status_code == 404
    assert all(n["related_id"] != base.rsplit('/', 1)[1] for n in coauthor.get("/api/v1/notifications").json())


def test_paper_reviewer_cannot_be_added_as_coauthor(world):
    base, _ = create_paper(world)
    assign(world, base)
    assert world.client("author").put(base + "/collaborators", json={"user_id": "reviewer"}).status_code == 409


@pytest.mark.parametrize("actor", ["other", "unassigned", "outsider"])
def test_collaboration_endpoints_hide_unrelated_papers(world, actor):
    base, _ = create_paper(world)
    client = world.client(actor)
    for path in ["/workflow", "/activity", "/conversation", "/collaborators"]:
        assert client.get(base + path).status_code == 404
    assert client.post(base + "/conversation", json={"body": "Intrusion"}).status_code == 404
    assert client.put(base + "/collaborators", json={"user_id": actor}).status_code == 404


def test_confidential_threads_and_events_are_chair_only(world):
    w = world
    base, _ = create_paper(w)
    chair, author = w.client("chair"), w.client("author")
    secret = thread(chair, base, body="Secret chair discussion", visibility="chairs")
    assert author.post(base + "/conversation", json={"body": "Fake secret", "visibility": "chairs"}).status_code == 403
    tid = secret["thread_id"]
    assert author.get(base + "/conversation").json() == []
    assert author.post(base + f"/conversation/{tid}/comments", json={"body": "Intrusion"}).status_code == 404
    assert author.patch(base + f"/conversation/{tid}", json={"resolved": True, "expected_resolved": False}).status_code == 404
    assert chair.get(base + "/conversation").json()[0]["comments"][0]["body"] == "Secret chair discussion"
    assert all(e["visibility"] == "participants" for e in author.get(base + "/activity").json()["events"])
    assert any(e["visibility"] == "chairs" for e in chair.get(base + "/activity").json()["events"])
    assert w.notifications.list_by_user("author") == []


def test_revision_page_anchors_do_not_move_when_revised_and_cross_paper_ids_fail(world):
    w = world
    base, first = create_paper(w)
    author = w.client("author")
    anchored = thread(author, base, revision_id=first["revision_id"], page_number=1)
    assert upload(author, base, first).status_code == 201
    saved = author.get(base + "/conversation").json()[0]
    assert saved["revision_id"] == first["revision_id"] and saved["page_number"] == 1
    other, revision = create_paper(w)
    assert author.post(base + "/conversation", json={"body": "Wrong paper", "revision_id": revision["revision_id"]}).status_code == 404
    assert author.post(base + "/conversation", json={"body": "No revision", "page_number": 1}).status_code == 422
    assert author.post(other + f"/conversation/{anchored['thread_id']}/comments", json={"body": "Wrong paper"}).status_code == 404


def test_comment_replies_versions_and_soft_delete(world):
    w = world
    base, _ = create_paper(w)
    author, chair = w.client("author"), w.client("chair")
    created = thread(author, base)
    tid, comment = created["thread_id"], created["comments"][0]
    url = base + f"/conversation/{tid}/comments/{comment['comment_id']}"
    assert chair.patch(url, json={"body": "Impersonation", "expected_version": 1}).status_code == 403
    edited = author.patch(url, json={"body": "Edited comment", "expected_version": 1})
    assert edited.status_code == 200 and edited.json()["comments"][0]["version"] == 2
    assert author.patch(url, json={"body": "Stale edit", "expected_version": 1}).status_code == 409
    assert chair.post(base + f"/conversation/{tid}/comments", json={"body": "A reply", "parent_comment_id": comment["comment_id"]}).status_code == 201
    assert author.delete(url + "?expected_version=1").status_code == 409
    assert chair.delete(url + "?expected_version=2").status_code == 204
    saved = author.get(base + "/conversation").json()[0]["comments"][0]
    assert saved["deleted_at"] and saved["body"] == "" and not saved["can_edit"]
    assert w.submissions._connect().execute("SELECT body FROM paper_comments WHERE comment_id=?", (comment["comment_id"],)).fetchone()[0] == "Edited comment"


def test_replies_cannot_point_to_another_thread_and_resolution_is_explicit(world):
    w = world
    base, _ = create_paper(w)
    author = w.client("author")
    first, second = thread(author, base), thread(author, base)
    url = base + "/conversation/" + first["thread_id"]
    assert author.post(url + "/comments", json={"body": "Wrong thread", "parent_comment_id": second["comments"][0]["comment_id"]}).status_code == 404
    assert author.patch(url, json={"resolved": True, "expected_resolved": False}).status_code == 200
    assert author.post(url + "/comments", json={"body": "Closed reply"}).status_code == 409
    assert author.patch(url, json={"resolved": False, "expected_resolved": False}).status_code == 409
    assert author.patch(url, json={"resolved": False, "expected_resolved": True}).status_code == 200
    assert author.post(url + "/comments", json={"body": "Reopened reply"}).status_code == 201


def test_reviewer_identity_remains_hidden_after_assignment_revocation(world):
    w = world
    base, _ = create_paper(w)
    assignment = assign(w, base)
    thread(w.client("reviewer"), base, body="Reviewer's public observation")
    assert w.client("author").get(base + "/conversation").json()[0]["comments"][0]["author_id"] == "Reviewer"
    w.client("chair").delete(base + "/assignments/" + assignment["assignment_id"])
    assert w.client("author").get(base + "/conversation").json()[0]["comments"][0]["author_id"] == "Reviewer"
    assert w.client("chair").get(base + "/conversation").json()[0]["comments"][0]["author_id"] == "reviewer"
    events = w.client("author").get(base + "/activity").json()["events"]
    assert any(e["actor_id"] == "Reviewer" for e in events)
    assert not any(e["actor_id"] == "reviewer" for e in events)


def test_activity_is_append_only_and_pagination_does_not_leak_chair_events(world):
    w = world
    base, _ = create_paper(w)
    chair, author = w.client("chair"), w.client("author")
    for i in range(3):
        thread(author, base, body=f"Public {i}")
        thread(chair, base, body=f"Secret {i}", visibility="chairs")
    first = author.get(base + "/activity?limit=2").json()
    second = author.get(base + f"/activity?limit=2&before={first['next_before']}").json()
    assert len(first["events"]) == len(second["events"]) == 2
    assert {e["event_id"] for e in first["events"]}.isdisjoint(e["event_id"] for e in second["events"])
    assert all(e["visibility"] == "participants" for e in first["events"] + second["events"])
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        w.submissions._connect().execute("DELETE FROM paper_events")


def test_comment_write_and_notification_failure_roll_back_together(world, monkeypatch):
    w = world
    base, _ = create_paper(w)
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated notification failure")
    monkeypatch.setattr(collaboration_routes, "notify_thread", fail)
    from fastapi.testclient import TestClient
    with TestClient(w.app, base_url="https://testserver", raise_server_exceptions=False) as client:
        client.headers["Authorization"] = w.client("author").headers["Authorization"]
        assert client.post(base + "/conversation", json={"body": "Rolled back"}).status_code == 500
    assert w.client("author").get(base + "/conversation").json() == []
    assert not any(e["action"] == "conversation.comment_added" for e in w.client("author").get(base + "/activity").json()["events"])


def test_cookie_mutations_require_csrf_and_reject_impersonation_fields(world):
    w = world
    base, _ = create_paper(w)
    cookie = w.client("author", cookie=True)
    assert cookie.post(base + "/conversation", json={"body": "No CSRF"}).status_code == 403
    cookie.headers["X-CSRF-Token"] = cookie.cookies.get("paper_csrf")
    assert cookie.post(base + "/conversation", json={"body": "Valid CSRF"}).status_code == 201
    assert cookie.post(base + "/conversation", json={"body": "Fake identity", "author_id": "chair"}).status_code == 422


def test_concurrent_transitions_have_one_winner(world):
    w = world
    base, first = create_paper(w)
    common = {"expected_status": "submitted", "expected_revision_id": first["revision_id"], "reason": "Action"}
    author, chair = w.client("author"), w.client("chair")
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(author.post, base + "/transitions", json={**common, "target_status": "withdrawn"}),
                 pool.submit(chair.post, base + "/transitions", json={**common, "target_status": "rejected"})]
        results = [c.result(timeout=20) for c in calls]
    assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]


def test_unavailable_check_blocks_review_even_with_permissive_policy(world, monkeypatch):
    from app.api import revision_routes
    base, _ = create_paper(world)
    def fail(*args):
        raise RuntimeError("Parser failure")
    monkeypatch.setattr(revision_routes, "evaluate_document", fail)
    assert world.client("author").post(base + "/check-compliance").json()["status"] == "unable_to_validate"
    assert not world.client("author").get(base + "/workflow").json()["eligible"]
    assert world.client("chair").post(base + "/review", json="reviewer").status_code == 409


def test_copy_upgrade_preserves_historical_events_without_guessing_reviewer_identities(tmp_path):
    from app.storage.migrate import upgrade_target
    from .test_phase2_revisions import version_two
    source, target = tmp_path / "history.db", tmp_path / "collaboration.db"
    version_two(source)
    with sqlite3.connect(source) as conn:
        conn.execute("INSERT INTO conferences(conference_id,name,created_at,updated_at) VALUES ('conf','Legacy','old','old')")
        conn.execute("INSERT INTO submissions(submission_id,conference_id,template_id,filename,created_at,updated_at) VALUES ('paper','conf','template','paper.pdf','old','old')")
        conn.execute("INSERT INTO security_events(actor_id,action,target_id,created_at) VALUES ('old-reviewer','discussion.comment_added','paper','original-time')")
        conn.execute("INSERT INTO security_events(actor_id,action,target_id,created_at) VALUES ('old-reviewer','reviewer.verdict_recorded','paper','original-time')")
    before = source.read_bytes()
    upgrade_target(source, target, offline=True)
    with sqlite3.connect(target) as conn:
        rows = conn.execute("SELECT actor_id,actor_role,visibility,created_at FROM paper_events ORDER BY event_id").fetchall()
        assert rows == [(None, "legacy", "participants", "original-time"), (None, "legacy", "chairs", "original-time")]
        assert conn.execute("SELECT COUNT(*) FROM security_events").fetchone()[0] == 2
    assert source.read_bytes() == before
