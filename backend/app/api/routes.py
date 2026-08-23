import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.comparator.comparator import run_comparison
from app.demo.sample_pdfs import demo_documents
from app.models.report import ComplianceReport
from app.parsing.pdf_parser import PdfParseError, parse_pdf
from app.parsing.pipeline import compare_documents, normalize_pdf
from app.parsing.template_analyzer import analyze_template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "parser": "pymupdf"}


async def _read_pdf(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data:
        raise PdfParseError(f"Uploaded file '{upload.filename}' is empty.")
    return data


@router.post("/parse")
async def parse(file: UploadFile = File(...)) -> dict:
    try:
        data = await _read_pdf(file)
        normalized = normalize_pdf(data)
    except PdfParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while parsing PDF")
        raise HTTPException(status_code=500, detail="Internal error while parsing PDF.") from None
    return {"filename": file.filename, "normalized": normalized.model_dump()}


@router.post("/compare", response_model=ComplianceReport)
async def compare(
    template: UploadFile | None = File(default=None),
    paper: UploadFile | None = File(default=None),
    demo: bool = Form(False),
) -> ComplianceReport:
    if demo:
        template_data, paper_data = demo_documents()
        rules = analyze_template(normalize_pdf(template_data))
        report = run_comparison(rules, normalize_pdf(paper_data))
        return report

    if template is None or paper is None:
        raise HTTPException(
            status_code=422,
            detail="Upload both 'template' and 'paper' PDF files (or send demo=true).",
        )
    try:
        template_data, paper_data = await _read_pdf(template), await _read_pdf(paper)
        return compare_documents(template_data, paper_data)
    except PdfParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error during comparison")
        raise HTTPException(
            status_code=500, detail="Internal error while comparing documents."
        ) from None
