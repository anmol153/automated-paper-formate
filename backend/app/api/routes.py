import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.checks.engine import assess
from app.checks.submission import MAX_BATCH_SIZE, assess_batch
from app.comparator.comparator import run_comparison
from app.demo.sample_pdfs import demo_documents
from app.google.docs_client import GoogleAuthError, auth_mode
from app.google.drive_client import (
    DOWNLOADABLE_EXTENSIONS,
    DriveNotConfigured,
    download,
    extract_folder_id,
    list_folder,
    select_papers,
)
from app.google.url_parser import extract_doc_id
from app.models.report import ComplianceReport, SubmissionReport
from app.models.rules import RuleSet
from app.parsing.errors import ParseError
from app.parsing.fact_extractor import build_facts
from app.parsing.pipeline import (
    SUPPORTED_FORMATS,
    compare_files,
    format_of,
    normalize_document,
    sniff_format,
)
from app.parsing.rule_inference import infer_ruleset_from_template, rule_schema
from app.parsing.template_analyzer import analyze_template
from app.storage.report_store import ReportNotFound, get_report_store
from app.storage.template_store import TemplateNotFound, get_store

logger = logging.getLogger(__name__)

ACCEPTED_FORMATS = "PDF (.pdf), LaTeX (.tex) and Word (.docx)"

router = APIRouter(prefix="/api/v1")


# --------------------------------------------------------------------------- #
# request models
# --------------------------------------------------------------------------- #


class DriveSubmissionRequest(BaseModel):
    folder_url: str
    template_id: Optional[str] = None
    rules: Optional[RuleSet] = None
    recursive: bool = True


class DrivePreviewRequest(BaseModel):
    folder_url: str
    recursive: bool = True


class GoogleDocRequest(BaseModel):
    document_url: str
    template_id: Optional[str] = None
    rules: Optional[RuleSet] = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


async def _read_file(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data:
        raise ParseError(f"Uploaded file '{upload.filename}' is empty.")
    return data


def _load_rules(template_id: Optional[str], inline: Optional[RuleSet]) -> RuleSet:
    if inline is not None:
        return inline
    if not template_id:
        raise HTTPException(
            status_code=422,
            detail="Provide 'template_id' (a configured publisher template) or an inline "
            "'rules' object so the system knows which rules to enforce.",
        )
    try:
        return get_store().get(template_id)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _drive_unavailable(exc: Exception) -> HTTPException:
    """Map a Drive failure to the right status for the caller.

    A malformed link is the caller's mistake (400); missing server credentials
    is an operator problem (503); anything from the Drive API keeps its own code.
    """
    if isinstance(exc, DriveNotConfigured):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    status = getattr(exc, "status_code", 502)
    return HTTPException(status_code=status, detail=str(exc))


# --------------------------------------------------------------------------- #
# health + rule schema
# --------------------------------------------------------------------------- #


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "parsers": list(SUPPORTED_FORMATS),
        "google_auth": auth_mode(),
        "supported_formats": [f".{f}" for f in SUPPORTED_FORMATS],
    }


@router.get("/rule-schema")
def get_rule_schema() -> dict:
    """Field list + publisher presets that drive the rule editor UI."""
    return rule_schema()


# --------------------------------------------------------------------------- #
# publisher template management (conference-manager setup)
# --------------------------------------------------------------------------- #


@router.get("/templates")
def list_templates() -> dict:
    templates = get_store().list()
    return {
        "count": len(templates),
        "templates": [t.model_dump() for t in templates],
    }


@router.post("/templates/import", response_model=RuleSet)
async def import_template(
    file: UploadFile = File(...),
    name: str = Form(""),
) -> RuleSet:
    """Parse an uploaded template and return the rules inferred from it.

    This is a preview: nothing is persisted until the manager edits the returned
    rules and POSTs to /templates. That keeps "import" and "override" separate
    steps the manager can see.
    """
    try:
        data = await _read_file(file)
        doc = normalize_document(data, file.filename)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while importing a template")
        raise HTTPException(
            status_code=500, detail="Internal error while reading the template."
        ) from None

    rules = infer_ruleset_from_template(doc, file.filename or "template")
    if name.strip():
        rules.name = name.strip()
    return rules


@router.post("/templates", response_model=RuleSet, status_code=201)
def create_template(rules: RuleSet) -> RuleSet:
    """Persist a rule set as a selectable publisher template."""
    if not rules.name.strip() or rules.name == "Untitled template":
        raise HTTPException(status_code=422, detail="A template name is required.")
    return get_store().create(rules)


@router.get("/templates/{template_id}", response_model=RuleSet)
def get_template(template_id: str) -> RuleSet:
    try:
        return get_store().get(template_id)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/templates/{template_id}", response_model=RuleSet)
def update_template(template_id: str, rules: RuleSet) -> RuleSet:
    try:
        existing = get_store().get(template_id)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rules.template_id = existing.template_id
    return get_store().save(rules)


@router.delete("/templates/{template_id}")
def delete_template(template_id: str) -> dict:
    try:
        get_store().delete(template_id)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": template_id}


# --------------------------------------------------------------------------- #
# single-document parse + legacy template comparison
# --------------------------------------------------------------------------- #


@router.post("/parse")
async def parse(file: UploadFile = File(...)) -> dict:
    try:
        data = await _read_file(file)
        fmt = sniff_format(data, file.filename)
        normalized = normalize_document(data, file.filename)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while parsing document")
        raise HTTPException(
            status_code=500, detail="Internal error while parsing document."
        ) from None
    return {
        "filename": file.filename,
        "format": fmt,
        "extension": format_of(file.filename),
        "normalized": normalized.model_dump(),
    }


@router.post("/compare", response_model=ComplianceReport)
async def compare(
    template: UploadFile | None = File(default=None),
    paper: UploadFile | None = File(default=None),
    demo: bool = Form(False),
) -> ComplianceReport:
    if demo:
        template_data, paper_data = demo_documents()
        template_doc = normalize_document(template_data, "template.pdf")
        return run_comparison(analyze_template(template_doc), normalize_document(paper_data, "paper.pdf"))

    if template is None or paper is None:
        raise HTTPException(
            status_code=422,
            detail=f"Upload both 'template' and 'paper' files ({ACCEPTED_FORMATS}), or send demo=true.",
        )
    try:
        template_data = await _read_file(template)
        paper_data = await _read_file(paper)
        report = compare_files(
            template_data,
            template.filename,
            paper_data,
            paper.filename,
        )
        # Persist non-demo comparisons
        if not demo:
            try:
                get_report_store().save(
                    filename=paper.filename or "paper",
                    report=report.model_dump(),
                    kind="comparison",
                )
            except Exception:
                logger.exception("Failed to persist comparison report")
        return report
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error during comparison")
        raise HTTPException(
            status_code=500, detail="Internal error while comparing documents."
        ) from None


# --------------------------------------------------------------------------- #
# batch submission
# --------------------------------------------------------------------------- #


@router.post("/submissions", response_model=SubmissionReport)
async def submit_papers(
    files: list[UploadFile] = File(...),
    template_id: Optional[str] = Form(None),
    rules: Optional[str] = Form(None),
) -> SubmissionReport:
    """Check one or many uploaded papers against a publisher template.

    Accepts any number of files in a single request, so a batch of 40 papers is
    one call rather than 40. ``rules`` may carry an inline JSON rule set for
    callers that have not saved a template yet.
    """
    inline: Optional[RuleSet] = None
    if rules:
        try:
            inline = RuleSet.model_validate(json.loads(rules))
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"'rules' is not a valid rule set: {exc}"
            ) from exc

    active = _load_rules(template_id, inline)

    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"{len(files)} files submitted; the maximum batch size is {MAX_BATCH_SIZE}.",
        )

    papers: list[tuple[str, bytes]] = []
    for upload in files:
        data = await upload.read()
        papers.append((upload.filename or "unnamed", data))

    if not papers:
        raise HTTPException(status_code=422, detail="No files were uploaded.")

    report = assess_batch(active, papers, source="upload")

    # Persist each paper's report keyed by filename
    try:
        store = get_report_store()
        for paper_assessment in report.papers:
            single_report = SubmissionReport(
                template_id=report.template_id,
                template_name=report.template_name,
                publisher=report.publisher,
                source=report.source,
                papers=[paper_assessment],
                accepted=1 if paper_assessment.verdict == "accepted" else 0,
                rejected=1 if paper_assessment.verdict == "rejected" else 0,
                needs_review=1 if paper_assessment.verdict == "needs_review" else 0,
                generated_at=report.generated_at,
            )
            store.save(
                filename=paper_assessment.filename,
                report=single_report.model_dump(),
                kind="submission",
            )
    except Exception:
        logger.exception("Failed to persist submission reports")

    return report


@router.post("/submissions/drive", response_model=SubmissionReport)
def submit_from_drive(request: DriveSubmissionRequest) -> SubmissionReport:
    """Fetch every paper in a Google Drive folder and check them in one batch."""
    rules = _load_rules(request.template_id, request.rules)
    try:
        folder_id = extract_folder_id(request.folder_url)
        listing = list_folder(folder_id, recursive=request.recursive)
    except (ValueError, DriveNotConfigured) as exc:
        raise _drive_unavailable(exc) from exc
    except Exception as exc:
        if isinstance(exc, Exception) and getattr(exc, "status_code", None):
            raise _drive_unavailable(exc) from exc
        raise

    accepted = tuple(rules.accepted_extension_list()) or DOWNLOADABLE_EXTENSIONS
    candidates = select_papers(listing, accepted)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No files in that folder are in an accepted format "
                f"({', '.join('.' + e for e in accepted)}). Found "
                f"{len(listing)} item(s) in the folder."
            ),
        )

    papers: list[tuple[str, bytes]] = []
    errors: list[str] = []
    for drive_file in candidates:
        try:
            name, data = download(drive_file, target_extension="pdf" if drive_file.is_google_doc else None)
            papers.append((name, data))
        except Exception as exc:
            errors.append(f"{drive_file.name}: {exc}")

    if not papers:
        raise HTTPException(
            status_code=502,
            detail="No file in the folder could be downloaded. " + " | ".join(errors[:5]),
        )
    if errors:
        logger.warning("Skipped %d Drive file(s): %s", len(errors), errors[:5])

    report = assess_batch(rules, papers, source="google-drive")

    # Persist each paper's report keyed by filename
    try:
        store = get_report_store()
        for paper_assessment in report.papers:
            single_report = SubmissionReport(
                template_id=report.template_id,
                template_name=report.template_name,
                publisher=report.publisher,
                source=report.source,
                papers=[paper_assessment],
                accepted=1 if paper_assessment.verdict == "accepted" else 0,
                rejected=1 if paper_assessment.verdict == "rejected" else 0,
                needs_review=1 if paper_assessment.verdict == "needs_review" else 0,
                generated_at=report.generated_at,
            )
            store.save(
                filename=paper_assessment.filename,
                report=single_report.model_dump(),
                kind="submission",
            )
    except Exception:
        logger.exception("Failed to persist drive submission reports")

    return report


@router.post("/submissions/google-doc", response_model=SubmissionReport)
def submit_from_google_doc(request: GoogleDocRequest) -> SubmissionReport:
    """Check a single Google Doc by URL (exported to PDF first)."""
    from app.google.docs_client import fetch_document
    from app.parsing.normalizer import parse_google_doc

    rules = _load_rules(request.template_id, request.rules)
    try:
        doc_id = extract_doc_id(request.document_url)
        remote = fetch_document(doc_id)
    except (ValueError, GoogleAuthError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        status = getattr(exc, "status_code", 502)
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    normalized = parse_google_doc(remote)
    title = remote.get("title") or "google-doc"
    facts = build_facts(
        title.encode("utf-8"), f"{title}.gdoc", normalized, "docx"
    )
    assessment = assess(rules, facts)
    report = SubmissionReport(
        template_id=rules.template_id,
        template_name=rules.name,
        publisher=rules.publisher,
        source="google-doc",
        papers=[assessment],
        accepted=1 if assessment.verdict == "accepted" else 0,
        rejected=1 if assessment.verdict == "rejected" else 0,
        needs_review=1 if assessment.verdict == "needs_review" else 0,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    # Persist the single paper report
    try:
        get_report_store().save(
            filename=assessment.filename,
            report=report.model_dump(),
            kind="submission",
        )
    except Exception:
        logger.exception("Failed to persist google-doc submission report")

    return report


# --------------------------------------------------------------------------- #
# Report history
# --------------------------------------------------------------------------- #


@router.get("/reports")
def list_reports() -> dict:
    """List all stored reports, most recent first."""
    try:
        reports = get_report_store().list()
        return {"reports": reports}
    except Exception:
        logger.exception("Failed to list reports")
        raise HTTPException(status_code=500, detail="Failed to list reports.") from None


@router.get("/reports/{filename:path}")
def get_report(filename: str) -> dict:
    """Get a full stored report by filename."""
    try:
        report = get_report_store().get(filename)
        return report
    except ReportNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception("Failed to get report")
        raise HTTPException(status_code=500, detail="Failed to get report.") from None


@router.delete("/reports/{filename:path}")
def delete_report(filename: str) -> dict:
    """Delete a stored report by filename."""
    try:
        get_report_store().delete(filename)
        return {"deleted": filename}
    except ReportNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception("Failed to delete report")
        raise HTTPException(status_code=500, detail="Failed to delete report.") from None


@router.get("/drive/status")
def drive_status() -> dict:
    return {
        "configured": auth_mode() != "not-configured",
        "auth_mode": auth_mode(),
        "instructions": (
            None
            if auth_mode() != "not-configured"
            else "Add backend/credentials/service_account.json (Drive read-only scope) or set "
            "GOOGLE_API_KEY, then share the folder with the service account."
        ),
    }


@router.post("/drive/preview")
def drive_preview(request: DrivePreviewRequest) -> dict:
    """List what a Drive folder contains, so a submitter can confirm before checking."""
    try:
        folder_id = extract_folder_id(request.folder_url)
        listing = list_folder(folder_id, recursive=request.recursive)
    except (ValueError, DriveNotConfigured) as exc:
        raise _drive_unavailable(exc) from exc

    candidates = select_papers(listing)
    return {
        "folder_id": folder_id,
        "total_items": len(listing),
        "usable_papers": len(candidates),
        "skipped": [f.as_dict() for f in listing if f not in candidates],
        "files": [f.as_dict() for f in candidates],
    }


__all__ = ["router"]
