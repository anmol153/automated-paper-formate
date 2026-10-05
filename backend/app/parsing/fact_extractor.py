"""Builds a ``PaperFacts`` record from raw bytes plus the normalised document.

Layout: format-specific extractors first (LaTeX source, OOXML parts, PDF
metadata), then format-agnostic facts derived from the ``NormalizedDocument``
that every parser already produces. Facts that rely on heuristics record their
confidence so the engine can avoid hard failures on shaky readings.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections import Counter
from typing import Any, Optional

import pymupdf

from app.models.document import NormalizedDocument, TextFormat
from app.models.facts import (
    AssetFacts,
    DocxFacts,
    FileFacts,
    IdentityFacts,
    LatexFacts,
    LayoutFacts,
    PaperFacts,
    PdfFacts,
    StructureFacts,
    TypographyFacts,
)
from app.models.report import PaperMetadata
from app.parsing.structure import aggregate_formats

MAX_ANON_SNIPPET = 400

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
_ORCID_RE = re.compile(r"\b(?:\(?\d{4}\)?[-\s]?){3}\d{3}[\dXx]\b")
_URL_RE = re.compile(r"https?://[^\s,;)\]]+|www\.[^\s,;)\]]+", re.IGNORECASE)

_AFFILIATION_HINTS = re.compile(
    r"(\buniversit|\binstitut|\bcollege\b|\bschool\s+of|\bdepartment|\bfaculty\b|\blaborator|"
    r"\blab\b|\bcentre\b|\bcenter\s+for|\bacademy\b|\bpolytechnic|\bhospital|"
    r"\bresearch\s+(?:centre|center)|\binc\.|\bllc\b|\bltd\.?|\bcorp\.|\bfoundation\b|\bclinic\b|"
    r"\btechnolog(?:y|ical)\s+institute)",
    re.IGNORECASE,
)
_AFFILIATION_RE = re.compile(r"[^.;\n]{0,70}" + _AFFILIATION_HINTS.pattern + r"[^.;\n]{0,40}", re.IGNORECASE)
_NON_NAME_MARKER_RE = re.compile(
    r"(\buniversit|\binstitut|\bcollege\b|\bdepartment|@|\babstract\b|\bkeywords\b)",
    re.IGNORECASE,
)
_ACK_SECTION_RE = re.compile(r"\backnowledg", re.IGNORECASE)
_ACK_PHRASE_RE = re.compile(
    r"\b(we (thank|gratefully acknowledge|acknowledge)|this (work|research) (was|is) (supported|funded)|"
    r"the authors (thank|acknowledge))\b",
    re.IGNORECASE,
)
_FUNDING_RE = re.compile(
    r"(\b(funded|funded by|supported by|grant(?:s)?|award(?:s)?|grant no|award no|project no|"
    r"r\d{2}[A-Z]{2}\d{4,}|nsf|erc|dst[ie]|nih|erc|eu horizon)\b)",
    re.IGNORECASE,
)
_SELF_CITATION_RE = re.compile(
    r"\b(our (previous|earlier|prior|former) (work|paper|papers|results|study|studies|approach|"
    r"method)|we (previously|earlier) (proposed|presented|introduced|showed|published|described)|"
    r"in our (previous|earlier) (work|paper|study)\b)",
    re.IGNORECASE,
)
_ANON_PLACEHOLDER_RE = re.compile(
    r"\b(anonymous|anonymised|anonymized|author(?:s)? withheld|double[\s-]blind|"
    r"under\s+(?:double\s+)?(?:blind\s+)?review|for\s+peer\s+review|manuscript\s+id)\b",
    re.IGNORECASE,
)
_FIGURE_REF_RE = re.compile(r"\b(?:fig(?:ure)?s?\.?)\s*(\d{1,3})\b", re.IGNORECASE)
_TABLE_REF_RE = re.compile(r"\b(?:tab(?:le)?s?\.?)\s*(\d{1,3})\b", re.IGNORECASE)
_EQUATION_REF_RE = re.compile(r"\b(?:eq(?:uation)?s?\.?)\s*\(?(\d{1,3})\)?\b", re.IGNORECASE)
_REF_YEAR_RE = re.compile(r"\(?\b(?:19|20)\d{2}[a-z]?\b\)?")
_SECTION_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+")
_EXCLUDED_FROM_STATS = {"references"}

_PERSON_STOPWORDS = {
    "abstract", "introduction", "conclusion", "results", "methodology", "references",
    "keywords", "affiliation", "university", "department", "institute", "email",
    "corresponding", "author", "authors", "google", "scholar", "orcid", "the", "and",
    "for", "with", "using", "based", "via", "from", "toward", "towards",
    # Institution words that precede an affiliation marker but look like names.
    "state", "national", "technical", "polytechnic", "federal", "central", "royal",
    "public", "private", "science", "sciences", "technology", "engineering", "medicine",
    "research", "advanced", "higher", "learning", "applied", "pure",
}

_FONT_PACKAGES = {
    "times", "mathptmx", "mathptm", "newtxtext", "txfonts", "ptm", "helvet", "helveto",
    "phv", "newcent", "pnc", "palatino", "mathpazo", "ppl", "bookman", "pbk", "avant",
    "pag", "charter", "courier", "pcr", "lmodern", "timesmath", "libertine", "kpfonts",
    "newtxmath", "tgheros", "tgtermes", "tgschola", "tgpagella", "tgbonum", "tgcursor",
}

_DOCX_CORE = "docProps/core.xml"
_DOCX_APP = "docProps/app.xml"


# --------------------------------------------------------------------------- #
# generic helpers
# --------------------------------------------------------------------------- #


def _weighted_font_histogram(formats: list[TextFormat]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for fmt in formats:
        if fmt.font_family:
            counter[fmt.font_family] += 1
    return dict(counter.most_common())


def _words(text: str) -> int:
    return len(text.split())


def _heading_names(doc: NormalizedDocument) -> list[str]:
    return [b.name for b in doc.headings() if b.name]


def _section_text(doc: NormalizedDocument, name: str) -> str:
    return " ".join(b.text for b in doc.sections if b.name == name and b.type == "body")


def _max_number(refs: list[int]) -> int:
    return max(refs) if refs else 0


# --------------------------------------------------------------------------- #
# format-specific extraction
# --------------------------------------------------------------------------- #


def _extract_latex(data: bytes, doc: NormalizedDocument) -> LatexFacts:
    source = data.decode("utf-8", errors="replace")
    facts = LatexFacts()

    docclass = re.search(r"\\documentclass(\[[^\]]*\])?\{([^}]*)\}", source)
    if docclass:
        facts.document_class = docclass.group(2).strip()
        facts.class_options = [
            o.strip() for o in (docclass.group(1) or "").strip("[]").split(",") if o.strip()
        ]

    facts.packages = sorted(
        {
            p.strip()
            for group in re.findall(r"\\usepackage(\[[^\]]*\])?\{([^}]*)\}", source)
            for p in group[1].split(",")
            if p.strip()
        }
    )
    facts.font_packages = [p for p in facts.packages if p.casefold() in _FONT_PACKAGES]

    geometry = re.search(r"\\geometry(\[[^\]]*\])?\s*\{([^}]*)\}", source)
    if geometry:
        for option in re.split(r",", f"{(geometry.group(1) or '').strip('[]')},{geometry.group(2)}"):
            if "=" in option:
                key, _, value = option.partition("=")
                facts.geometry_options[key.strip()] = value.strip()
    else:
        for group in re.findall(r"\\usepackage(\[[^\]]*\])?\{geometry\}", source):
            for option in (group[0] or "").strip("[]").split(","):
                if "=" in option:
                    key, _, value = option.partition("=")
                    facts.geometry_options[key.strip()] = value.strip()

    spread = re.search(r"\\(linespread|setstretch)\s*\{?([0-9]*\.?[0-9]+)\}?", source)
    if spread:
        facts.linespread = float(spread.group(2))
    parindent = re.search(r"\\setlength\s*\{\\parindent\}\s*\{([^}]*)\}", source)
    if parindent:
        facts.parindent = parindent.group(1).strip()

    facts.has_maketitle = bool(re.search(r"\\maketitle\b", source))
    title_macro = re.search(r"\\title\s*\{", source)
    if title_macro:
        facts.title_macro = "present"
    author_macro = re.search(r"\\author\s*\{", source)
    if author_macro:
        facts.author_macro = "present"
    bibstyle = re.search(r"\\bibliographystyle\s*\{([^}]*)\}", source)
    if bibstyle:
        facts.bibliography_style = bibstyle.group(1).strip()

    facts.has_anonymous_package = "anonymous" in {p.casefold() for p in facts.packages}
    facts.explicit_page_break_commands = len(
        re.findall(r"\\(newpage|clearpage|cleardoublepage|pagebreak)\b", source)
    )
    facts.unresolved_includes = sorted(
        {
            m.group(1)
            for m in re.finditer(r"\\(?:input|include)\s*\{([^}]*)\}", source)
            if not m.group(1).strip()
        }
    )
    facts.inline_math_spans = len(re.findall(r"(?<!\$)\$(?!\$)", source))
    facts.display_math_spans = len(re.findall(r"\\\[|\\begin\{(?:equation|align|gather|eqnarray)\*?\}", source))
    return facts


def _docx_xml(zf: zipfile.ZipFile, name: str) -> Optional[str]:
    try:
        return zf.read(name).decode("utf-8", errors="replace")
    except KeyError:
        return None


def _xml_text(blob: str, tag: str) -> Optional[str]:
    match = re.search(rf"<(?:[a-z0-9]+:)?{tag}[^>]*>(.*?)</(?:[a-z0-9]+:)?{tag}>", blob, re.S | re.I)
    if not match:
        return None
    return re.sub(r"<[^>]+>", "", match.group(1)).strip() or None


def _extract_docx(data: bytes) -> DocxFacts:
    facts = DocxFacts()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return facts

    names = set(zf.namelist())
    if _DOCX_CORE in names:
        core = _docx_xml(zf, _DOCX_CORE) or ""
        facts.core_title = _xml_text(core, "title")
        facts.last_modified_by = _xml_text(core, "lastModifiedBy")
        revision = _xml_text(core, "revision")
        if revision and revision.isdigit():
            facts.revision = int(revision)

    if _DOCX_APP in names:
        app = _docx_xml(zf, _DOCX_APP) or ""
        facts.template_name = _xml_text(app, "Template")
        facts.application = _xml_text(app, "Application")
        facts.app_version = _xml_text(app, "AppVersion")

    facts.embedded_image_count = sum(
        1 for n in names if n.startswith("word/media/") and not n.endswith("/")
    )
    facts.has_comments = "word/comments.xml" in names
    if "word/document.xml" in names:
        document = _docx_xml(zf, "word/document.xml") or ""
        facts.has_track_changes = bool(
            re.search(r"<w:(ins|del)\b", document)
        )

    if "word/styles.xml" in names:
        styles = _docx_xml(zf, "word/styles.xml") or ""
        default = re.search(r"<w:docDefaults>.*?</w:docDefaults>", styles, re.S)
        if default:
            block = default.group(0)
            font = re.search(r'w:ascii="([^"]+)"', block)
            if font:
                facts.default_style_font = font.group(1)
            size = re.search(r'<w:sz w:val="(\d+)"', block)
            if size:
                facts.default_style_size_pt = int(size.group(1)) / 2
    return facts


def _extract_pdf(data: bytes) -> PdfFacts:
    facts = PdfFacts()
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            facts.page_count = int(doc.page_count)
            metadata = doc.metadata or {}
            facts.metadata = {k: str(v) for k, v in metadata.items() if v}
            try:
                facts.has_javascript = bool(doc.get_page_text(0)) and bool(
                    doc.get_optional_content
                )
            except Exception:
                facts.has_javascript = False
            facts.is_encrypted = bool(doc.needs_pass)
            facts.has_embedded_files = bool(getattr(doc, "embfile_count", 0))
            facts.has_form_fields = any(
                bool(page.widgets()) for page in (doc[i] for i in range(min(doc.page_count, 5)))
            )
            labels: list[int] = []
            for index in range(doc.page_count):
                labels.append(index + 1)
            facts.page_labels = labels
    except Exception:
        return facts
    return facts


# --------------------------------------------------------------------------- #
# identity detection
# --------------------------------------------------------------------------- #


def _person_names(text: str, title_text: str) -> list[str]:
    title_tokens = {t.casefold() for t in re.findall(r"[A-Za-z]+", title_text)}
    candidates: list[str] = []
    for sentence in re.split(r"(?<=[.;,])\s+", text):
        stripped = sentence.strip()
        if not stripped or len(stripped) > 200:
            continue
        marker = _NON_NAME_MARKER_RE.search(stripped)
        if marker:
            stripped = stripped[: marker.start()]
        words = stripped.split()
        run: list[str] = []
        for word in words:
            cleaned = re.sub(r"[^A-Za-z'\-]", "", word)
            if not cleaned:
                run = []
                continue
            is_cap = cleaned[:1].isupper()
            if is_cap and cleaned.casefold() not in _PERSON_STOPWORDS:
                run.append(cleaned)
            else:
                if 2 <= len(run) <= 4:
                    candidates.append(" ".join(run))
                run = []
        if 2 <= len(run) <= 4:
            candidates.append(" ".join(run))

    filtered = [
        name
        for name in candidates
        if not all(token.casefold() in title_tokens for token in name.split())
    ]
    seen: dict[str, None] = {}
    for name in filtered:
        seen.setdefault(name, None)
    return list(seen)


def _extract_identity(doc: NormalizedDocument, pdf: Optional[PdfFacts], latex: Optional[LatexFacts]) -> IdentityFacts:
    identity = IdentityFacts()
    full_text = doc.full_text()
    lower_text = full_text.casefold()

    author_block = doc.find("authors")
    if author_block and author_block.text.strip():
        block_text = author_block.text.strip()
        identity.author_block_text = block_text[:MAX_ANON_SNIPPET]
        # An author block that only carries a placeholder ("Anonymous Authors",
        # "Author names withheld", ...) is the *correct* double-blind form and
        # must not be reported as an identifying block. Only flag it once real
        # name-like content is present alongside the placeholder.
        if _ANON_PLACEHOLDER_RE.search(block_text) and not _person_names(
            block_text, doc.document.title
        ):
            identity.author_block_placeholder_only = True
        else:
            identity.author_block_present = True

    identity.detected_emails = sorted(set(_EMAIL_RE.findall(full_text)))
    identity.detected_urls = sorted(set(u.rstrip(".") for u in _URL_RE.findall(full_text)))[:20]
    identity.detected_orcids = sorted(set(_ORCID_RE.findall(full_text)))
    identity.detected_affiliations = sorted(
        {
            m.group(0).strip()[:MAX_ANON_SNIPPET]
            for m in _AFFILIATION_RE.finditer(full_text)
        }
    )[:10]

    if author_block:
        identity.detected_person_names = _person_names(
            author_block.text, doc.document.title
        )[:10]

    ack_heading = next(
        (b for b in doc.sections if b.type == "heading" and _ACK_SECTION_RE.search(b.name or "")),
        None,
    )
    if ack_heading:
        identity.acknowledgement_present = True
        identity.acknowledgement_text = _section_text(doc, ack_heading.name or "")[:MAX_ANON_SNIPPET]
    elif _ACK_PHRASE_RE.search(full_text):
        match = _ACK_PHRASE_RE.search(full_text)
        identity.acknowledgement_present = True
        identity.acknowledgement_text = full_text[match.start() : match.start() + MAX_ANON_SNIPPET]

    if _FUNDING_RE.search(full_text):
        identity.funding_present = True
        match = _FUNDING_RE.search(full_text)
        identity.funding_text = full_text[max(0, match.start() - 80) : match.start() + MAX_ANON_SNIPPET]

    self_hits = _SELF_CITATION_RE.findall(full_text)
    identity.self_citation_count = len(self_hits) if self_hits else 0

    identity.anonymous_placeholder_present = bool(_ANON_PLACEHOLDER_RE.search(lower_text))
    if latex is not None and latex.has_anonymous_package:
        identity.anonymous_placeholder_present = True

    if pdf is not None:
        for field in ("author", "creator", "producer", "title", "subject", "keywords"):
            value = pdf.metadata.get(field)
            if value:
                identity.metadata_leaks[field] = str(value)[:MAX_ANON_SNIPPET]

    return identity


# --------------------------------------------------------------------------- #
# main entry point
# --------------------------------------------------------------------------- #


def _reference_count(doc: NormalizedDocument) -> tuple[Optional[int], str]:
    body = [b for b in doc.sections if b.name == "References" and b.type == "body"]
    if not body:
        return None, "unknown"
    entries = 0
    for block in body:
        text = block.text.strip()
        if not text:
            continue
        parts = re.split(r"(?=\[\d{1,3}\])|(?=\(\d{1,3}\))|(?<=\.)\s+(?=[A-Z][a-z]+,?\s+[A-Z])", text)
        entries += max(1, len([p for p in parts if p.strip()]))
    if entries == 0:
        return None, "low"
    years = sum(1 for block in body if _REF_YEAR_RE.search(block.text))
    confidence = "high" if years >= max(1, entries // 2) else "medium"
    return entries, confidence


def _asset_counts(doc: NormalizedDocument, latex: Optional[LatexFacts]) -> AssetFacts:
    text = doc.full_text()
    assets = AssetFacts()

    if latex is not None:
        source_fig = len(re.findall(r"\\begin\{figure\*?\}", text)) or len(
            re.findall(r"\\includegraphics", text)
        )
        assets.figures = source_fig
        assets.tables = len(re.findall(r"\\begin\{table\*?\}", text))
        assets.equations = len(
            re.findall(r"\\begin\{(?:equation|align|gather|eqnarray|multline)\*?\}", text)
        )
        assets.algorithms = len(re.findall(r"\\begin\{algorithm\*?\}", text))
        assets.listings = len(re.findall(r"\\begin\{lstlisting\}", text))
        assets.bibliography_items = len(re.findall(r"\\bibitem\b", text))
        assets.confidence = "high"
    else:
        assets.figures = _max_number([int(n) for n in _FIGURE_REF_RE.findall(text)])
        assets.tables = _max_number([int(n) for n in _TABLE_REF_RE.findall(text)])
        assets.equations = _max_number([int(n) for n in _EQUATION_REF_RE.findall(text)])
        assets.confidence = "medium"

    assets.footnotes = len(re.findall(r"\b(?:footnote|thanks)\b", text)) if latex else len(
        re.findall(r"^\s*\d+\s{2,}\S", text, re.MULTILINE)
    )
    return assets


def build_facts(
    data: bytes,
    filename: str,
    doc: NormalizedDocument,
    fmt: str,
    author_supplied: dict[str, Any] | None = None,
) -> PaperFacts:
    facts = PaperFacts()
    facts.parser = fmt
    supplied = author_supplied or {}

    extension = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    facts.file = FileFacts(
        filename=filename,
        extension=extension,
        format=fmt,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        author_supplied_name=supplied.get("name"),
        author_supplied_email=supplied.get("email"),
        author_supplied_track=supplied.get("track"),
    )

    page = doc.document.page_size
    margins = doc.document.margins
    facts.layout = LayoutFacts(
        page_count=doc.document.page_count,
        page_count_exact=doc.document.page_count_exact,
        page_count_confidence="exact" if doc.document.page_count_exact else "medium",
        page_size_label=page.label,
        width_pt=page.width_pt,
        height_pt=page.height_pt,
        orientation=doc.document.orientation,
        columns=doc.document.columns,
        column_spacing_pt=doc.document.column_spacing_pt,
        margins_pt={
            "top": margins.top_pt,
            "bottom": margins.bottom_pt,
            "left": margins.left_pt,
            "right": margins.right_pt,
        },
        margins_confidence="exact" if fmt in ("latex", "docx") else "low",
    )

    title_block = doc.find("title")
    abstract_block = doc.find("abstract")
    heading_blocks = doc.headings()
    body_blocks = [b for b in doc.sections if b.type == "body" and b.name not in _EXCLUDED_FROM_STATS]

    body_format = aggregate_formats([b.format for b in body_blocks]) if body_blocks else None
    all_formats = [b.format for b in doc.sections]

    alignment_counts = Counter(
        b.format.alignment for b in body_blocks if b.format.alignment
    )
    body_sizes = sorted({b.format.font_size_pt for b in body_blocks if b.format.font_size_pt})

    heading_levels: dict[str, float] = {}
    for block in heading_blocks:
        if block.format.font_size_pt:
            heading_levels[block.name or "?"] = block.format.font_size_pt

    facts.typography = TypographyFacts(
        fonts_used=_weighted_font_histogram(all_formats),
        dominant_font=body_format.font_family if body_format else None,
        body_font=body_format.font_family if body_format else None,
        body_font_size_pt=body_format.font_size_pt if body_format else None,
        title_font_size_pt=title_block.format.font_size_pt if title_block else None,
        heading_font_size_pt=aggregate_formats([b.format for b in heading_blocks]).font_size_pt
        if heading_blocks
        else None,
        heading_levels=heading_levels,
        line_spacing=body_format.line_spacing if body_format else None,
        alignment_distribution=dict(alignment_counts),
        first_line_indent_pt=body_format.indent_first_line_pt if body_format else None,
        space_above_pt=body_format.space_above_pt if body_format else None,
        space_below_pt=body_format.space_below_pt if body_format else None,
        distinct_body_font_sizes=body_sizes,
    )

    keywords_block = doc.find("keywords")
    keywords: list[str] = []
    if keywords_block:
        keywords = [k.strip() for k in re.split(r"[,;]", keywords_block.text) if k.strip()]

    reference_entries, reference_confidence = _reference_count(doc)

    facts.structure = StructureFacts(
        sections_present=_heading_names(doc),
        headings=[
            {"name": b.name, "text": b.text, "numbered": bool(_SECTION_NUMBER_RE.match(b.text))}
            for b in heading_blocks
            if b.name
        ],
        numbered_headings=[b.name for b in heading_blocks if b.name and _SECTION_NUMBER_RE.match(b.text)],
        has_abstract=abstract_block is not None,
        abstract_word_count=_words(abstract_block.text) if abstract_block else None,
        abstract_truncated=bool(abstract_block and len(abstract_block.text) >= 2000),
        has_keywords=keywords_block is not None,
        keyword_count=len(keywords) if keywords_block else 0,
        keywords=keywords,
        title_present=title_block is not None,
        title_text=title_block.text if title_block else doc.document.title,
        author_block_present=doc.find("authors") is not None,
        author_block_text=(doc.find("authors").text[:MAX_ANON_SNIPPET] if doc.find("authors") else ""),
        reference_entry_count=reference_entries,
        reference_count_confidence=reference_confidence,
        body_word_count=sum(_words(b.text) for b in body_blocks),
        total_word_count=doc.word_count(),
    )

    latex_facts = _extract_latex(data, doc) if fmt == "latex" else None
    docx_facts = _extract_docx(data) if fmt == "docx" else None
    pdf_facts = _extract_pdf(data) if fmt == "pdf" else None

    facts.latex = latex_facts
    facts.docx = docx_facts
    facts.pdf = pdf_facts

    if latex_facts is not None:
        assets = _asset_counts(doc, latex_facts)
        if assets.bibliography_items:
            assets.confidence = "high"
            reference_entries, reference_confidence = assets.bibliography_items, "exact"
            facts.structure.reference_entry_count = reference_entries
            facts.structure.reference_count_confidence = reference_confidence
    else:
        assets = _asset_counts(doc, None)

    facts.assets = assets
    facts.identity = _extract_identity(doc, pdf_facts, latex_facts)
    # Keep the structure view consistent with the identity view: a placeholder-only
    # author block is not an author block.
    facts.structure.author_block_present = facts.identity.author_block_present
    facts.structure.author_block_placeholder_only = facts.identity.author_block_placeholder_only

    if doc.document.page_count and not doc.document.page_count_exact:
        facts.parse_warnings.append(
            f"Page count ({doc.document.page_count}) is an estimate: {fmt} sources are not paginated until rendered."
        )
    if facts.layout.margins_confidence == "low":
        facts.parse_warnings.append(
            "Margins are estimated from content extents in PDFs; headers and footers can skew them."
        )

    return facts


def extract_paper_metadata(
    doc: NormalizedDocument,
    pdf: Optional[PdfFacts] = None,
    latex: Optional[LatexFacts] = None,
) -> PaperMetadata:
    """Extract structured paper metadata from a normalized document for display."""
    full_text = doc.full_text()
    title = doc.document.title or ""

    author_block = doc.find("authors")
    author_block_text = author_block.text.strip() if author_block and author_block.text.strip() else ""
    authors = _person_names(author_block_text, title) if author_block_text else []

    emails = sorted(set(_EMAIL_RE.findall(full_text)))
    affiliations = sorted(
        {m.group(0).strip()[:MAX_ANON_SNIPPET] for m in _AFFILIATION_RE.finditer(full_text)}
    )[:10]
    orcids = sorted(set(_ORCID_RE.findall(full_text)))

    if pdf is not None and pdf.metadata.get("title") and not title:
        title = pdf.metadata["title"]

    return PaperMetadata(
        title=title,
        authors=authors,
        author_block=author_block_text,
        emails=emails,
        affiliations=affiliations,
        orcids=orcids,
    )


__all__ = ["build_facts", "extract_paper_metadata"]
