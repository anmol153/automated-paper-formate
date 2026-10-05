"""End-to-end coverage for the submission portal API.

Exercises the manager setup flow (import template -> edit rules -> save) and the
author flow (multi-file upload -> per-paper verdicts), plus the batch fault
tolerance that makes multi-paper submission usable in practice.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.template_store import reset_store


@pytest.fixture()
def client(tmp_path):
    reset_store(tmp_path / "templates")
    with TestClient(app) as test_client:
        yield test_client
    reset_store()


@pytest.fixture()
def rules_payload() -> dict:
    return {
        "name": "Test Venue",
        "description": "Fixture rules",
        "file_type": {"accepted_extensions": ["pdf", "tex"], "max_file_size_mb": 50},
        "pages": {
            "max_pages": 8,
            "page_size_label": "A4",
            "orientation": "portrait",
            "columns": 2,
            "margins": {"top_pt": 64, "bottom_pt": 64, "left_pt": 54, "right_pt": 54},
        },
        "sections": {
            "required_sections": ["Abstract", "Introduction", "Conclusion", "References"],
            "keywords_required": True,
            "min_reference_entries": 2,
        },
        "anonymisation": {"required": True},
        "typography": {"body": {"font_family": "Times New Roman", "font_size_pt": 10}},
        "publisher": {
            "publisher_name": "Test Publisher",
            "conference_name": "TestConf 2026",
            "contact_email": "format@testconf.org",
        },
    }


def _template_file() -> tuple[str, bytes, str]:
    return ("template.tex", open("samples/template.tex", "rb").read(), "application/x-tex")


def _paper_file(name: str = "paper.tex"):
    return (name, open("samples/paper.tex", "rb").read(), "application/x-tex")


# --------------------------------------------------------------------------- #
# health + schema
# --------------------------------------------------------------------------- #


def test_health_lists_formats_and_google_auth(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert set(body["parsers"]) == {"pdf", "latex", "docx"}
    assert "google_auth" in body


def test_rule_schema_exposes_groups_and_presets(client):
    schema = client.get("/api/v1/rule-schema").json()
    keys = [g["key"] for g in schema["groups"]]
    for expected in ("file_type", "pages", "sections", "anonymisation", "decision", "publisher"):
        assert expected in keys
    assert schema["templates"], "publisher presets should be offered"
    assert all("rules" in preset for preset in schema["templates"])


# --------------------------------------------------------------------------- #
# conference-manager setup flow
# --------------------------------------------------------------------------- #


def test_import_template_infers_rules_without_saving(client):
    name, data, ctype = _template_file()
    response = client.post(
        "/api/v1/templates/import",
        files={"file": (name, data, ctype)},
        data={"name": "Imported Venue"},
    )
    assert response.status_code == 200
    rules = response.json()
    assert rules["name"] == "Imported Venue"
    assert rules["pages"]["page_size_label"] == "A4"
    assert rules["pages"]["columns"] == 2
    assert rules["typography"]["body"]["font_family"]
    assert "Introduction" in rules["sections"]["required_sections"]
    # Nothing persisted yet.
    assert client.get("/api/v1/templates").json()["count"] == 0


def test_template_crud_round_trip(client, rules_payload):
    created = client.post("/api/v1/templates", json=rules_payload)
    assert created.status_code == 201
    template_id = created.json()["template_id"]
    assert template_id

    assert client.get("/api/v1/templates").json()["count"] == 1
    fetched = client.get(f"/api/v1/templates/{template_id}").json()
    assert fetched["pages"]["max_pages"] == 8
    assert fetched["publisher"]["contact_email"] == "format@testconf.org"

    rules_payload["pages"]["max_pages"] = 4
    updated = client.put(f"/api/v1/templates/{template_id}", json=rules_payload)
    assert updated.status_code == 200
    assert client.get(f"/api/v1/templates/{template_id}").json()["pages"]["max_pages"] == 4

    assert client.delete(f"/api/v1/templates/{template_id}").status_code == 200
    assert client.get(f"/api/v1/templates/{template_id}").status_code == 404


def test_template_name_is_required(client, rules_payload):
    rules_payload["name"] = "Untitled template"
    assert client.post("/api/v1/templates", json=rules_payload).status_code == 422


def test_creating_template_from_preset_works(client):
    preset = client.get("/api/v1/rule-schema").json()["templates"][0]
    payload = {"name": preset["name"]}
    for group, values in preset["rules"].items():
        payload[group] = values
    response = client.post("/api/v1/templates", json=payload)
    assert response.status_code == 201
    assert response.json()["pages"]["max_pages"] == 8


# --------------------------------------------------------------------------- #
# author submission flow
# --------------------------------------------------------------------------- #


def test_submit_single_paper_returns_verdict_and_advice(client, rules_payload):
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file()

    response = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": template_id},
    )
    assert response.status_code == 200
    report = response.json()

    assert report["template_name"] == "Test Venue"
    assert report["publisher"]["conference_name"] == "TestConf 2026"
    assert len(report["papers"]) == 1

    paper = report["papers"][0]
    assert paper["verdict"] in ("accepted", "rejected", "needs_review")
    assert paper["facts"]["structure"]["title_present"] is True
    assert paper["results"], "every rule should produce a result row"

    if paper["verdict"] == "rejected":
        assert paper["blocking_reasons"]
        for reason in paper["blocking_reasons"]:
            assert reason["advice"], f"{reason['id']} rejected without telling the author why"


def test_submit_many_papers_in_one_request(client, rules_payload):
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    files = [
        ("files", _paper_file(f"paper-{i}.tex")) for i in range(5)
    ]
    response = client.post(
        "/api/v1/submissions",
        files=files,
        data={"template_id": template_id},
    )
    assert response.status_code == 200
    report = response.json()
    assert len(report["papers"]) == 5
    assert {p["filename"] for p in report["papers"]} == {f"paper-{i}.tex" for i in range(5)}
    assert report["accepted"] + report["rejected"] + report["needs_review"] == 5


def test_submission_without_rules_is_rejected(client):
    name, data, ctype = _paper_file()
    response = client.post(
        "/api/v1/submissions", files={"files": (name, data, ctype)}
    )
    assert response.status_code == 422
    assert "template_id" in response.json()["detail"]


def test_submission_with_unknown_template_is_404(client):
    name, data, ctype = _paper_file()
    response = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": "does-not-exist"},
    )
    assert response.status_code == 404


def test_submission_accepts_inline_rules(client, rules_payload):
    name, data, ctype = _paper_file()
    response = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"rules": json.dumps(rules_payload)},
    )
    assert response.status_code == 200
    assert len(response.json()["papers"]) == 1


# --------------------------------------------------------------------------- #
# batch fault tolerance
# --------------------------------------------------------------------------- #


def test_unparseable_file_does_not_abort_the_batch(client, rules_payload):
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    good_name, good_data, ctype = _paper_file("good.tex")

    # Note: files must be passed as a flat list so that httpx emits one multipart
    # part per file, matching what a browser's FormData appends repeatedly.
    response = client.post(
        "/api/v1/submissions",
        files=[
            ("files", (good_name, good_data, ctype)),
            ("files", ("notes.txt", b"just some prose, not a paper", "text/plain")),
            ("files", ("empty.tex", b"", "application/x-tex")),
        ],
        data={"template_id": template_id},
    )
    assert response.status_code == 200
    report = response.json()
    assert len(report["papers"]) == 3

    by_name = {p["filename"]: p for p in report["papers"]}
    assert by_name["good.tex"]["verdict"] != "rejected" or by_name["good.tex"]["results"]
    assert by_name["notes.txt"]["verdict"] == "rejected"
    assert "not a recognised format" in by_name["notes.txt"]["action_required"]
    assert by_name["empty.tex"]["verdict"] == "rejected"
    assert "empty" in by_name["empty.tex"]["action_required"].lower()


def test_wrong_extension_is_flagged_by_the_file_type_rule(client, rules_payload):
    rules_payload["file_type"]["accepted_extensions"] = ["pdf"]
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file("paper.tex")

    report = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": template_id},
    ).json()

    result = next(r for r in report["papers"][0]["results"] if r["id"] == "file.extension_accepted")
    assert result["status"] == "failed"
    assert result["severity"] == "blocking"


# --------------------------------------------------------------------------- #
# the four headline rules
# --------------------------------------------------------------------------- #


def _result_ids(paper: dict) -> set[str]:
    return {r["id"] for r in paper["results"]}


def _long_paper(pages_worth: int = 12) -> bytes:
    """A deliberately over-length LaTeX paper, for page-limit testing.

    The stock sample is one page, so a page-limit rule cannot be exercised
    against it; this pads the body until the estimated page count is well past
    any realistic limit.
    """
    filler = (
        "The proposed system was evaluated across a stratified corpus of documents "
        "and the measured agreement with expert review remained stable under "
        "perturbation of the input distribution. "
    )
    body = "\n".join("\\section{Analysis}\n" + filler * 12 for _ in range(pages_worth))
    return (
        "\\documentclass[11pt,a4paper]{article}\n"
        "\\begin{document}\n"
        "\\title{A Long Paper For Page Limit Testing}\n"
        "\\author{Anonymous Author}\n"
        "\\maketitle\n"
        "\\begin{abstract}\nA short abstract for the test fixture.\n\\end{abstract}\n"
        f"{body}\n"
        "\\section{References}\n[1] A. Author, A Reference, 2024.\n"
        "\\end{document}\n"
    ).encode("utf-8")


def test_page_limit_rule_fires_when_exceeded(client, rules_payload):
    rules_payload["pages"]["max_pages"] = 2
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]

    report = client.post(
        "/api/v1/submissions",
        files=[("files", ("long.tex", _long_paper(), "application/x-tex"))],
        data={"template_id": template_id},
    ).json()

    paper = report["papers"][0]
    page = next(r for r in paper["results"] if r["id"] == "page.limit")
    assert page["status"] == "failed"
    assert page["severity" ] == "blocking"
    assert "exceeds" in page["advice"]
    assert paper["verdict"] == "rejected"
    # The estimate is labelled as such so authors are not misled by a hard number.
    assert "estimated" in page["actual"]


def test_page_limit_passes_when_within_budget(client, rules_payload):
    rules_payload["pages"]["max_pages"] = 50
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file("paper.tex")

    paper = client.post(
        "/api/v1/submissions",
        files=[("files", (name, data, ctype))],
        data={"template_id": template_id},
    ).json()["papers"][0]

    page = next(r for r in paper["results"] if r["id"] == "page.limit")
    assert page["status"] == "passed"


def test_pdf_page_count_is_exact_and_latex_is_estimated(client, rules_payload):
    """PDFs report a measured page count; source formats report an estimate."""
    rules_payload["file_type"]["accepted_extensions"] = ["pdf", "tex"]
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]

    report = client.post(
        "/api/v1/submissions",
        files=[
            ("files", ("paper.tex", open("samples/paper.tex", "rb").read(), "application/x-tex")),
            ("files", ("paper.pdf", open("samples/paper.pdf", "rb").read(), "application/pdf")),
        ],
        data={"template_id": template_id},
    ).json()

    by_name = {p["filename"]: p for p in report["papers"]}
    assert by_name["paper.tex"]["facts"]["layout"]["page_count_exact"] is False
    assert by_name["paper.pdf"]["facts"]["layout"]["page_count_exact"] is True
    assert by_name["paper.pdf"]["facts"]["pdf"]["page_count"] >= 1


def test_required_sections_rule_fires_when_absent(client, rules_payload):
    rules_payload["sections"]["required_sections"] = ["Methodology", "Related Work"]
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file("paper.tex")

    paper = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": template_id},
    ).json()["papers"][0]

    ids = _result_ids(paper)
    assert "structure.section.methodology" in ids
    methodology = next(r for r in paper["results"] if r["id"] == "structure.section.methodology")
    assert methodology["status"] == "missing"
    assert methodology["severity"] == "blocking"


def test_anonymisation_rule_fires_on_author_block(client, rules_payload):
    rules_payload["anonymisation"] = {"required": True}
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file("paper.tex")

    paper = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": template_id},
    ).json()["papers"][0]

    author = next(r for r in paper["results"] if r["id"] == "anonymisation.author_block")
    assert author["status"] == "failed"
    assert paper["verdict"] == "rejected"


def test_anonymisation_is_inert_when_not_required(client, rules_payload):
    rules_payload["anonymisation"] = {"required": False}
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file("paper.tex")

    paper = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": template_id},
    ).json()["papers"][0]

    enabled = next(r for r in paper["results"] if r["id"] == "anonymisation.enabled")
    assert enabled["status"] == "not_applicable"


# --------------------------------------------------------------------------- #
# reporting semantics
# --------------------------------------------------------------------------- #


def test_unmeasurable_rules_are_not_counted_as_failures(client, rules_payload):
    """A disabled rule must be 'not_applicable', never a failure.

    Regression guard: the earlier template-comparison path reported every
    unmeasurable property as 'missing', which silently penalised PDFs.
    """
    rules_payload["paragraph"] = {"line_spacing": 1.5}
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file("paper.tex")

    paper = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": template_id},
    ).json()["papers"][0]

    statuses = {r["status"] for r in paper["results"]}
    assert "not_applicable" in statuses
    assert paper["not_applicable"] > 0
    scored = paper["passed"] + paper["failed"] + paper["missing"]
    assert scored == len([r for r in paper["results"] if r["status"] != "not_applicable"])


def test_facts_expose_extraction_detail_for_each_paper(client, rules_payload):
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    name, data, ctype = _paper_file("paper.tex")

    paper = client.post(
        "/api/v1/submissions",
        files={"files": (name, data, ctype)},
        data={"template_id": template_id},
    ).json()["papers"][0]

    facts = paper["facts"]
    assert facts["file"]["format"] == "latex"
    assert facts["file"]["sha256"]
    assert facts["layout"]["page_count"] >= 1
    assert facts["structure"]["sections_present"]
    assert facts["latex"]["document_class"] == "article"
    assert facts["identity"]["author_block_present"] is True
    assert "Alice Lee" in facts["identity"]["detected_person_names"]


# --------------------------------------------------------------------------- #
# Drive endpoints degrade cleanly when unconfigured
# --------------------------------------------------------------------------- #


def test_drive_status_reports_configuration(client):
    body = client.get("/api/v1/drive/status").json()
    assert "configured" in body and "auth_mode" in body


def test_drive_submission_without_credentials_is_503_with_guidance(client, rules_payload):
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    response = client.post(
        "/api/v1/submissions/drive",
        json={"folder_url": "https://drive.google.com/drive/folders/1a2B3c4D5e6F7g8H9i0J",
              "template_id": template_id},
    )
    assert response.status_code == 503
    assert "service_account.json" in response.json()["detail"]


def test_drive_submission_rejects_a_non_drive_link(client, rules_payload):
    template_id = client.post("/api/v1/templates", json=rules_payload).json()["template_id"]
    response = client.post(
        "/api/v1/submissions/drive",
        json={"folder_url": "https://example.com/my-papers", "template_id": template_id},
    )
    assert response.status_code == 400
    assert "Google Drive" in response.json()["detail"]
