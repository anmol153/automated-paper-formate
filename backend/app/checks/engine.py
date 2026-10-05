"""Rule engine: evaluates a ``PaperFacts`` record against a ``RuleSet``.

Every rule produces exactly one ``CheckResult`` whose ``id`` is stable, so
results can be diffed across runs and mapped to the rule editor UI. Rules that
are switched off, or whose underlying fact is unmeasurable for the submitted
format, produce ``not_applicable`` and are excluded from the score rather than
counting as failures.
"""

from __future__ import annotations


from typing import Any, Optional

from app.checks.anonymisation import check_anonymisation, score_anonymisation
from app.models.facts import PaperFacts
from app.models.report import CheckResult, PaperAssessment, PaperMetadata
from app.models.rules import RuleSet, Severity
from app.parsing.normalizer import page_size_label
from app.parsing.structure import match_canonical_section

_STANDARD_DIMENSIONS = {
    "a4": (595.28, 841.89),
    "a5": (419.53, 595.28),
    "letter": (612.0, 792.0),
    "legal": (612.0, 1008.0),
    "tabloid": (792.0, 1224.0),
    "executive": (522.0, 756.0),
}


def _fmt_pt(value: Optional[float]) -> Optional[str]:
    return f"{value:g} pt" if value is not None else None


def _norm_font(name: Optional[str]) -> str:
    return " ".join((name or "").split()).casefold()


def _check(
    rule_id: str,
    name: str,
    status: str,
    severity: Severity,
    expected: Any = None,
    actual: Any = None,
    advice: Optional[str] = None,
    evidence: Optional[str] = None,
    confidence: str = "high",
) -> CheckResult:
    return CheckResult(
        id=rule_id,
        name=name,
        category=_CATEGORY_OF.get(rule_id.split(".")[0], "policy"),
        status=status,
        severity=severity,
        expected=expected,
        actual=actual,
        rule=rule_id,
        advice=advice,
        evidence=evidence,
        confidence=confidence,
    )


_CATEGORY_OF = {
    "file": "file",
    "page": "page",
    "layout": "layout",
    "typography": "typography",
    "paragraph": "paragraph",
    "structure": "structure",
    "anonymisation": "anonymisation",
    "policy": "policy",
}


def _na(rule_id: str, name: str, note: str) -> CheckResult:
    return _check(rule_id, name, "not_applicable", Severity.ADVISORY, "n/a", "n/a", evidence=note)


# --------------------------------------------------------------------------- #
# file rules
# --------------------------------------------------------------------------- #


def _check_file(rules: RuleSet, facts: PaperFacts) -> list[CheckResult]:
    out: list[CheckResult] = []
    file_rule = rules.file_type
    ext = facts.file.extension

    if not ext:
        status = "failed" if file_rule.reject_if_extension_missing else "passed"
        out.append(
            _check(
                "file.extension_present",
                "File has an extension",
                status,
                Severity.BLOCKING,
                "A file extension (for example .pdf)",
                "No extension found",
                advice=f"'{facts.file.filename}' has no file extension, so its type cannot be "
                "verified. Rename the file with the correct extension and re-upload.",
            )
        )
    else:
        accepted = file_rule.accepts(ext)
        if accepted:
            out.append(_check("file.extension_present", "File has an extension", "passed", Severity.BLOCKING, ext, ext))
        else:
            severity = Severity.BLOCKING if file_rule.reject_if_extension_not_accepted else Severity.WARNING
            allowed = ", ".join(rules.accepted_extension_list())
            out.append(
                _check(
                    "file.extension_accepted",
                    "File type accepted",
                    "failed",
                    severity,
                    allowed,
                    f".{ext}",
                    advice=f"This template accepts {allowed}. Convert your manuscript to an "
                    f"accepted format and re-upload as '.<ext>'.",
                    evidence=f"filename={facts.file.filename}",
                )
            )

    if file_rule.max_file_size_mb is not None and file_rule.max_file_size_mb > 0:
        limit = file_rule.max_file_size_mb * 1_048_576
        size = facts.file.size_bytes
        ok = size <= limit
        out.append(
            _check(
                "file.size",
                "File size within limit",
                "passed" if ok else "failed",
                Severity.BLOCKING,
                f"<= {file_rule.max_file_size_mb:g} MB",
                f"{size / 1_048_576:.2f} MB",
                advice=(None if ok else
                        f"Your file is {size / 1_048_576:.2f} MB, above the "
                        f"{file_rule.max_file_size_mb:g} MB limit. Reduce image resolution or "
                        "compress the PDF."),
                evidence=f"{size} bytes",
            )
        )

    if not file_rule.allow_source_upload and facts.file.format in ("latex", "docx"):
        out.append(
            _check(
                "file.source_allowed",
                "Source files accepted",
                "failed",
                Severity.BLOCKING,
                "PDF only",
                f".{facts.file.extension}",
                advice="This template accepts PDF submissions only. Export your manuscript "
                "to PDF and upload that instead.",
            )
        )

    if file_rule.require_source_when_pdf_given and facts.file.format == "pdf":
        out.append(
            _na(
                "file.source_required",
                "Source file supplied",
                "Source requirement is enforced per-submission, not per-paper.",
            )
        )

    return out


# --------------------------------------------------------------------------- #
# page + layout rules
# --------------------------------------------------------------------------- #


def _check_pages(rules: RuleSet, facts: PaperFacts) -> list[CheckResult]:
    out: list[CheckResult] = []
    page_rule = rules.pages
    count = facts.layout.page_count

    if page_rule.max_pages is None and page_rule.min_pages is None:
        out.append(_na("page.limit", "Page limit", "No page limit configured for this template."))
    elif count is None:
        out.append(_na("page.limit", "Page limit", "Page count could not be determined."))
    else:
        exact = facts.layout.page_count_exact
        tolerance = 0 if exact else max(0, page_rule.estimate_tolerance_pages)
        limit = page_rule.max_pages
        passed = True
        advice = None
        expected_desc: Any = None
        if limit is not None:
            expected_desc = f"<= {limit} page(s)"
            if count > limit + tolerance:
                passed = False
                over = count - limit
                advice = (
                    f"Your paper is {count} pages, which exceeds the {limit}-page limit by {over} "
                    f"page(s). Shorten the text, move material to a supplementary appendix, or "
                    f"reduce figure and table sizes."
                )
        if passed and page_rule.min_pages is not None:
            expected_desc = (
                f"<= {limit} page(s)" if limit is not None else f">= {page_rule.min_pages} page(s)"
            )
            if count < max(1, page_rule.min_pages - tolerance):
                passed = False
                advice = (
                    f"Your paper is {count} pages, below the {page_rule.min_pages}-page minimum."
                )
        confidence_note = None if exact else (
            f"Page count is an estimate for {facts.file.format.upper()} sources; "
            f"a tolerance of {tolerance} page(s) is applied."
        )
        out.append(
            _check(
                "page.limit",
                "Page limit",
                "passed" if passed else "failed",
                Severity.BLOCKING,
                expected_desc,
                f"{count} page(s)" + ("" if exact else " (estimated)"),
                advice=advice,
                evidence=confidence_note,
                confidence="exact" if exact else "medium",
            )
        )

    if page_rule.page_size_label:
        actual_label = facts.layout.page_size_label or (
            f"{facts.layout.width_pt:g} x {facts.layout.height_pt:g} pt"
            if facts.layout.width_pt and facts.layout.height_pt
            else "unknown"
        )
        std = _STANDARD_DIMENSIONS.get(page_rule.page_size_label.strip().casefold())
        matched = _norm_font(page_rule.page_size_label) == _norm_font(actual_label)
        if not matched and std and facts.layout.width_pt and facts.layout.height_pt:
            matched = (
                abs(facts.layout.width_pt - std[0]) <= 2
                and abs(facts.layout.height_pt - std[1]) <= 2
            )
        out.append(
            _check(
                "layout.page_size",
                "Page size",
                "passed" if matched else "failed",
                Severity.BLOCKING,
                page_rule.page_size_label,
                actual_label,
                advice=(None if matched else
                        f"Set the page size to {page_rule.page_size_label}. Your manuscript uses "
                        f"{actual_label}."),
            )
        )
    else:
        out.append(_na("layout.page_size", "Page size", "No page size rule configured."))

    if page_rule.orientation:
        matched = page_rule.orientation == facts.layout.orientation
        out.append(
            _check(
                "layout.orientation",
                "Orientation",
                "passed" if matched else "failed",
                Severity.BLOCKING,
                page_rule.orientation.title(),
                facts.layout.orientation.title(),
                advice=(None if matched else
                        f"Set the page orientation to {page_rule.orientation}; your manuscript is "
                        f"{facts.layout.orientation}."),
            )
        )
    else:
        out.append(_na("layout.orientation", "Orientation", "No orientation rule configured."))

    if page_rule.columns is not None:
        matched = page_rule.columns == facts.layout.columns
        out.append(
            _check(
                "layout.columns",
                "Column count",
                "passed" if matched else "failed",
                Severity.BLOCKING,
                page_rule.columns,
                facts.layout.columns,
                advice=(None if matched else
                        f"This template requires {page_rule.columns} column(s); your manuscript "
                        f"uses {facts.layout.columns}."),
            )
        )
    else:
        out.append(_na("layout.columns", "Column count", "No column rule configured."))

    if page_rule.margins is not None:
        expected = page_rule.margins
        actual = facts.layout.margins_pt
        if not actual:
            out.append(_na("layout.margins", "Margins", "Margins could not be measured."))
        else:
            tol = page_rule.margin_tolerance_pt
            deltas = {
                side: round(actual.get(side, 0.0) - getattr(expected, f"{side}_pt"), 2)
                for side in ("top", "bottom", "left", "right")
            }
            worst = max(deltas.values(), key=abs)
            matched = abs(worst) <= tol
            out.append(
                _check(
                    "layout.margins",
                    "Margins",
                    "passed" if matched else "failed",
                    Severity.WARNING,
                    {s: _fmt_pt(getattr(expected, f"{s}_pt")) for s in deltas},
                    {s: _fmt_pt(actual.get(s)) for s in deltas},
                    advice=(None if matched else
                            "Set uniform page margins of "
                            f"{_fmt_pt(expected.top_pt)}. Largest deviation: {worst:+g} pt on the "
                            f"{max(deltas, key=lambda k: abs(deltas[k]))} margin."),
                    evidence=f"deviation(pt)={deltas}",
                    confidence=facts.layout.margins_confidence,
                )
            )
    else:
        out.append(_na("layout.margins", "Margins", "No margin rule configured."))

    return out


# --------------------------------------------------------------------------- #
# structure rules
# --------------------------------------------------------------------------- #


def _check_structure(rules: RuleSet, facts: PaperFacts) -> list[CheckResult]:
    out: list[CheckResult] = []
    section_rule = rules.sections
    structure = facts.structure
    present = {h.casefold() for h in structure.sections_present}

    def found(name: str) -> bool:
        if name == "Abstract":
            return structure.has_abstract
        if name == "Keywords":
            return structure.has_keywords
        if name == "Title":
            return structure.title_present
        target = name.casefold()
        if target in present:
            return True
        return any(match_canonical_section(h) == name for h in structure.sections_present)

    out.append(
        _check(
            "structure.title",
            "Title present",
            "passed" if structure.title_present else "missing",
            Severity.BLOCKING,
            "Title",
            "Title present" if structure.title_present else "No title found",
            advice=(None if structure.title_present else
                    "Add a paper title. In LaTeX use \\title{...}; in Word apply the Title style "
                    "to the first paragraph."),
        )
    )

    for name in section_rule.required_sections:
        ok = found(name)
        out.append(
            _check(
                f"structure.section.{name.casefold().replace(' ', '_')}",
                f"Section: {name}",
                "passed" if ok else "missing",
                Severity.BLOCKING,
                f"A '{name}' section",
                "Found" if ok else "Missing",
                advice=(None if ok else
                        f"This template requires a '{name}' section. Add a heading named "
                        f"'{name}' — common synonyms such as "
                        f"{_synonyms_for(name)} are also accepted."),
            )
        )

    for name in section_rule.forbid_sections:
        ok = not found(name)
        out.append(
            _check(
                f"structure.forbid.{name.casefold().replace(' ', '_')}",
                f"Section absent: {name}",
                "passed" if ok else "failed",
                Severity.WARNING,
                f"No '{name}' section",
                f"'{name}' present" if not ok else "Absent",
                advice=(None if ok else
                        f"This template does not accept a '{name}' section. Move that material "
                        "into an appendix or supplementary material."),
            )
        )

    if section_rule.abstract_required:
        out.append(
            _check(
                "structure.abstract",
                "Abstract present",
                "passed" if structure.has_abstract else "missing",
                Severity.BLOCKING,
                "Abstract",
                "Present" if structure.has_abstract else "Missing",
                advice=(None if structure.has_abstract else
                        "Add an abstract. In LaTeX wrap it in \\begin{abstract}...\\end{abstract}."),
            )
        )
    else:
        out.append(_na("structure.abstract", "Abstract present", "Abstract not required."))

    if section_rule.abstract_max_words is not None:
        wc = structure.abstract_word_count
        if wc is None:
            out.append(_na("structure.abstract_length", "Abstract length", "No abstract to measure."))
        else:
            ok = wc <= section_rule.abstract_max_words
            out.append(
                _check(
                    "structure.abstract_length",
                    "Abstract length",
                    "passed" if ok else "failed",
                    Severity.WARNING,
                    f"<= {section_rule.abstract_max_words} words",
                    f"{wc} words",
                    advice=(None if ok else
                            f"Your abstract is {wc} words; the limit is "
                            f"{section_rule.abstract_max_words}. Cut {wc - section_rule.abstract_max_words} "
                            "word(s)."),
                    confidence="low" if structure.abstract_truncated else "high",
                )
            )

    if section_rule.keywords_required:
        ok = structure.has_keywords
        out.append(
            _check(
                "structure.keywords",
                "Keywords present",
                "passed" if ok else "missing",
                Severity.BLOCKING if section_rule.abstract_required else Severity.WARNING,
                "Keywords",
                "Present" if ok else "Missing",
                advice=(None if ok else
                        "Add a keywords line after the abstract. In LaTeX use "
                        "\\begin{keywords}...\\end{keywords}."),
            )
        )
    else:
        out.append(_na("structure.keywords", "Keywords present", "Keywords not required."))

    if section_rule.min_reference_entries is not None:
        count = structure.reference_entry_count
        if count is None:
            out.append(
                _na("structure.references", "Reference count",
                    "No References section was found, so entries could not be counted.")
            )
        else:
            ok = count >= section_rule.min_reference_entries
            out.append(
                _check(
                    "structure.references",
                    "Reference count",
                    "passed" if ok else "failed",
                    Severity.WARNING,
                    f">= {section_rule.min_reference_entries} entries",
                    f"{count} entries",
                    advice=(None if ok else
                            f"{count} reference entries were detected; at least "
                            f"{section_rule.min_reference_entries} are required. Counting is "
                            "heuristic — verify manually before resubmitting."),
                    confidence=structure.reference_count_confidence,
                )
            )

    if section_rule.require_canonical_heading_names:
        offenders = [
            h["name"] for h in structure.headings
            if h.get("name") and not match_canonical_section(h["name"])
        ]
        out.append(
            _check(
                "structure.heading_names",
                "Canonical heading names",
                "passed" if not offenders else "failed",
                Severity.WARNING,
                "Standard section names",
                "Non-standard: " + ", ".join(offenders[:3]) if offenders else "All standard",
                advice=(None if not offenders else
                        "Rename headings to the standard names this template expects, e.g. "
                        + ", ".join(_synonyms_for("Introduction")) + "."),
            )
        )

    return out


def _synonyms_for(name: str) -> str:
    table = {
        "Introduction": "'Introduction' or 'Background'",
        "Related Work": "'Related Work' or 'Literature Review'",
        "Methodology": "'Methodology', 'Method', 'Experimental Setup' or 'Approach'",
        "Results": "'Results', 'Experiments' or 'Evaluation'",
        "Conclusion": "'Conclusion' or 'Conclusions'",
        "References": "'References' or 'Bibliography'",
    }
    return table.get(name, f"'{name}'")


# --------------------------------------------------------------------------- #
# typography rules
# --------------------------------------------------------------------------- #


def _compare_font_attr(
    rule_id: str,
    label: str,
    expected: Any,
    actual: Any,
    matcher,
    advice: str,
) -> CheckResult:
    if expected is None:
        return _na(rule_id, label, f"No {label.lower()} configured.")
    if actual is None:
        return _check(
            rule_id, label, "missing", Severity.WARNING, expected, None,
            advice=f"{label} could not be read from the submitted document. {advice}",
        )
    ok = matcher(expected, actual)
    return _check(
        rule_id, label, "passed" if ok else "failed", Severity.WARNING,
        expected, actual,
        advice=None if ok else f"{label} must be {expected}, but is {actual}. {advice}",
    )


def _typography_element(
    rule_id_prefix: str,
    label: str,
    rule_format,
    facts: PaperFacts,
    tolerance,
    advice_prefix: str,
) -> list[CheckResult]:
    out: list[CheckResult] = []
    if rule_format is None:
        for suffix, attr in (
            ("font_family", "font"),
            ("font_size_pt", "font size"),
            ("bold", "weight"),
            ("alignment", "alignment"),
        ):
            out.append(
                _na(
                    f"{rule_id_prefix}.{suffix}",
                    f"{label} {attr}",
                    f"No {attr} rule configured for the {label.lower()}.",
                )
            )
        return out

    actual_family = None
    actual_size = None
    if rule_id_prefix.startswith("typography.title"):
        actual_family = facts.typography.dominant_font
        actual_size = facts.typography.title_font_size_pt
    elif rule_id_prefix.startswith("typography.heading"):
        actual_family = facts.typography.dominant_font
        actual_size = facts.typography.heading_font_size_pt
    elif rule_id_prefix.startswith("typography.abstract"):
        actual_family = facts.typography.body_font
        actual_size = facts.typography.body_font_size_pt
    else:
        actual_family = facts.typography.body_font
        actual_size = facts.typography.body_font_size_pt

    allowed = tolerance.allowed_font_families
    expected_family = rule_format.font_family
    if allowed:
        matched_family = any(_norm_font(expected_family) == _norm_font(a) for a in allowed) or (
            actual_family is not None and any(_norm_font(actual_family) == _norm_font(a) for a in allowed)
        )
        out.append(
            _check(
                f"{rule_id_prefix}.font_family",
                f"{label} font",
                "passed" if matched_family else "failed",
                Severity.WARNING,
                "One of: " + ", ".join(sorted(allowed)),
                actual_family or "not detected",
                advice=(None if matched_family else
                        f"Use one of the approved fonts: {', '.join(sorted(allowed))}. "
                        f"{advice_prefix}"),
            )
        )
    else:
        out.append(
            _compare_font_attr(
                f"{rule_id_prefix}.font_family",
                f"{label} font",
                expected_family,
                actual_family,
                lambda e, a: _norm_font(e) == _norm_font(a),
                advice_prefix,
            )
        )

    def size_matcher(e: Any, a: Any) -> bool:
        try:
            return abs(float(e) - float(a)) <= tolerance.font_size_pt
        except (TypeError, ValueError):
            return False

    out.append(
        _compare_font_attr(
            f"{rule_id_prefix}.font_size_pt",
            f"{label} font size",
            rule_format.font_size_pt,
            actual_size,
            size_matcher,
            advice_prefix,
        )
    )

    if rule_format.bold is not None:
        out.append(
            _na(
                f"{rule_id_prefix}.bold",
                f"{label} weight",
                "Per-element bold state is not compared; the dominant body weight is reported "
                "in the extracted facts instead.",
            )
        )

    if rule_format.alignment is not None:
        dominant_alignment = _dominant_alignment(facts, rule_id_prefix)
        if dominant_alignment is None:
            out.append(
                _na(
                    f"{rule_id_prefix}.alignment",
                    f"{label} alignment",
                    f"Alignment of the {label.lower()} could not be measured.",
                )
            )
        else:
            ok = dominant_alignment == rule_format.alignment
            out.append(
                _check(
                    f"{rule_id_prefix}.alignment",
                    f"{label} alignment",
                    "passed" if ok else "failed",
                    Severity.ADVISORY,
                    rule_format.alignment,
                    dominant_alignment,
                    advice=(None if ok else
                            f"The {label.lower()} should be {rule_format.alignment}-aligned; "
                            f"the dominant body alignment is {dominant_alignment}."),
                    evidence=f"alignment_distribution={facts.typography.alignment_distribution}",
                    confidence="low",
                )
            )

    return out


def _dominant_alignment(facts: PaperFacts, rule_id_prefix: str) -> Optional[str]:
    dist = facts.typography.alignment_distribution
    if not dist:
        return None
    if rule_id_prefix.startswith("typography.body"):
        return max(dist.items(), key=lambda kv: kv[1])[0]
    if rule_id_prefix.startswith(("typography.abstract", "typography.heading", "typography.title")):
        return max(dist.items(), key=lambda kv: kv[1])[0]
    return None


def _check_typography(rules: RuleSet, facts: PaperFacts) -> list[CheckResult]:
    out: list[CheckResult] = []
    typo = rules.typography
    tol = typo.tolerance

    out.extend(
        _typography_element("typography.title", "Title", typo.title, facts, tol,
                            "Set the title style in your word processor or template.")
    )
    out.extend(
        _typography_element("typography.heading", "Heading", typo.headings, facts, tol,
                            "Apply the template's heading style.")
    )
    out.extend(
        _typography_element("typography.abstract", "Abstract", typo.abstract, facts, tol,
                            "Style the abstract with the template's abstract style.")
    )
    out.extend(
        _typography_element("typography.body", "Body", typo.body, facts, tol,
                            "Set the body text style in your word processor.")
    )

    if tol.min_font_size_pt is not None or tol.max_font_size_pt is not None:
        sizes = facts.typography.distinct_body_font_sizes
        if not sizes:
            out.append(_na("typography.size_range", "Body font size range",
                           "No body font sizes could be read."))
        else:
            offending = [
                s for s in sizes
                if (tol.min_font_size_pt is not None and s < tol.min_font_size_pt)
                or (tol.max_font_size_pt is not None and s > tol.max_font_size_pt)
            ]
            bounds = []
            if tol.min_font_size_pt is not None:
                bounds.append(f">= {tol.min_font_size_pt:g} pt")
            if tol.max_font_size_pt is not None:
                bounds.append(f"<= {tol.max_font_size_pt:g} pt")
            out.append(
                _check(
                    "typography.size_range",
                    "Body font size range",
                    "passed" if not offending else "failed",
                    Severity.WARNING,
                    " and ".join(bounds),
                    f"{min(sizes):g}-{max(sizes):g} pt",
                    advice=(None if not offending else
                            f"Body text must stay within {' and '.join(bounds)}. Offending "
                            f"size(s): {', '.join(f'{s:g}' for s in offending[:4])} pt."),
                    evidence=f"sizes={sizes[:10]}",
                )
            )
    else:
        out.append(_na("typography.size_range", "Body font size range", "No size range configured."))

    return out


# --------------------------------------------------------------------------- #
# paragraph rules
# --------------------------------------------------------------------------- #


def _check_paragraph(rules: RuleSet, facts: PaperFacts) -> list[CheckResult]:
    out: list[CheckResult] = []
    para = rules.paragraph
    typo = facts.typography

    def numeric_rule(rule_id: str, name: str, expected, actual, tolerance, advice: str) -> None:
        if expected is None:
            out.append(_na(rule_id, name, f"No {name.lower()} rule configured."))
            return
        if actual is None:
            out.append(
                _check(
                    rule_id, name, "missing", Severity.WARNING, _fmt_pt(expected), None,
                    advice=f"{name} could not be measured for this file type. {advice}",
                    confidence="low",
                )
            )
            return
        ok = abs(float(expected) - float(actual)) <= tolerance
        out.append(
            _check(
                rule_id, name, "passed" if ok else "failed", Severity.WARNING,
                _fmt_pt(expected), _fmt_pt(actual),
                advice=None if ok else f"{name} must be {expected:g}, but is {actual:g}. {advice}",
            )
        )

    numeric_rule(
        "paragraph.line_spacing", "Line spacing", para.line_spacing, typo.line_spacing,
        para.line_spacing_tolerance,
        "In LaTeX set \\linespread{...}; in Word set Paragraph > Line spacing.",
    )
    numeric_rule(
        "paragraph.first_line_indent", "First-line indent", para.indent_first_line_pt,
        typo.first_line_indent_pt, para.indent_tolerance_pt,
        "In LaTeX set \\setlength{\\parindent}{...}; in Word set Paragraph > Indentation > First line.",
    )
    numeric_rule(
        "paragraph.space_above", "Space above paragraph", para.space_above_pt,
        typo.space_above_pt, para.space_tolerance_pt,
        "Set Paragraph > Spacing > Before, or \\setlength{\\parskip}{...} in LaTeX.",
    )
    numeric_rule(
        "paragraph.space_below", "Space below paragraph", para.space_below_pt,
        typo.space_below_pt, para.space_tolerance_pt,
        "Set Paragraph > Spacing > After.",
    )

    if para.require_justified_body:
        dist = typo.alignment_distribution
        total = sum(dist.values())
        if not total:
            out.append(_na("paragraph.justified", "Body justified", "No body alignment data."))
        else:
            justified = dist.get("justified", 0)
            ratio = justified / total
            ok = ratio >= 0.9
            out.append(
                _check(
                    "paragraph.justified",
                    "Body justified",
                    "passed" if ok else "failed",
                    Severity.ADVISORY,
                    "Justified body text",
                    f"{justified}/{total} body blocks justified",
                    advice=(None if ok else
                            "This template requires justified body text. Select the body and "
                            "apply justified alignment."),
                    evidence=f"alignment_distribution={dist}",
                    confidence="low",
                )
            )
    else:
        out.append(_na("paragraph.justified", "Body justified", "Justification not required."))

    if para.require_uniform_alignment:
        dist = typo.alignment_distribution
        if len(dist) <= 1:
            out.append(_check("paragraph.uniform_alignment", "Uniform body alignment", "passed",
                              Severity.ADVISORY, "One alignment", dict(dist)))
        else:
            mismatch = max(dist.values())
            ok = mismatch <= max(1, para.max_alignment_mismatches)
            out.append(
                _check(
                    "paragraph.uniform_alignment",
                    "Uniform body alignment",
                    "passed" if ok else "failed",
                    Severity.ADVISORY,
                    f"At most {para.max_alignment_mismatches} block(s) deviating",
                    dict(dist),
                    advice=(None if ok else
                            f"{mismatch} body block(s) use a different alignment than the rest. "
                            "Apply one alignment across the body."),
                    confidence="low",
                )
            )
    else:
        out.append(_na("paragraph.uniform_alignment", "Uniform body alignment",
                       "Uniform alignment not required."))

    return out


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #


def evaluate(rules: RuleSet, facts: PaperFacts) -> list[CheckResult]:
    """Run every enabled rule and return the full, ordered result list."""
    results: list[CheckResult] = []
    results.extend(_check_file(rules, facts))
    results.extend(_check_pages(rules, facts))
    results.extend(_check_structure(rules, facts))
    results.extend(_check_typography(rules, facts))
    results.extend(_check_paragraph(rules, facts))
    results.extend(check_anonymisation(rules.anonymisation, facts))
    return results


def _verdict(rules: RuleSet, results: list[CheckResult]) -> tuple[str, Optional[str]]:
    decision = rules.decision
    blocking = [r for r in results if r.status in ("failed", "missing") and r.severity == Severity.BLOCKING]
    warnings = [r for r in results if r.status in ("failed", "missing") and r.severity == Severity.WARNING]

    scored = [r for r in results if r.status in ("passed", "failed", "missing")]
    score = round(100 * sum(1 for r in scored if r.status == "passed") / len(scored)) if scored else 100

    if decision.reject_if_any_blocking and blocking:
        first = blocking[0]
        return "rejected", (
            f"{len(blocking)} blocking issue(s) must be fixed: {first.name}"
            + (f" (and {len(blocking) - 1} more)" if len(blocking) > 1 else "")
        )
    if decision.reject_if_any_warning and warnings:
        return "rejected", f"{len(warnings)} warning-level issue(s) must be fixed"
    if decision.min_score_to_accept is not None and score < decision.min_score_to_accept:
        return "rejected", (
            f"Compliance score {score}% is below the required {decision.min_score_to_accept}%"
        )
    if warnings:
        return "needs_review", f"{len(warnings)} warning(s) to review before final acceptance"
    return "accepted", None


def _build_paper_metadata(facts: PaperFacts) -> PaperMetadata:
    structure = facts.structure
    identity = facts.identity

    title = structure.title_text or ""
    if not title:
        if facts.docx and facts.docx.core_title:
            title = facts.docx.core_title
        elif facts.pdf and facts.pdf.metadata.get("title"):
            title = facts.pdf.metadata["title"]
        elif facts.latex and facts.latex.title_macro:
            title = facts.latex.title_macro

    authors = list(identity.detected_person_names)
    author_block = identity.author_block_text or ""

    return PaperMetadata(
        title=title,
        authors=authors,
        author_block=author_block,
        emails=list(identity.detected_emails),
        affiliations=list(identity.detected_affiliations),
        orcids=list(identity.detected_orcids),
    )


def assess(rules: RuleSet, facts: PaperFacts) -> PaperAssessment:
    results = evaluate(rules, facts)
    verdict, action = _verdict(rules, results)

    scored = [r for r in results if r.status in ("passed", "failed", "missing")]
    passed = sum(1 for r in scored if r.status == "passed")
    failed = sum(1 for r in scored if r.status == "failed")
    missing = sum(1 for r in scored if r.status == "missing")
    not_applicable = sum(1 for r in results if r.status == "not_applicable")
    score = round(100 * passed / len(scored)) if scored else 100

    blocking = [r for r in results if r.status in ("failed", "missing") and r.severity == Severity.BLOCKING]
    warnings = [r for r in results if r.status in ("failed", "missing") and r.severity == Severity.WARNING]

    enriched = facts.model_copy(deep=True)
    enriched.identity.anonymisation_score = score_anonymisation(facts)

    if verdict == "accepted":
        line = f"Accepted — all {len(scored)} applicable requirements satisfied."
    elif verdict == "rejected":
        names = ", ".join(r.name for r in blocking[:3])
        more = f" (+{len(blocking) - 3} more)" if len(blocking) > 3 else ""
        line = f"Rejected — {len(blocking)} blocking issue(s): {names}{more}."
    else:
        line = f"Accepted with warnings — {len(warnings)} advisory issue(s) to review."

    return PaperAssessment(
        filename=facts.file.filename,
        format=facts.file.format,
        verdict=verdict,
        score=score,
        passed=passed,
        failed=failed,
        missing=missing,
        not_applicable=not_applicable,
        blocking_reasons=blocking,
        warnings=warnings,
        results=results,
        facts=enriched,
        metadata=_build_paper_metadata(facts),
        summary_line=line,
        action_required=action,
    )


__all__ = ["assess", "evaluate"]
