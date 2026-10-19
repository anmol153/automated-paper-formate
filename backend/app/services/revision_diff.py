"""Read-only comparisons of immutable paper files and saved check snapshots."""
import difflib
import hashlib
import json
import logging

from fastapi import HTTPException

from app.parsing.errors import ParseError
from app.parsing.pipeline import normalize_document
from app.parsing.pdf_parser import MAX_PAGES
from app.security.files import PrivateFiles, validate_document

logger = logging.getLogger(__name__)
TEXT_EXTRACTOR_VERSION = "normalized-document-diff-1"
MAX_TEXT_CHARS = 100_000
MAX_TEXT_LINES = 1500
MAX_LINE_CHARS = 2000
MAX_HUNKS = 100

# Compare only facts already extracted by the checker. Empty/unknown values remain
# visible as evidence; absence of evidence is never a numeric zero or a resolution.
PROPERTY_FIELDS = (
    ("layout.page_count", "Page count"),
    ("layout.page_count_exact", "Exact page count"),
    ("layout.page_count_confidence", "Page count confidence"),
    ("layout.page_size_label", "Page size"),
    ("layout.columns", "Columns"),
    ("layout.margins_pt", "Margins (pt)"),
    ("layout.margins_confidence", "Margins confidence"),
    ("typography.body_font", "Body font"),
    ("typography.body_font_size_pt", "Body font size (pt)"),
    ("structure.title_text", "Extracted title"),
    ("structure.author_block_text", "Extracted author block"),
    ("structure.sections_present", "Detected sections"),
    ("structure.headings", "Detected headings"),
    ("structure.reference_entry_count", "Reference entries"),
    ("structure.reference_count_confidence", "Reference count confidence"),
    ("structure.total_word_count", "Extracted words"),
    ("assets.figures", "Detected figures"),
    ("assets.tables", "Detected tables"),
    ("assets.confidence", "Asset count confidence"),
    ("identity.acknowledgement_present", "Detected acknowledgements"),
    ("latex.document_class", "LaTeX document class"),
)


def _value(facts, path):
    value = facts
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def compare_properties(base, target):
    before = (base or {}).get("assessment") or {}
    after = (target or {}).get("assessment") or {}
    left, right = before.get("facts"), after.get("facts")
    if not left or not right:
        return {"status": "unavailable", "reason": "Both selected reports need extracted facts.", "fields": []}
    fields = []
    for key, label in PROPERTY_FIELDS:
        old, new = _value(left, key), _value(right, key)
        # Missing values must not look like a measured change.
        state = "unavailable" if old is None or new is None else "unchanged" if old == new else "changed"
        fields.append({"key": key, "label": label, "before": old, "after": new, "state": state})
    return {"status": "available", "fields": fields,
            "base_parser": left.get("parser"), "target_parser": right.get("parser"),
            "base_warnings": left.get("parse_warnings", []), "target_warnings": right.get("parse_warnings", [])}


def compare_findings(base, target, *, same_rules):
    result = {"status": "unavailable", "findings": [], "summary": {}, "warnings": []}
    if not base or not target or not base.get("assessment") or not target.get("assessment"):
        result["reason"] = "Both selected checks must have completed assessments; failed attempts are not passes."
        return result
    if not same_rules:
        result["warnings"].append("Template rules differ; finding changes may reflect different requirements.")
    if base["engine_version"] != target["engine_version"]:
        result["warnings"].append("Checker versions differ; changes may reflect extraction or rule-engine changes.")
    if base["assessment"].get("format") != target["assessment"].get("format"):
        result["warnings"].append("Document formats differ; their measurable properties may differ.")
    maps = []
    for check in (base, target):
        rules = check["assessment"].get("results", [])
        ids = [r.get("id") for r in rules]
        if any(not i for i in ids) or len(ids) != len(set(ids)):
            result["reason"] = "These reports lack unique stable rule IDs; findings cannot be matched reliably."
            return result
        maps.append({r["id"]: r for r in rules})
    left, right = maps
    summary = {key: 0 for key in ("resolved", "newly_reported", "remaining", "not_evaluated")}
    for rule_id in sorted(left.keys() | right.keys()):
        old, new = left.get(rule_id), right.get(rule_id)
        old_issue = old is not None and old["status"] in {"failed", "missing"}
        new_issue = new is not None and new["status"] in {"failed", "missing"}
        if not old_issue and not new_issue:
            continue
        if old_issue and new_issue:
            state = "remaining"
        elif new_issue:
            state = "newly_reported"
        elif new is not None and new["status"] == "passed":
            state = "resolved"
        else:
            state = "not_evaluated"
        summary[state] += 1
        result["findings"].append({
            "rule_id": rule_id, "state": state, "before": old, "after": new,
            "changed_fields": [key for key in ("status", "severity", "expected", "actual", "confidence")
                               if old is not None and new is not None and old.get(key) != new.get(key)],
            "base_issue_ids": [i["issue_id"] for i in base.get("issues", []) if i["rule_id"] == rule_id],
            "target_issue_ids": [i["issue_id"] for i in target.get("issues", []) if i["rule_id"] == rule_id],
        })
    result.update(status="available", summary=summary,
                  base_status=base["status"], target_status=target["status"],
                  base_score=base["assessment"].get("score"), target_score=target["assessment"].get("score"))
    return result


def _read_file(root, revision):
    files = PrivateFiles(root)
    path = files.verified(revision["storage_key"], revision["sha256"], revision["size_bytes"])
    data = path.read_bytes()
    if len(data) != revision["size_bytes"] or hashlib.sha256(data).hexdigest() != revision["sha256"]:
        raise HTTPException(status_code=409, detail="Stored file failed its integrity check")
    return data


def _lines(doc):
    # Normalized reading-order text, not source-code, layout or semantic comparison.
    text = doc.full_text().replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > MAX_TEXT_CHARS:
        return None
    lines = text.splitlines()
    if len(lines) > MAX_TEXT_LINES or any(len(line) > MAX_LINE_CHARS for line in lines):
        return None
    return lines


def compare_text(root, base, target):
    result = {"status": "unavailable", "extractor_version": TEXT_EXTRACTOR_VERSION, "hunks": []}
    try:
        before, after = _read_file(root, base), _read_file(root, target)
        formats = (validate_document(before, base["filename"]), validate_document(after, target["filename"]))
        docs = (normalize_document(before, base["filename"]), normalize_document(after, target["filename"]))
        if any(fmt == "pdf" and doc.document.page_count > MAX_PAGES for fmt, doc in zip(formats, docs)):
            result.update(status="limit_exceeded", reason=f"The PDF text parser reads at most {MAX_PAGES} pages. Download the files to compare the complete documents.")
            return result
        left, right = (_lines(doc) for doc in docs)
    except (HTTPException, OSError, ParseError):
        result["reason"] = "A retained file is unavailable, failed integrity validation, or could not be parsed. Saved report comparisons remain available."
        return result
    except Exception:
        logger.exception("Revision text comparison failed")
        result["reason"] = "Text extraction failed. Saved report comparisons remain available."
        return result
    if left is None or right is None:
        result.update(status="limit_exceeded", reason="Text exceeds the comparison limit (100,000 characters, 1,500 lines, or 2,000 characters per line). Download the files for comparison.")
        return result
    if not any(s.strip() for s in left) or not any(s.strip() for s in right):
        result["reason"] = "Both revisions need extractable text. Scanned or image-only documents may require OCR, which is not available."
        return result
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=True)
    groups = list(matcher.get_grouped_opcodes(n=3))
    if len(groups) > MAX_HUNKS:
        result.update(status="limit_exceeded", reason="Too many separate text changes to display. Download the files for comparison.")
        return result
    added = deleted = 0
    for group in groups:
        lines = []
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                lines.extend({"kind": "context", "base_line": i + 1, "target_line": j + 1, "text": left[i]}
                             for i, j in zip(range(i1, i2), range(j1, j2)))
            else:
                if tag in {"delete", "replace"}:
                    deleted += i2 - i1
                    lines.extend({"kind": "removed", "base_line": i + 1, "target_line": None, "text": left[i]}
                                 for i in range(i1, i2))
                if tag in {"insert", "replace"}:
                    added += j2 - j1
                    lines.extend({"kind": "added", "base_line": None, "target_line": j + 1, "text": right[j]}
                                 for j in range(j1, j2))
        result["hunks"].append({"base_start": group[0][1] + 1, "target_start": group[0][3] + 1, "lines": lines})
    result.update(status="available", identical=left == right, added_lines=added, removed_lines=deleted,
                  base_lines=len(left), target_lines=len(right))
    return result


def same_rules(base, target):
    return json.loads(base["rules_json"]) == json.loads(target["rules_json"])
