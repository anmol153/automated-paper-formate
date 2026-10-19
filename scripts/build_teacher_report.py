"""Build the shareable teacher report as DOCX using only the Python standard library.

Run from any directory: .venv/bin/python scripts/build_teacher_report.py
The source is docs/TEACHER_PROJECT_REPORT.md. Existing PNG captures are embedded
unchanged. No application data, credentials, network calls or dependencies are used.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/TEACHER_PROJECT_REPORT.md"
OUTPUT = SOURCE.with_suffix(".docx")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_WIDTH = 9746


def runs(value: str, size: int | None = None, bold: bool = False) -> str:
    parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))", value)
    output = []
    for part in parts:
        if not part:
            continue
        code = part.startswith("`") and part.endswith("`")
        strong = part.startswith("**") and part.endswith("**")
        link = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", part)
        text = part[1:-1] if code else part[2:-2] if strong else link[1] if link else part
        properties = []
        if code:
            properties.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
        if strong or bold:
            properties.append("<w:b/>")
        if size:
            properties.append(f'<w:sz w:val="{size}"/>')
        if link:
            properties.append('<w:color w:val="245EDB"/>')
        output.append(f'<w:r><w:rPr>{"".join(properties)}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>')
    return "".join(output)


def paragraph(text: str = "", style: str = "Normal", size: int | None = None, extra: str = "", bold: bool = False) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{extra}</w:pPr>{runs(text, size, bold)}</w:p>'


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def table(rows: list[list[str]]) -> str:
    columns = max(map(len, rows))
    # Give label columns only the space they need and reserve most of the page
    # for explanatory text. Equal thirds made the implementation matrices wrap
    # into tall, difficult-to-scan cells in both Word and the PDF export.
    proportions = {2: [0.28, 0.72], 3: [0.22, 0.38, 0.40]}.get(columns, [1 / columns] * columns)
    widths = [int(CONTENT_WIDTH * value) for value in proportions]
    widths[-1] += CONTENT_WIDTH - sum(widths)
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    body = []
    for index, row in enumerate(rows):
        cells = []
        for column, cell in enumerate(row):
            shading = '<w:shd w:fill="EAF0FF"/>' if index == 0 else '<w:shd w:fill="F8FAFC"/>' if index % 2 == 0 else ""
            cell_paragraph = paragraph(cell, "TableText", 19, bold=index == 0)
            if index == 0:
                # Keep the repeated table heading with the first data row when
                # Word or Writer paginates a table across pages.
                cell_paragraph = cell_paragraph.replace("</w:pPr>", "<w:keepNext/></w:pPr>", 1)
            cells.append(f'<w:tc><w:tcPr><w:tcW w:w="{widths[column]}" w:type="dxa"/>{shading}<w:vAlign w:val="top"/></w:tcPr>{cell_paragraph}</w:tc>')
        header = '<w:tblHeader/>' if index == 0 else ""
        body.append(f'<w:tr><w:trPr>{header}<w:cantSplit/></w:trPr>{"".join(cells)}</w:tr>')
    return f'''<w:tbl><w:tblPr><w:tblW w:w="{CONTENT_WIDTH}" w:type="dxa"/><w:tblLayout w:type="fixed"/>
      <w:tblBorders><w:top w:val="single" w:sz="4" w:color="D1D9E0"/><w:left w:val="single" w:sz="4" w:color="D1D9E0"/><w:bottom w:val="single" w:sz="4" w:color="D1D9E0"/><w:right w:val="single" w:sz="4" w:color="D1D9E0"/><w:insideH w:val="single" w:sz="4" w:color="D1D9E0"/><w:insideV w:val="single" w:sz="4" w:color="D1D9E0"/></w:tblBorders>
      <w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>
      </w:tblPr><w:tblGrid>{grid}</w:tblGrid>{"".join(body)}</w:tbl>'''


def picture(path: Path, index: int, alt: str) -> str:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Expected a PNG capture: {path}")
    width, height = struct.unpack(">II", data[16:24])
    # Preserve the full capture and its aspect ratio. Leave room for its caption.
    scale = min(6.55 * 914400 / width, 7.4 * 914400 / height)
    cx, cy = int(width * scale), int(height * scale)
    description = escape(alt, {'"': '&quot;'})
    return f'''<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>
      <wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{index}" name="Figure {index}" descr="{description}"/>
        <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{index}" name="Figure {index}"/><pic:cNvPicPr/></pic:nvPicPr>
            <pic:blipFill><a:blip r:embed="image{index}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
            <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
          </pic:pic></a:graphicData></a:graphic>
      </wp:inline></w:drawing></w:r></w:p>'''


def build() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    headings = [line[3:] for line in lines if line.startswith("## ") and not line.startswith("## Conference Paper")]
    body = [paragraph("PAPER-FORMAT", "CoverTitle"), paragraph("Conference Paper Submission, Formatting Validation and Peer Review Platform", "CoverSubtitle"),
            paragraph("Detailed implementation and progress report", "CoverLead"), paragraph("Prepared for faculty / project mentor review", "CoverLead"),
            paragraph("19 October 2026", "CoverLead"), paragraph("Integrated local prototype · Implementation, evidence and next steps", "CoverLead"), page_break(), paragraph("Contents", "Heading1")]
    body.extend(paragraph(heading, "Contents") for heading in headings)
    body.append(page_break())
    images: list[Path] = []
    index = next(i for i, line in enumerate(lines) if line == "## Executive summary")
    code = False
    figure = False
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue
        if line.startswith("```"):
            code = not code
            index += 1
            continue
        if code:
            body.append(paragraph(line, "Code"))
        elif line.startswith("## "):
            if line.startswith("## Appendix"):
                body.append(page_break())
            body.append(paragraph(line[3:], "Heading1"))
        elif line.startswith("### "):
            if line.startswith("### Figure"):
                if figure:
                    body.append(page_break())
                figure = True
            body.append(paragraph(line[4:], "Heading2"))
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell or " ") for cell in cells):
                    rows.append(cells)
                index += 1
            body.append(table(rows))
            body.append(paragraph("", "TableGap"))
            continue
        elif match := re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line):
            path = (SOURCE.parent / match[2]).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError(f"Missing or out-of-repository figure: {path}")
            images.append(path)
            body.append(picture(path, len(images), match[1]))
        elif line.startswith("- "):
            body.append(paragraph("• " + line[2:], "List"))
        elif re.match(r"\d+\. ", line):
            body.append(paragraph(line, "List"))
        else:
            # Rejoin wrapped prose while preserving intentional paragraph boundaries.
            fragments = [line]
            while index + 1 < len(lines) and lines[index + 1].strip() and not re.match(r"^(#|\||-|```|!\[|\d+\. )", lines[index + 1]):
                index += 1
                fragments.append(lines[index].strip())
            body.append(paragraph(" ".join(fragments), "Caption" if figure else "Normal"))
        index += 1

    section = '<w:sectPr><w:headerReference w:type="default" r:id="header"/><w:footerReference w:type="default" r:id="footer"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="500" w:footer="500"/><w:titlePg/></w:sectPr>'
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{"".join(body)}{section}</w:body></w:document>'
    styles = f'''<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="{W}">
      <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/><w:color w:val="1F2328"/><w:lang w:val="en-IN"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults>
      <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
      <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="280" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="194BB8"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="Heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="180" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="25"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="CoverTitle"><w:name w:val="Title"/><w:pPr><w:spacing w:before="1600" w:after="320"/></w:pPr><w:rPr><w:b/><w:sz w:val="68"/><w:color w:val="245EDB"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="CoverSubtitle"><w:pPr><w:spacing w:after="500"/></w:pPr><w:rPr><w:b/><w:sz w:val="38"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="CoverLead"><w:pPr><w:spacing w:after="200"/></w:pPr><w:rPr><w:sz w:val="24"/><w:color w:val="59636E"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Contents"><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="110"/></w:pPr><w:rPr><w:sz w:val="22"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="List"><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="260" w:hanging="230"/><w:spacing w:after="100"/></w:pPr></w:style>
      <w:style w:type="paragraph" w:styleId="Code"><w:pPr><w:spacing w:after="80" w:line="280"/><w:shd w:fill="F0F3F6"/><w:ind w:left="120"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="17"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="TableText"><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="30" w:line="240"/></w:pPr><w:rPr><w:sz w:val="19"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="TableGap"><w:pPr><w:spacing w:after="100"/></w:pPr><w:rPr><w:sz w:val="4"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Caption"><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="120"/></w:pPr><w:rPr><w:sz w:val="20"/><w:color w:val="59636E"/></w:rPr></w:style>
    </w:styles>'''
    ET.register_namespace("w", W)
    style_tree = ET.fromstring(styles)
    for style in style_tree.findall(f"{{{W}}}style"):
        if style.find(f"{{{W}}}name") is None:
            style.insert(0, ET.Element(f"{{{W}}}name", {f"{{{W}}}val": style.get(f"{{{W}}}styleId")}))
        if style.get(f"{{{W}}}styleId") != "Normal" and style.find(f"{{{W}}}basedOn") is None:
            style.insert(1, ET.Element(f"{{{W}}}basedOn", {f"{{{W}}}val": "Normal"}))
        if style.get(f"{{{W}}}styleId") == "Normal":
            properties = ET.SubElement(style, f"{{{W}}}rPr")
            ET.SubElement(properties, f"{{{W}}}rFonts", {f"{{{W}}}ascii": "Liberation Sans", f"{{{W}}}hAnsi": "Liberation Sans"})
            ET.SubElement(properties, f"{{{W}}}sz", {f"{{{W}}}val": "22"})
    styles = ET.tostring(style_tree, encoding="unicode")
    relationships = [('<Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'),
                     '<Relationship Id="header" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>',
                     '<Relationship Id="footer" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>']
    relationships.extend(f'<Relationship Id="image{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{i}.png"/>' for i in range(1, len(images) + 1))
    types = '''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'''
    header = f'<w:hdr xmlns:w="{W}">{paragraph("PAPER-FORMAT  |  Implementation and Progress Report", "Normal", 18, extra="<w:spacing w:after=\"0\"/>")}</w:hdr>'
    footer = f'<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:jc w:val="right"/></w:pPr>{runs("Faculty review · 19 October 2026  |  Page ", 18)}<w:fldSimple w:instr="PAGE"><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p></w:ftr>'
    core = '<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Paper-Format — Detailed Implementation and Progress Report</dc:title><dc:subject>Conference submission, formatting validation, collaboration and peer review</dc:subject><dc:description>Faculty review report; no demo credentials included.</dc:description></cp:coreProperties>'
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("_rels/.rels", f'<Relationships xmlns="{REL}"><Relationship Id="document" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="core" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>')
        archive.writestr("docProps/core.xml", core)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)
        archive.writestr("word/_rels/document.xml.rels", f'<Relationships xmlns="{REL}">{"".join(relationships)}</Relationships>')
        archive.writestr("word/header1.xml", header)
        archive.writestr("word/footer1.xml", footer)
        for i, path in enumerate(images, 1):
            archive.write(path, f"word/media/image{i}.png")
    print(f"Created {OUTPUT.relative_to(ROOT)} with {len(images)} unchanged screenshots.")


if __name__ == "__main__":
    build()
