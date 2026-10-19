"""Conference setup contracts: no proxy redirects, role checks, pinned templates."""
import pytest

from app import auth
from app.models.rules import RuleSet

from .test_phase1_security import PAPER, password_hash, world  # noqa: F401


@pytest.mark.parametrize("suffix", ["", "/"])
def test_conference_create_and_list_do_not_redirect_cookie_sessions(world, suffix):
    client = world.client("chair", cookie=True)
    response = client.post(
        "/api/v1/conferences" + suffix,
        json={"name": "Conference onboarding", "description": "Local UI setup"},
        headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin",
                 "X-CSRF-Token": client.cookies.get(auth.CSRF_COOKIE)},
        follow_redirects=False,
    )
    assert response.status_code == 201, response.text
    assert "location" not in response.headers
    conf = response.json()
    assert any(member["user_id"] == "chair" and member["role"] == "owner" for member in conf["members"])
    listed = client.get("/api/v1/conferences" + suffix, follow_redirects=False)
    assert listed.status_code == 200
    assert "location" not in listed.headers
    assert any(row["conference_id"] == conf["conference_id"] for row in listed.json())


@pytest.mark.parametrize("suffix", ["", "/"])
def test_conference_alias_preserves_csrf_and_origin_checks(world, suffix):
    client = world.client("chair", cookie=True)
    url = "/api/v1/conferences" + suffix
    headers = {"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-origin"}
    assert client.post(url, json={"name": "Denied"}, headers=headers, follow_redirects=False).status_code == 403
    headers["X-CSRF-Token"] = client.cookies.get(auth.CSRF_COOKIE)
    for extra in [{"Origin": "https://untrusted.example"}, {"Sec-Fetch-Site": "cross-site"}]:
        response = client.post(url, json={"name": "Denied"}, headers={**headers, **extra}, follow_redirects=False)
        assert response.status_code == 403
        assert "location" not in response.headers
    assert not any(conf.name == "Denied" for conf in world.conferences.list_conferences())


def test_publishing_requires_chair_and_preserves_paper_template_snapshots(world):
    chair, author = world.client("chair"), world.client("author")
    created = chair.post("/api/v1/conferences/", json={"name": "Template publishing"})
    assert created.status_code == 201
    conf_id = created.json()["conference_id"]
    base = "/api/v1/conferences/" + conf_id
    assert chair.get(base + "/templates").json() == []
    assert chair.post(base + "/members", json={"user_id": "author", "role": "author"}).status_code == 201
    assert world.client("outsider").get(base + "/templates").status_code == 404
    rules = RuleSet(name="First requirements")
    rules.file_type.accepted_extensions = ["tex"]
    assert author.post(base + "/templates", json=rules.model_dump()).status_code == 403
    first = chair.post(base + "/templates", json=rules.model_dump())
    assert first.status_code == 201
    first = first.json()
    original_paper = author.post(base + "/submissions", files={"file": ("first.tex", PAPER)})
    assert original_paper.status_code == 201, original_paper.text
    assert original_paper.json()["template_id"] == first["template_id"]
    rules.name = "Updated requirements"
    second = chair.post(base + "/templates", json=rules.model_dump())
    assert second.status_code == 201
    second = second.json()
    assert first["template_id"] != second["template_id"]
    rows = author.get(base + "/templates").json()
    assert [row[0] for row in rows] == [second["template_id"], first["template_id"]]
    assert author.get(base + "/templates/" + first["template_id"]).json() == first
    assert author.get(base + "/templates/latest").json() == second
    assert author.get("/api/v1/submissions/" + original_paper.json()["submission_id"]).json()["template_id"] == first["template_id"]
    new_paper = author.post(base + "/submissions", files={"file": ("second.tex", PAPER)})
    assert new_paper.status_code == 201, new_paper.text
    assert new_paper.json()["template_id"] == second["template_id"]


def test_only_chairs_receive_conference_memberships(world):
    url = "/api/v1/conferences/" + world.conf.conference_id
    chair = world.client("chair").get(url)
    assert chair.status_code == 200
    assert chair.json()["owners"] == ["chair"]
    assert {member["user_id"] for member in chair.json()["members"]} == {"chair", "author", "other", "coauthor", "reviewer", "unassigned"}
    for actor in ["author", "reviewer"]:
        response = world.client(actor).get(url)
        assert response.status_code == 200
        assert response.json()["members"] == response.json()["owners"] == []
    assert world.client("outsider").get(url).status_code == 404
    for row in world.client("outsider").get("/api/v1/conferences/").json():
        assert row["members"] == row["owners"] == []
