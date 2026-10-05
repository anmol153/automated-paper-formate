"""Tests for the report API endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import router
from app.main import app
from app.storage.report_store import reset_report_store

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture(autouse=True)
def temp_report_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        reset_report_store(tmpdir)
        yield


def test_list_reports_empty():
    client = TestClient(app)
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    assert response.json() == {"reports": []}


def test_list_reports_after_submission():
    client = TestClient(app)

    # Create a template first
    template = {
        "name": "Test Template",
        "document": {
            "page_size": "a4",
            "margins_pt": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "columns": 1,
        },
        "typography": {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5},
    }
    resp = client.post("/api/v1/templates", json=template)
    assert resp.status_code == 201
    template_id = resp.json()["template_id"]

    # Submit a paper (using real sample PDF)
    pdf_content = (SAMPLES_DIR / "paper.pdf").read_bytes()
    files = {"files": ("test_paper.pdf", pdf_content, "application/pdf")}
    data = {"template_id": template_id}
    resp = client.post("/api/v1/submissions", files=files, data=data)
    assert resp.status_code == 200

    # List reports
    resp = client.get("/api/v1/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["reports"]) == 1
    report = data["reports"][0]
    assert report["filename"] == "test_paper.pdf"
    assert report["kind"] == "submission"
    assert report["score"] >= 0
    assert report["verdict"] in ("accepted", "rejected", "needs_review")


def test_get_report():
    client = TestClient(app)

    # Create a template first
    template = {
        "name": "Test Template",
        "document": {
            "page_size": "a4",
            "margins_pt": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "columns": 1,
        },
        "typography": {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5},
    }
    resp = client.post("/api/v1/templates", json=template)
    assert resp.status_code == 201
    template_id = resp.json()["template_id"]

    # Submit a paper
    pdf_content = (SAMPLES_DIR / "paper.pdf").read_bytes()
    files = {"files": ("test_paper.pdf", pdf_content, "application/pdf")}
    data = {"template_id": template_id}
    resp = client.post("/api/v1/submissions", files=files, data=data)
    assert resp.status_code == 200

    # Get the report
    resp = client.get("/api/v1/reports/test_paper.pdf")
    assert resp.status_code == 200
    report = resp.json()
    assert report["template_id"] == template_id
    assert report["papers"][0]["filename"] == "test_paper.pdf"
    assert "metadata" in report["papers"][0]


def test_get_nonexistent_report():
    client = TestClient(app)
    resp = client.get("/api/v1/reports/nonexistent.pdf")
    assert resp.status_code == 404


def test_delete_report():
    client = TestClient(app)

    # Create a template first
    template = {
        "name": "Test Template",
        "document": {
            "page_size": "a4",
            "margins_pt": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "columns": 1,
        },
        "typography": {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5},
    }
    resp = client.post("/api/v1/templates", json=template)
    assert resp.status_code == 201
    template_id = resp.json()["template_id"]

    # Submit a paper
    pdf_content = (SAMPLES_DIR / "paper.pdf").read_bytes()
    files = {"files": ("test_paper.pdf", pdf_content, "application/pdf")}
    data = {"template_id": template_id}
    resp = client.post("/api/v1/submissions", files=files, data=data)
    assert resp.status_code == 200

    # Delete the report
    resp = client.delete("/api/v1/reports/test_paper.pdf")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": "test_paper.pdf"}

    # Verify it's gone
    resp = client.get("/api/v1/reports/test_paper.pdf")
    assert resp.status_code == 404

    # List should be empty
    resp = client.get("/api/v1/reports")
    assert resp.json() == {"reports": []}


def test_delete_nonexistent_report():
    client = TestClient(app)
    resp = client.delete("/api/v1/reports/nonexistent.pdf")
    assert resp.status_code == 404


def test_compare_persists_report():
    client = TestClient(app)

    # Create a template first
    template = {
        "name": "Test Template",
        "document": {
            "page_size": "a4",
            "margins_pt": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "columns": 1,
        },
        "typography": {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5},
    }
    resp = client.post("/api/v1/templates", json=template)
    assert resp.status_code == 201

    # Compare two papers using real samples
    pdf_content1 = (SAMPLES_DIR / "template.pdf").read_bytes()
    pdf_content2 = (SAMPLES_DIR / "paper.pdf").read_bytes()

    files = {
        "template": ("template.pdf", pdf_content1, "application/pdf"),
        "paper": ("paper.pdf", pdf_content2, "application/pdf"),
    }
    resp = client.post("/api/v1/compare", files=files)
    assert resp.status_code == 200

    # Check report is persisted
    resp = client.get("/api/v1/reports/paper.pdf")
    assert resp.status_code == 200
    report = resp.json()
    # ComplianceReport doesn't have 'kind' field, it's stored in DB only
    assert "score" in report
    assert report["filename"] == "paper.pdf"


def test_compare_demo_not_persisted():
    client = TestClient(app)
    resp = client.post("/api/v1/compare", data={"demo": "true"})
    assert resp.status_code == 200

    # List should be empty (demo not persisted)
    resp = client.get("/api/v1/reports")
    assert resp.json() == {"reports": []}


def test_submission_metadata_in_report():
    client = TestClient(app)

    # Create a template first
    template = {
        "name": "Test Template",
        "document": {
            "page_size": "a4",
            "margins_pt": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "columns": 1,
        },
        "typography": {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5},
    }
    resp = client.post("/api/v1/templates", json=template)
    assert resp.status_code == 201
    template_id = resp.json()["template_id"]

    # Submit a paper
    pdf_content = (SAMPLES_DIR / "paper.pdf").read_bytes()
    files = {"files": ("test_paper.pdf", pdf_content, "application/pdf")}
    data = {"template_id": template_id}
    resp = client.post("/api/v1/submissions", files=files, data=data)
    assert resp.status_code == 200
    report = resp.json()

    # Check metadata field exists
    assert "papers" in report
    assert len(report["papers"]) == 1
    paper = report["papers"][0]
    assert "metadata" in paper
    assert "title" in paper["metadata"]
    assert "authors" in paper["metadata"]
    assert isinstance(paper["metadata"]["authors"], list)