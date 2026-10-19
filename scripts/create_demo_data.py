"""Create a resumable local walkthrough using the running application's real APIs.

Only creates demo-owned records. Does not access SQLite, migrate, reset, or modify
existing users/conferences. Credentials and progress stay in ignored backend/data.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlparse

import httpx
import pymupdf as fitz

ROOT = Path(__file__).resolve().parent.parent


def make_pdf(title, pages, revised=False):
    """Original, synthetic paper with actual selectable text and PDF pages."""
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=595.28, height=841.89)
        if index == 0:
            page.insert_textbox((54, 45, 541, 104), title, fontsize=17, fontname="hebo", align=1)
            page.insert_textbox((54, 110, 541, 146), "Alex Demo and Sam Example\nPaper-Format Demo Research Lab", fontsize=10, align=1)
            sections = [
                ("Abstract", "This synthetic paper demonstrates reproducible research collaboration. We track document revisions, evaluate formatting requirements, and preserve discussion during conference review. All results and authors in this document are fictional."),
                ("1 Introduction", "Research workflows benefit from transparent review and immutable artifacts. This demonstration provides safe material for exploring the application. It does not report real experimental results."),
                ("2 Methodology", "We retain the original manuscript and upload changes as a separate revision. The formatting checker evaluates each document against the conference template. Reviewers discuss the manuscript and submit a formal recommendation."),
            ]
        elif index == 1:
            sections = [
                ("3 Results", "The revised experiment includes a clear explanation of missing artifacts and additional reproducibility details." if revised else "The baseline experiment tracks document availability and review progress. Further explanation of missing artifacts is requested in the discussion."),
                ("4 Conclusion", "Versioned manuscripts support a transparent review process. Formatting validation is separate from the chair's final academic decision."),
                ("References", "[1] A. Demo. Synthetic research workflows. Example Proceedings, 2026.\n[2] S. Example. Reproducible review practices. Demo Journal, 2026."),
            ]
        else:
            sections = [("Appendix A: Additional observations", "This extra page intentionally exceeds the demo conference's two-page limit. Upload the two-page revised sample to correct the page-count finding.")]
        y = 165 if index == 0 else 65
        for heading, body in sections:
            page.insert_text((54, y), heading, fontsize=13, fontname="hebo")
            page.insert_textbox((54, y + 14, 541, y + 114), body, fontsize=11, lineheight=1.4)
            y += 150
        page.insert_text((285, 805), str(index + 1), fontsize=9)
    document.set_metadata({"title": title, "author": "Paper-Format synthetic demo"})
    data = document.tobytes()
    document.close()
    return data


class Demo:
    def __init__(self, args):
        self.args = args
        self.path = args.state.resolve()
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
            if self.state["api_base"] != args.api_base:
                raise RuntimeError("Saved demo belongs to another API. Choose a different --state file.")
        else:
            suffix = secrets.token_hex(3)
            password = "PaperDemo-" + secrets.token_urlsafe(9)
            self.state = {"api_base": args.api_base, "ui_base": args.ui_base, "suffix": suffix,
                          "accounts": {role: {"email": f"{role}-{suffix}@example.test", "password": password,
                                                "full_name": f"Demo {role.title()}"} for role in ("chair", "author", "reviewer")},
                          "steps": {}, "papers": {}}
            self.save()
        self.clients = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(self.state, stream, indent=2)

    def call(self, role, method, path, **kwargs):
        response = self.clients[role].request(method, path, **kwargs)
        if not response.is_success:
            try:
                detail = response.json().get("detail", "Request failed")
            except ValueError:
                detail = "Non-JSON backend error"
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {detail}")
        return response.json() if response.content else None

    def once(self, key, operation):
        if key not in self.state["steps"]:
            self.state["steps"][key] = operation()
            self.save()
            print(f"Created {key}", flush=True)
        return self.state["steps"][key]

    def authenticate(self):
        for role, account in self.state["accounts"].items():
            client = httpx.Client(base_url=self.args.api_base + "/", timeout=120, trust_env=False)
            self.clients[role] = client
            if not account.get("user_id"):
                user = self.call(role, "POST", "auth/register", json={k: account[k] for k in ("email", "password", "full_name")})
                account["user_id"] = user["user_id"]
                self.save()
            session = self.call(role, "POST", "auth/login", data={"username": account["email"], "password": account["password"]})
            # Existing supported API-client bearer flow; browser sign-in still uses
            # its normal HttpOnly cookie/CSRF session. Never persist access tokens.
            client.headers["Authorization"] = "Bearer " + session["access_token"]

    def transition(self, paper, status, reason=""):
        workflow = self.call("chair", "GET", f"submissions/{paper}/workflow")
        return self.call("chair", "POST", f"submissions/{paper}/transitions", json={
            "target_status": status, "expected_status": workflow["status"],
            "expected_revision_id": workflow["revision_id"], "reason": reason})

    def run(self):
        # Displaying an existing walkthrough must not consume the shared local
        # login budget (10 attempts per 15 minutes, including successful logins).
        if self.state.get("complete"):
            self.describe()
            return
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.get(self.args.api_base + "/health")
            response.raise_for_status()
        self.authenticate()
        conf = self.once("conference", lambda: self.call("chair", "POST", "conferences/", json={
            "name": f"[DEMO] Research Systems Conference · {self.state['suffix']}",
            "description": "Synthetic walkthrough data for Paper-Format. Explore author, reviewer and chair workflows. No real research or personal data."}))
        conference_id = conf["conference_id"]
        base = f"conferences/{conference_id}"
        for role in ("author", "reviewer"):
            self.once(f"membership-{role}", lambda role=role: self.call("chair", "POST", base + "/members", json={"user_id": self.state["accounts"][role]["user_id"], "role": role}))
        now = datetime.now(timezone.utc)
        settings = self.call("chair", "GET", base + "/settings")
        self.once("settings", lambda: self.call("chair", "PUT", base + "/settings", json={"expected_version": settings["version"], "settings": {
            "abbreviation": "DEMO-RSC", "research_scope": "Reproducible research and document collaboration", "lifecycle_status": "open",
            "submissions_open_at": (now - timedelta(days=1)).isoformat(), "submissions_close_at": (now + timedelta(days=60)).isoformat(),
            "revisions_close_at": (now + timedelta(days=90)).isoformat(), "require_title": True, "require_abstract": True, "require_authors": True, "require_track": True}}))
        track = self.once("track", lambda: self.call("chair", "POST", base + "/tracks", json={"name": "Research Systems", "description": "Synthetic research submissions"}))
        self.once("template", lambda: self.call("chair", "POST", base + "/templates", json={
            "name": "Demo manuscript requirements v1", "description": "PDF/DOCX/LaTeX; maximum two pages. Deliberately simple rules for exploring real validation.",
            "file_type": {"accepted_extensions": ["pdf", "docx", "tex", "latex"]}, "pages": {"max_pages": 2}, "sections": {"abstract_required": True}}))
        self.once("workflow-policy", lambda: self.call("chair", "PUT", base + "/workflow", json={"formatting_gate": "allow_issues"}))
        review_config = self.call("chair", "GET", base + "/review-configuration")
        self.once("review-configuration", lambda: self.call("chair", "PUT", base + "/review-configuration", json={
            "expected_version": review_config["version"], "form": review_config["form"], "policy": {
                **review_config["policy"], "minimum_reviews": 1, "reviewer_identities": "hidden", "deadline": (now + timedelta(days=75)).isoformat()}}))

        specifications = [
            ("workspace", "Reproducible Research Workflows", 3, True),
            ("formatting", "Formatting Fixes: A Hands-On Example", 3, False),
            ("revision", "Artifact Tracking for Open Research", 2, True),
            ("accepted", "Transparent Collaboration in Peer Review", 2, True),
            ("submitted", "Document-Centered Research Collaboration", 2, True),
        ]
        samples = self.path.parent / "demo-samples"
        samples.mkdir(exist_ok=True)
        for key, title, pages, submit in specifications:
            content = make_pdf(title, pages)
            (samples / f"{key}-initial.pdf").write_bytes(content)
            (samples / f"{key}-revised.pdf").write_bytes(make_pdf(title, 2, revised=True))
            metadata = {"title": title, "abstract": "A fictional research paper demonstrating versioned manuscripts, formatting checks, reviewer feedback and conference decisions. Use this submission to explore the application safely.",
                        "authors": [{"name": "Alex Demo", "affiliation": "Paper-Format Demo Research Lab"}, {"name": "Sam Example", "affiliation": "Example Institute"}], "track_id": track["track_id"]}
            record = self.once(f"paper-{key}", lambda title=title, content=content, metadata=metadata, submit=submit, key=key: self.call("author", "POST", base + "/submissions", files={"file": (f"{key}-initial.pdf", content, "application/pdf")}, data={"metadata_json": json.dumps(metadata), "submit_for_review": str(submit).lower()}))
            self.state["papers"][key] = {"id": record["submission_id"], "title": title}
            self.save()

        main = self.state["papers"]["workspace"]["id"]
        history = self.call("author", "GET", f"submissions/{main}/revisions")
        original = next(row for row in history["revisions"] if row["number"] == 1)
        updated = self.once("second-revision", lambda: self.call("author", "POST", f"submissions/{main}/revisions", files={"file": ("workspace-revised.pdf", (samples / "workspace-revised.pdf").read_bytes(), "application/pdf")}, data={
            "parent_revision_id": original["revision_id"], "change_summary": "Removed the extra appendix page and clarified missing-artifact handling. Original file and feedback remain available.", "request_key": "demo-" + self.state["suffix"]}))
        self.once("earlier-discussion", lambda: self.call("author", "POST", f"submissions/{main}/conversation", json={"body": "This first upload contains an extra appendix page. The next revision removes it; keep this thread attached to the original document.", "revision_id": original["revision_id"], "page_number": 3}))
        for key in ("workspace", "revision", "accepted", "submitted"):
            paper_id = self.state["papers"][key]["id"]
            workflow = self.call("chair", "GET", f"submissions/{paper_id}/workflow")
            if workflow["status"] == "draft":
                self.once(f"submit-{key}", lambda paper_id=paper_id: self.transition(paper_id, "submitted"))
            if key != "submitted":
                self.once(f"assignment-{key}", lambda paper_id=paper_id: self.call("chair", "POST", f"submissions/{paper_id}/review", json=self.state["accounts"]["reviewer"]["user_id"]))
        self.once("current-discussion", lambda: self.call("reviewer", "POST", f"submissions/{main}/conversation", json={"body": "The revised paper now fits the page limit. Could you expand the explanation of missing artifacts in Section 3?", "revision_id": updated["revision_id"], "page_number": 2}))
        self.once("confidential-discussion", lambda: self.call("chair", "POST", f"submissions/{main}/conversation", json={"body": "Demo chair-only note: coordinate reviewers here. This thread must not appear for the author or reviewer account.", "visibility": "chairs"}))
        revision_paper = self.state["papers"]["revision"]["id"]
        self.once("changes-requested", lambda: self.transition(revision_paper, "changes_requested", "Please clarify the artifact availability policy, upload a revised document, and resubmit. This is a sample revision request."))

        for key, submitted in (("workspace", False), ("accepted", True)):
            paper_id = self.state["papers"][key]["id"]
            data = self.call("reviewer", "GET", f"submissions/{paper_id}/reviews")
            config = data["configuration"]
            answers = {criterion["id"]: (4 if criterion["kind"] == "score" else "Clear motivation and useful revision history." if criterion["id"] == "strengths" else "The experimental description could be more detailed." if criterion["id"] == "weaknesses" else "Clarify reproducibility details in Section 3.") for criterion in config["form"]["criteria"]}
            self.once(f"review-{key}", lambda paper_id=paper_id, data=data, config=config, answers=answers, submitted=submitted: self.call("reviewer", "PUT", f"submissions/{paper_id}/reviews/mine", json={
                "assignment_id": data["assignment_id"], "revision_id": data["revision_id"], "form_id": config["form_id"], "expected_version": 0, "submit": submitted,
                "recommendation": "Accept", "answers": answers, "confidential_comments": "Synthetic confidential review note for chairs. Not visible to authors."}))
        accepted = self.state["papers"]["accepted"]["id"]
        accepted_revision = self.call("chair", "GET", f"submissions/{accepted}/workflow")["revision_id"]
        self.once("released-review", lambda: self.call("chair", "POST", f"submissions/{accepted}/reviews/release", json={"expected_revision_id": accepted_revision}))
        self.once("accepted-decision", lambda: self.transition(accepted, "accepted", "Accepted for this synthetic demo after a completed review. This is not a real conference decision."))
        self.state["sample_directory"] = str(samples)
        self.save()
        self.verify()
        self.state["complete"] = True
        self.save()
        self.describe()

    def verify(self):
        expected = {"workspace": "under_review", "formatting": "draft", "revision": "changes_requested", "accepted": "accepted", "submitted": "submitted"}
        for key, status in expected.items():
            data = self.call("chair", "GET", f"submissions/{self.state['papers'][key]['id']}")
            if data["status"] != status:
                raise RuntimeError(f"Unexpected demo state for {key}: {data['status']}")
        paper_id = self.state["papers"]["workspace"]["id"]
        for role in ("author", "reviewer"):
            threads = self.call(role, "GET", f"submissions/{paper_id}/conversation")
            if any(thread["visibility"] == "chairs" for thread in threads):
                raise RuntimeError("Confidential demo thread was exposed")
        checks = self.call("author", "GET", f"submissions/{paper_id}/revisions")
        if len(checks["revisions"]) != 2:
            raise RuntimeError("Expected two immutable demo revisions")
        print("Verified real lifecycle states, two revisions, and confidential-thread filtering.", flush=True)

    def describe(self):
        ui = self.state["ui_base"]
        conference_id = self.state["steps"]["conference"]["conference_id"]
        print("\nDemo ready. Sign in normally at " + ui + "/login")
        for role, account in self.state["accounts"].items():
            print(f"{role}: {account['email']} | password: {account['password']}")
        print("Conference: " + ui + "/conferences/" + conference_id)
        print("Papers: " + ui + "/conferences/" + conference_id + "/submissions")
        print("Main workspace: " + ui + "/submissions/" + self.state["papers"]["workspace"]["id"])
        print("Local credentials and progress: " + str(self.path))
        print("Sample PDFs: " + str(self.path.parent / "demo-samples"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--ui-base", default="http://localhost:5173")
    parser.add_argument("--state", type=Path, default=ROOT / "backend/data/demo-walkthrough.json")
    args = parser.parse_args()
    args.api_base = args.api_base.rstrip("/")
    if urlparse(args.api_base).hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("This demo generator only writes to a local development API.")
    try:
        demo = Demo(args)
        try:
            demo.run()
        finally:
            for client in demo.clients.values():
                client.close()
    except (httpx.HTTPError, RuntimeError) as error:
        print(f"Demo stopped: {error}\nProgress is retained; rerun the same command to continue.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
