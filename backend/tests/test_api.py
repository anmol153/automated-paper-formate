import pytest
from fastapi.testclient import TestClient

from app.demo.sample_docx import demo_docx
from app.demo.sample_latex import latex_documents
from app.demo.sample_pdfs import demo_documents
from app.main import create_app

PDF_PART = ("application/pdf",)


@pytest.fixture()
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def pdf_files():
    template_bytes, paper_bytes = demo_documents()
    return template_bytes, paper_bytes


@pytest.fixture(scope="module")
def latex_files():
    template, paper = latex_documents()
    return template.encode("utf-8"), paper.encode("utf-8")


@pytest.fixture(scope="module")
def docx_files():
    return demo_docx()


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_compare_with_uploads(client, pdf_files):
    template_bytes, paper_bytes = pdf_files
    response = client.post(
        "/api/v1/compare",
        files={
            "template": ("template.pdf", template_bytes, *PDF_PART),
            "paper": ("paper.pdf", paper_bytes, *PDF_PART),
        },
    )
    assert response.status_code == 200
    report = response.json()

    for field in ("score", "passed", "failed", "missing", "results"):
        assert field in report
    total = report["passed"] + report["failed"] + report["missing"]
    assert total == len(report["results"])
    expected_score = round(100 * report["passed"] / total) if total else 0
    assert report["score"] == expected_score


def test_compare_demo(client):
    response = client.post("/api/v1/compare", data={"demo": "true"})
    assert response.status_code == 200
    report = response.json()
    assert report["missing"] >= 2
    assert any(r["status"] == "missing" for r in report["results"])


def test_compare_requires_both_files(client):
    response = client.post("/api/v1/compare")
    assert response.status_code == 422


def test_compare_rejects_invalid_pdf(client, pdf_files):
    _, paper_bytes = pdf_files
    response = client.post(
        "/api/v1/compare",
        files={
            "template": ("broken.pdf", b"not a pdf at all", *PDF_PART),
            "paper": ("paper.pdf", paper_bytes, *PDF_PART),
        },
    )
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


def test_parse_single_file(client, pdf_files):
    template_bytes, _ = pdf_files
    response = client.post(
        "/api/v1/parse",
        files={"file": ("template.pdf", template_bytes, *PDF_PART)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "template.pdf"
    assert body["normalized"]["document"]["page_size"]["label"] == "A4"


def test_parse_latex_file(client, latex_files):
    template_bytes, _ = latex_files
    response = client.post(
        "/api/v1/parse",
        files={"file": ("template.tex", template_bytes, "application/x-tex")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "latex"
    assert body["normalized"]["document"]["page_size"]["label"] == "A4"
    assert body["normalized"]["document"]["columns"] == 2


def test_parse_docx_file(client, docx_files):
    template_bytes, _ = docx_files
    response = client.post(
        "/api/v1/parse",
        files={"file": ("template.docx", template_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "docx"
    assert body["normalized"]["document"]["page_size"]["label"] == "A4"


def test_compare_mixed_formats(client, latex_files, docx_files):
    template_bytes, _ = latex_files
    paper_template_bytes, paper_bytes = docx_files
    response = client.post(
        "/api/v1/compare",
        files={
            "template": ("template.tex", template_bytes, "application/x-tex"),
            "paper": ("paper.docx", paper_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        },
    )
    assert response.status_code == 200
    report = response.json()
    for field in ("score", "passed", "failed", "missing", "results"):
        assert field in report
    total = report["passed"] + report["failed"] + report["missing"]
    assert total == len(report["results"])
    assert report["meta"]["paper_title"] == "Deep Learning for Format Compliance Checking"


def test_compare_rejects_invalid_tex(client):
    response = client.post(
        "/api/v1/compare",
        files={
            "template": ("template.pdf", b"not a pdf", *PDF_PART),
            "paper": ("paper.tex", b"\\documentclass{article}", "application/x-tex"),
        },
    )
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()
