"""Builds sample template/paper .docx files used by demo mode, tests and the samples/ folder.

A .docx is a ZIP of OOXML parts, so the builder writes minimal parts directly with the
stdlib (zipfile) — mirroring the Google Docs / PDF demo documents.
"""

from __future__ import annotations

import zipfile
from functools import lru_cache
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape

TEMPLATE_TITLE = "Sample Journal Paper Template"
PAPER_TITLE = "Deep Learning for Format Compliance Checking"

_SENTENCE = (
    "The proposed approach evaluates formatting compliance by parsing the document model "
    "directly and comparing extracted rules against observed typography across all sections."
)


def _run(text: str, *, family: str = "Times New Roman", size: float = 10.0,
         bold: bool = False, italic: bool = False) -> str:
    rpr = ""
    family_escaped = _xml_escape(family)
    rpr += f'<w:rFonts w:ascii="{family_escaped}" w:hAnsi="{family_escaped}" w:cs="{family_escaped}"/>'
    rpr += f'<w:sz w:val="{int(round(size * 2))}"/><w:szCs w:val="{int(round(size * 2))}"/>'
    if bold:
        rpr += "<w:b/>"
    if italic:
        rpr += "<w:i/>"
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{_xml_escape(text)}</w:t></w:r>'


def _para(*runs: str, style: str | None = None, jc: str | None = None, line: float | None = None,
          before: float | None = None, after: float | None = None,
          first_line_pt: float | None = None) -> str:
    ppr = ""
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if jc:
        ppr += f'<w:jc w:val="{jc}"/>'
    spacing = ""
    if line is not None:
        spacing += f' w:line="{int(round(line * 240))}" w:lineRule="auto"'
    if before is not None:
        spacing += f' w:before="{int(round(before * 20))}"'
    if after is not None:
        spacing += f' w:after="{int(round(after * 20))}"'
    if spacing:
        ppr += f"<w:spacing{spacing}/>"
    if first_line_pt is not None:
        ppr += f'<w:ind w:firstLine="{int(round(first_line_pt * 20))}"/>'
    body = "".join(runs) if runs else _run("")
    return f"<w:p>{f'<w:pPr>{ppr}</w:pPr>' if ppr else ''}{body}</w:p>"


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:spacing w:before="0" w:after="0"/></w:pPr><w:rPr><w:b/></w:rPr></w:style>
</w:styles>"""

_CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{title}</dc:title>
</cp:coreProperties>"""

_APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Paper Format Compliance</Application>
</Properties>"""


def _document(body_xml: str, sect_pr: str, title: str) -> bytes:
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body_xml}{sect_pr}</w:body>
</w:document>"""

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", _STYLES)
        archive.writestr("docProps/core.xml", _CORE.format(title=_xml_escape(title)))
        archive.writestr("docProps/app.xml", _APP)
    return buffer.getvalue()


def build_template_docx() -> bytes:
    body = "".join(
        [
            _para(_run(TEMPLATE_TITLE, size=16, bold=True), jc="center", after=12),
            _para(
                _run("Jane Doe, John Smith", size=11),
                _run("\nExample University, Example City", size=10, italic=True),
                jc="center",
                after=18,
            ),
            _para(_run("Abstract", size=10, bold=True)),
            _para(_run(_SENTENCE + " " + _SENTENCE, size=10), jc="both",
                  line=1.0, after=18, first_line_pt=14),
            _para(_run("Keywords", size=10), _run("\u2014format checking, templates, compliance", size=10)),
            _para(_run("INTRODUCTION", size=10, bold=True), style="Heading1", after=8),
            _para(_run(_SENTENCE + " " + _SENTENCE, size=10), jc="both", line=1.0, first_line_pt=14),
            _para(_run("METHODOLOGY", size=10, bold=True), style="Heading1", after=8),
            _para(_run(_SENTENCE, size=10), jc="both", line=1.0, first_line_pt=14),
            _para(_run("RESULTS", size=10, bold=True), style="Heading1", after=8),
            _para(_run(_SENTENCE, size=10), jc="both", line=1.0, first_line_pt=14),
            _para(_run("CONCLUSION", size=10, bold=True), style="Heading1", after=8),
            _para(_run(_SENTENCE, size=10), jc="both", line=1.0, first_line_pt=14),
            _para(_run("REFERENCES", size=10, bold=True), style="Heading1", after=8),
            _para(_run("[1] A. Author, B. Author, Some Paper, Venue 2024.", size=9)),
            _para(_run("[2] C. Author, Another Paper, Venue 2025.", size=9)),
        ]
    )
    sect_pr = (
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/>'
        '<w:cols w:num="2" w:space="480"/>'
        '<w:docGrid w:linePitch="360"/></w:sectPr>'
    )
    return _document(body, sect_pr, TEMPLATE_TITLE)


def build_paper_docx() -> bytes:
    body = "".join(
        [
            _para(_run(PAPER_TITLE, family="Arial", size=14, bold=True), jc="center", after=12),
            _para(
                _run("Alice Lee, Bob Chen", family="Arial", size=12),
                _run("\nState University, Springfield", family="Arial", size=10, italic=True),
                jc="center",
                after=16,
            ),
            _para(_run("ABSTRACT", family="Arial", size=12, bold=True), style="Heading1", after=6),
            _para(
                _run(
                    "We study whether research papers comply with venue formatting requirements "
                    "automatically using deterministic parsing of cloud document APIs. Our prototype "
                    "compares normalized documents against extracted rules and reports violations.",
                    family="Arial", size=11,
                ),
                line=1.15,
            ),
            _para(_run("1. Introduction", family="Arial", size=11, bold=True), style="Heading1", after=6),
            _para(
                _run(
                    "Formatting requirements are tedious to verify manually. We introduce a pipeline "
                    "that parses documents and compares them against journal templates.",
                    family="Arial", size=11,
                ),
                line=1.15,
            ),
            _para(
                _run(
                    "Prior systems rely on heuristics over PDFs. In contrast, we operate on the "
                    "structured document model directly, which preserves typography faithfully.",
                    family="Arial", size=11,
                ),
                line=1.15,
            ),
            _para(_run("Results", family="Arial", size=11, bold=True), style="Heading1", after=6),
            _para(
                _run(
                    "On a corpus of fifty papers the system reaches high agreement with manual review "
                    "and produces actionable per-requirement diagnostics for authors.",
                    family="Arial", size=11,
                ),
                line=1.15,
            ),
            _para(_run("Conclusion", family="Arial", size=11, bold=True), style="Heading1", after=6),
            _para(
                _run(
                    "Automated compliance checking saves reviewers time and helps authors fix issues "
                    "early before submission deadlines arrive.",
                    family="Arial", size=11,
                ),
                line=1.15,
            ),
            _para(_run("References", family="Arial", size=11, bold=True), style="Heading1", after=6),
            _para(_run("[1] X. Yang, Format Matters, Journal of Documents, 2024.", family="Arial", size=10)),
        ]
    )
    sect_pr = (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>'
        '<w:cols w:num="1" w:space="0"/>'
        '<w:docGrid w:linePitch="360"/></w:sectPr>'
    )
    return _document(body, sect_pr, PAPER_TITLE)


@lru_cache(maxsize=1)
def demo_docx() -> tuple[bytes, bytes]:
    return build_template_docx(), build_paper_docx()


def write_sample_files(directory: str) -> None:
    from pathlib import Path

    target = Path(directory)
    template, paper = demo_docx()
    (target / "template.docx").write_bytes(template)
    (target / "paper.docx").write_bytes(paper)


if __name__ == "__main__":
    write_sample_files(".")