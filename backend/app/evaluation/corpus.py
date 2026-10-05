"""Non-compliant evaluation corpus.

Each fixture is a LaTeX (or other) paper built to violate a known, enumerated
set of rules, and each declares that set as ground truth. The evaluation runs
the rule engine over every fixture and compares what it reported against what
was deliberately broken, which is what "does the system check what a human would
check" means operationally.

Flaws are declared at the level of rule *ids* plus a human-readable note, so a
missed detection names the rule that should have fired, and a false positive
names the rule that fired without cause.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from io import BytesIO


@dataclass
class GroundTruthFlaw:
    rule_id: str
    note: str


@dataclass
class Fixture:
    name: str
    filename: str
    data: bytes
    expected_flaws: list[GroundTruthFlaw] = field(default_factory=list)
    expected_verdict: str = "rejected"
    description: str = ""


# --------------------------------------------------------------------------- #
# LaTeX building blocks
# --------------------------------------------------------------------------- #

FILLER = (
    "We evaluate the proposed system on a stratified corpus and report agreement with "
    "expert annotators across every condition. "
)


def _long_body(sections: int = 10, repeat: int = 14) -> str:
    """A long body that still contains every required section.

    A paper that is only long because it omits the required headings would trip
    the section rules as well, which would hide the page-limit signal.
    """
    required = ["Introduction", "Related Work", "Methodology", "Results", "Conclusion"]
    parts = [f"\\section{{{name}}}\n{FILLER * 3}" for name in required]
    for i in range(1, max(0, sections - len(required)) + 1):
        parts.append(f"\\section{{Analysis {i}}}\n{FILLER * repeat}")
    return "\n".join(parts)


def _long_body_missing(sections: int = 12, repeat: int = 18) -> str:
    """A long body that deliberately omits Related Work, Methodology and Conclusion."""
    parts = ["\\section{Introduction}\n" + FILLER * 3, "\\section{Results}\n" + FILLER * 3]
    for i in range(1, max(0, sections - 2) + 1):
        parts.append(f"\\section{{Analysis {i}}}\n{FILLER * repeat}")
    return "\n".join(parts)


def _latex(
    *,
    docclass: str = "article",
    class_options: str = "[11pt,a4paper]",
    geometry: str | None = "\\usepackage[a4paper,margin=2.5cm]{geometry}",
    font_packages: str = "\\usepackage{mathptmx}",
    linespread: str | None = None,
    parindent: str | None = None,
    title: str = "A Compliant Anonymous Paper",
    author: str | None = "Anonymous Author",
    abstract: str | None = "A concise abstract describing the work in a few sentences.",
    keywords: str | None = "keywords, formatting, compliance",
    sections: str | None = None,
    references: int = 4,
    acknowledgements: str | None = None,
    funding: str | None = None,
    email: str | None = None,
    affiliation: str | None = None,
    extra_preamble: str = "",
) -> str:
    parts = [f"\\documentclass{class_options}{{{docclass}}}"]
    if geometry:
        parts.append(geometry)
    if font_packages:
        parts.append(font_packages)
    if linespread:
        parts.append(linespread)
    if parindent:
        parts.append(parindent)
    if extra_preamble:
        parts.append(extra_preamble)

    parts.append("\\begin{document}")
    parts.append(f"\\title{{{title}}}")
    if author is not None:
        parts.append(f"\\author{{{author}}}")
    parts.append("\\maketitle")

    if abstract is not None:
        parts.append("\\begin{abstract}\n" + abstract + "\n\\end{abstract}")
    if keywords is not None:
        parts.append("\\begin{keywords}\n" + keywords + "\n\\end{keywords}")

    default_sections = (
        "\\section{Introduction}\n" + FILLER * 3
        + "\n\\section{Related Work}\n" + FILLER * 3
        + "\n\\section{Methodology}\n" + FILLER * 3
        + "\n\\section{Results}\n" + FILLER * 3
        + "\n\\section{Conclusion}\n" + FILLER * 3
    )
    parts.append(sections if sections is not None else default_sections)

    if acknowledgements:
        parts.append("\\section{Acknowledgements}\n" + acknowledgements)
    if funding:
        parts.append("\\section{Funding}\n" + funding)
    if email:
        parts.append("\\section{Contact}\nCorresponding author: " + email)
    if affiliation:
        parts.append("\\section{Affiliation}\n" + affiliation)

    if references:
        refs = "\n".join(
            f"[{i}] A. Author{i}, B. Author{i}, Title {i}, Journal {i}, {2000 + i}."
            for i in range(1, references + 1)
        )
        parts.append("\\section{References}\n" + refs)

    parts.append("\\end{document}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# rule set used by the evaluation
# --------------------------------------------------------------------------- #


def evaluation_rules():
    """The publisher template the corpus is written against."""
    from app.models.document import Margins, TextFormat
    from app.models.rules import (
        AnonymisationRule,
        DecisionRule,
        FileTypeRule,
        PageRule,
        ParagraphRule,
        PublisherDetails,
        RuleSet,
        SectionRule,
        ToleranceRule,
        TypographyRule,
    )

    return RuleSet(
        name="Evaluation Venue 2026",
        description="Two-column anonymous conference, Times 10pt, 8 page limit.",
        publisher=PublisherDetails(
            publisher_name="Evaluation Press",
            conference_name="Evaluation Venue 2026",
            contact_email="format@evaluation.org",
            notes_for_authors="Submit a single anonymised PDF.",
        ),
        file_type=FileTypeRule(
            accepted_extensions=["pdf", "tex", "docx"],
            max_file_size_mb=20,
            # Source uploads are allowed so that the corpus can isolate a file-type
            # violation instead of every fixture tripping it at once.
            allow_source_upload=True,
        ),
        pages=PageRule(
            max_pages=8,
            page_size_label="A4",
            orientation="portrait",
            columns=2,
            margins=Margins(top_pt=64, bottom_pt=64, left_pt=54, right_pt=54),
        ),
        sections=SectionRule(
            required_sections=[
                "Abstract", "Introduction", "Related Work", "Methodology",
                "Results", "Conclusion", "References",
            ],
            abstract_required=True,
            abstract_max_words=200,
            keywords_required=True,
            min_reference_entries=3,
        ),
        anonymisation=AnonymisationRule(
            required=True,
            allow_author_block=False,
            detect_emails=True,
            detect_affiliations=True,
            detect_acknowledgements=True,
            detect_funding_statements=True,
            detect_orcid=True,
            detect_self_citation=True,
            detect_pdf_metadata=True,
        ),
        typography=TypographyRule(
            body=TextFormat(font_family="Times New Roman", font_size_pt=10),
            headings=TextFormat(font_family="Times New Roman", font_size_pt=10, bold=True),
            tolerance=ToleranceRule(
                font_size_pt=0.51,
                min_font_size_pt=9.0,
                max_font_size_pt=12.0,
            ),
        ),
        paragraph=ParagraphRule(line_spacing=1.0, require_justified_body=True),
        # A strict venue: anything the engine flags at warning level is enough to
        # send a paper back. This is what a hand-check by a conscientious manager
        # does in practice, so it is the configuration worth measuring.
        decision=DecisionRule(reject_if_any_blocking=True, reject_if_any_warning=True),
    )


# --------------------------------------------------------------------------- #
# a genuinely compliant paper
# --------------------------------------------------------------------------- #

# Matches evaluation_rules(): A4, two columns, 64pt top/bottom, 54pt left/right,
# Times at 10pt. Anything that drifts from this belongs in a violating fixture,
# not in the baseline.
COMPLIANT_PREAMBLE = {
    "class_options": "[10pt,a4paper,twocolumn]",
    "geometry": "\\usepackage[a4paper,top=64pt,bottom=64pt,left=54pt,right=54pt]{geometry}",
    "font_packages": "\\usepackage{mathptmx}",
    # Declared explicitly so the line-spacing rule is measurable rather than
    # unreadable: an unverifiable value would otherwise force needs_review.
    "linespread": "\\linespread{1.0}",
}


def compliant_paper(**overrides) -> str:
    """Build a paper that satisfies every rule in :func:`evaluation_rules`."""
    kwargs = dict(COMPLIANT_PREAMBLE)
    kwargs.update(overrides)
    return _latex(**kwargs)


# --------------------------------------------------------------------------- #
# the corpus
# --------------------------------------------------------------------------- #


def build_corpus() -> list[Fixture]:
    fixtures: list[Fixture] = []

    # 1. Fully compliant baseline: nothing should be reported. If this fixture
    #    ever fails, every other number in the report is suspect.
    fixtures.append(
        Fixture(
            name="compliant-baseline",
            filename="compliant.tex",
            data=compliant_paper().encode("utf-8"),
            expected_flaws=[],
            expected_verdict="accepted",
            description="Meets every configured rule.",
        )
    )

    # 2. Wrong file type: a legacy .doc that the template does not accept.
    fixtures.append(
        Fixture(
            name="wrong-file-type",
            filename="manuscript.doc",
            data=b"{\\rtf1\\ansi Word 97 content that the parser cannot read.}",
            expected_flaws=[
                GroundTruthFlaw("file.ingest", "Content is not a parseable document"),
            ],
            description="Unsupported file type and unreadable content.",
        )
    )

    # 3. Way over the page limit.
    fixtures.append(
        Fixture(
            name="over-page-limit",
            filename="long.tex",
            data=compliant_paper(sections=_long_body(30, 20), references=6).encode("utf-8"),
            expected_flaws=[GroundTruthFlaw("page.limit", "Far beyond the 8-page limit")],
            description="Excessive length.",
        )
    )

    # 4. Missing required sections.
    fixtures.append(
        Fixture(
            name="missing-sections",
            filename="incomplete.tex",
            data=compliant_paper(
                sections=(
                    "\\section{Introduction}\n" + FILLER * 3
                    + "\n\\section{Results}\n" + FILLER * 3
                )
            ).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("structure.section.related_work", "No Related Work section"),
                GroundTruthFlaw("structure.section.methodology", "No Methodology section"),
                GroundTruthFlaw("structure.section.conclusion", "No Conclusion section"),
            ],
            description="Skeletal paper missing three required sections.",
        )
    )

    # 5. No abstract, no keywords.
    fixtures.append(
        Fixture(
            name="no-abstract-no-keywords",
            filename="no-abstract.tex",
            data=compliant_paper(abstract=None, keywords=None).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("structure.abstract", "Abstract removed"),
                GroundTruthFlaw("structure.section.abstract", "Abstract section removed"),
                GroundTruthFlaw("structure.keywords", "Keywords removed"),
            ],
            description="Front matter stripped.",
        )
    )

    # 6. Anonymisation failures: author block, email, affiliation, ack, funding.
    fixtures.append(
        Fixture(
            name="not-anonymous",
            filename="identified.tex",
            data=compliant_paper(
                author="Maria Santos, Johan Bergstrom",
                email="m.santos@university-example.edu",
                affiliation="Department of Computer Science, Riverside Institute of Technology, Springfield",
                acknowledgements="We thank the anonymous reviewers for their helpful comments on this work.",
                funding="This work was supported by grant R01GM123456 from the National Science Foundation.",
            ).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("anonymisation.author_block", "Real author names present"),
                GroundTruthFlaw("anonymisation.emails", "Corresponding email present"),
                GroundTruthFlaw("anonymisation.affiliations", "Institution named"),
                GroundTruthFlaw("anonymisation.acknowledgements", "Acknowledgements reveal identity"),
                GroundTruthFlaw("anonymisation.funding", "Grant number present"),
            ],
            description="Double-blind violation across the board.",
        )
    )

    # 7. Self-citation in first person.
    fixtures.append(
        Fixture(
            name="self-citation",
            filename="selfcite.tex",
            data=compliant_paper(
                sections=(
                    "\\section{Introduction}\n" + FILLER * 2
                    + "\nIn our previous work we proposed a related pipeline, which we extend here."
                )
                + "\n\\section{Related Work}\n" + FILLER * 3
                + "\n\\section{Methodology}\n" + FILLER * 3
                + "\n\\section{Results}\n" + FILLER * 3
                + "\n\\section{Conclusion}\n" + FILLER * 3
            ).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("anonymisation.self_citation", "First-person self-reference"),
            ],
            expected_verdict="rejected",
            description="Self-citation that a reviewer could de-anonymise from.",
        )
    )

    # 8. Wrong page geometry: A5, single column, wrong margins.
    fixtures.append(
        Fixture(
            name="wrong-page-geometry",
            filename="geometry.tex",
            data=_latex(
                class_options="[10pt,a5paper,twocolumn]",
                geometry="\\usepackage[a5paper,margin=4cm]{geometry}",
                font_packages="\\usepackage{mathptmx}",
                linespread="\\linespread{1.0}",
            ).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("layout.page_size", "A5 instead of A4"),
                GroundTruthFlaw("layout.margins", "4 cm margins instead of 54/64 pt"),
            ],
            description="Wrong trim size and margins.",
        )
    )

    # 9. Single column instead of two.
    fixtures.append(
        Fixture(
            name="single-column",
            filename="onecol.tex",
            data=_latex(
                class_options="[10pt,a4paper,onecolumn]",
                geometry="\\usepackage[a4paper,top=64pt,bottom=64pt,left=54pt,right=54pt]{geometry}",
                font_packages="\\usepackage{mathptmx}",
                linespread="\\linespread{1.0}",
            ).encode("utf-8"),
            expected_flaws=[GroundTruthFlaw("layout.columns", "1 column instead of 2")],
            description="Column count mismatch.",
        )
    )

    # 10. Wrong typography: Helvetica 12pt instead of Times 10pt.
    fixtures.append(
        Fixture(
            name="wrong-font",
            filename="helvetica.tex",
            data=_latex(
                class_options="[12pt,a4paper,twocolumn]",
                geometry="\\usepackage[a4paper,top=64pt,bottom=64pt,left=54pt,right=54pt]{geometry}",
                font_packages="\\usepackage{helvet}",
                linespread="\\linespread{1.0}",
            ).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("typography.body.font_family", "Helvetica instead of Times"),
                GroundTruthFlaw("typography.body.font_size_pt", "12 pt instead of 10 pt"),
                GroundTruthFlaw("typography.heading.font_family", "Helvetica headings"),
                GroundTruthFlaw("typography.heading.font_size_pt", "12 pt headings"),
            ],
            description="Wrong typeface and size.",
        )
    )

    # 11. Too few references.
    fixtures.append(
        Fixture(
            name="too-few-references",
            filename="thin-bib.tex",
            data=compliant_paper(references=1).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("structure.references", "1 reference where 3 are required"),
            ],
            description="Insufficient bibliography.",
        )
    )

    # 12. Over-long abstract.
    fixtures.append(
        Fixture(
            name="abstract-too-long",
            filename="verbose-abstract.tex",
            data=compliant_paper(abstract=FILLER * 40).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("structure.abstract_length", "Abstract far beyond 200 words"),
            ],
            expected_verdict="rejected",
            description="Abstract length violation.",
        )
    )

    # 13. Combined kitchen sink.
    fixtures.append(
        Fixture(
            name="everything-wrong",
            filename="kitchen-sink.tex",
            data=_latex(
                class_options="[12pt,a5paper,onecolumn]",
                geometry="\\usepackage[a5paper,margin=4cm]{geometry}",
                font_packages="\\usepackage{helvet}",
                linespread="\\linespread{1.0}",
                author="Maria Santos, Johan Bergstrom",
                abstract=None,
                keywords=None,
                sections=_long_body_missing(12, 18),
                references=1,
                email="m.santos@university-example.edu",
                affiliation="Riverside Institute of Technology",
            ).encode("utf-8"),
            expected_flaws=[
                GroundTruthFlaw("page.limit", "Longer than 8 pages"),
                GroundTruthFlaw("structure.abstract", "No abstract"),
                GroundTruthFlaw("structure.section.abstract", "No Abstract section"),
                GroundTruthFlaw("structure.keywords", "No keywords"),
                GroundTruthFlaw("structure.section.related_work", "No Related Work"),
                GroundTruthFlaw("structure.section.methodology", "No Methodology"),
                GroundTruthFlaw("structure.section.conclusion", "No Conclusion"),
                GroundTruthFlaw("structure.references", "Only 1 reference"),
                GroundTruthFlaw("layout.page_size", "A5 not A4"),
                GroundTruthFlaw("layout.columns", "1 column not 2"),
                GroundTruthFlaw("layout.margins", "Wrong margins"),
                GroundTruthFlaw("typography.body.font_family", "Helvetica not Times"),
                GroundTruthFlaw("typography.body.font_size_pt", "12 pt not 10 pt"),
                GroundTruthFlaw("typography.heading.font_family", "Helvetica headings"),
                GroundTruthFlaw("typography.heading.font_size_pt", "12 pt headings"),
                GroundTruthFlaw("anonymisation.author_block", "Authors present"),
                GroundTruthFlaw("anonymisation.emails", "Email present"),
                GroundTruthFlaw("anonymisation.affiliations", "Institution present"),
            ],
            description="Every major rule violated at once.",
        )
    )

    # 14. PDF metadata leak: author/creator set in the file properties.
    fixtures.append(_pdf_with_metadata())

    # 15. A file that is not a paper at all.
    fixtures.append(
        Fixture(
            name="not-a-paper",
            filename="readme.txt",
            data=b"This is a plain text readme, not a manuscript.\n",
            expected_flaws=[GroundTruthFlaw("file.ingest", "Not a parseable document")],
            description="Wrong file type entirely.",
        )
    )

    return fixtures


def _pdf_with_metadata() -> Fixture:
    """A one-page PDF whose document properties name the authors.

    ``pymupdf`` writes those properties on save, so the anonymisation rule has
    something real to detect rather than a synthetic dict.
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Anonymised Paper Title", fontsize=16)
    page.insert_text((72, 110), "Abstract", fontsize=12)
    page.insert_text((72, 130), "An abstract that satisfies the length rule comfortably.", fontsize=10)
    page.insert_text((72, 160), "1 Introduction", fontsize=11)
    page.insert_text((72, 180), FILLER * 6, fontsize=10)
    page.insert_text((72, 320), "2 Related Work", fontsize=11)
    page.insert_text((72, 340), FILLER * 6, fontsize=10)
    page.insert_text((72, 480), "3 Methodology", fontsize=11)
    page.insert_text((72, 500), FILLER * 6, fontsize=10)
    page.insert_text((72, 640), "4 Results", fontsize=11)
    page.insert_text((72, 660), FILLER * 6, fontsize=10)
    page.insert_text((72, 780), "5 Conclusion", fontsize=11)
    page.insert_text((72, 800), FILLER * 4, fontsize=10)
    page.insert_text((72, 760), "Keywords: formatting, compliance", fontsize=10)

    doc.set_metadata(
        {
            "title": "Anonymised Paper Title",
            "author": "Maria Santos; Johan Bergstrom",
            "subject": "Riverside Institute of Technology grant R01GM123456",
            "keywords": "Maria Santos, m.santos@university-example.edu",
            "creator": "m.santos@university-example.edu",
            "producer": "Microsoft Word 16.0",
        }
    )
    data = doc.tobytes()
    doc.close()

    return Fixture(
        name="pdf-metadata-leak",
        filename="paper.pdf",
        data=data,
        expected_flaws=[
            GroundTruthFlaw("anonymisation.metadata.author", "Author metadata names the authors"),
            GroundTruthFlaw("anonymisation.metadata.creator", "Creator field holds an email"),
            # This fixture is a hand-built single-column A4 page, so the layout and
            # typography rules below are genuine findings, not noise. Only
            # metadata.title and metadata.producer are left undeclared on purpose:
            # neither a document title nor "Microsoft Word 16.0" identifies an
            # author, so flagging them is over-reporting.
            GroundTruthFlaw("anonymisation.metadata.subject", "Subject names the institution and grant"),
            GroundTruthFlaw("anonymisation.metadata.keywords", "Keywords hold the author name and email"),
            GroundTruthFlaw("layout.columns", "Single column"),
            GroundTruthFlaw("layout.margins", "1 inch margins, not 54/64 pt"),
            GroundTruthFlaw("paragraph.justified", "Body text is left-aligned"),
            GroundTruthFlaw("paragraph.line_spacing", "Single spacing not asserted as 1.0"),
            GroundTruthFlaw("structure.section.references", "No References section"),
            GroundTruthFlaw("typography.body.font_family", "Helvetica, not Times"),
            GroundTruthFlaw("typography.heading.font_family", "Helvetica headings"),
            GroundTruthFlaw("typography.heading.font_size_pt", "11 pt headings, not 10 pt"),
        ],
        expected_verdict="rejected",
        description="Anonymised body, but identifying PDF document properties.",
    )


def docx_fixture() -> Fixture:
    """A Word submission, to prove the DOCX path is exercised by the evaluation."""
    buffer = BytesIO()
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>A Word Submission</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Maria Santos</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Abstract</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>An abstract that is comfortably inside the word limit.</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Keywords: formatting, compliance</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>1 Introduction</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>' + FILLER * 4 + '</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>2 Related Work</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>' + FILLER * 4 + '</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>3 Methodology</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>' + FILLER * 4 + '</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>4 Results</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>' + FILLER * 4 + '</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>5 Conclusion</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>' + FILLER * 3 + '</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>6 References</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>[1] A. Author, A Title, 2021.</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>[2] B. Author, Another Title, 2022.</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>[3] C. Author, A Third Title, 2023.</w:t></w:r></w:p>'
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}"
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
        'w:header="708" w:footer="708" w:gutter="0"/>'
        '<w:cols w:num="1"/></w:sectPr>'
        "</w:body></w:document>"
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>A Word Submission</dc:title>"
        "<dc:creator>Maria Santos</dc:creator>"
        "<cp:lastModifiedBy>Maria Santos</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml",
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                    "</Types>")
        zf.writestr("_rels/.rels",
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                    "</Relationships>")
        zf.writestr("word/document.xml", document)
        zf.writestr("docProps/core.xml", core)

    return Fixture(
        name="word-identified",
        filename="paper.docx",
        data=buffer.getvalue(),
        expected_flaws=[
            GroundTruthFlaw("anonymisation.author_block", "Author name in the document"),
            # The generated document really is a single-column A4 page with 2 cm
            # margins and no explicit fonts, so these are true findings.
            GroundTruthFlaw("layout.columns", "Single column"),
            GroundTruthFlaw("layout.margins", "2 cm margins, not 54/64 pt"),
            GroundTruthFlaw("paragraph.line_spacing", "Line spacing not asserted as 1.0"),
            GroundTruthFlaw("typography.body.font_family", "No Times font applied"),
            GroundTruthFlaw("typography.body.font_size_pt", "Body size not 10 pt"),
            GroundTruthFlaw("typography.heading.font_family", "No Times font on headings"),
            GroundTruthFlaw("typography.heading.font_size_pt", "Heading size not 10 pt"),
        ],
        expected_verdict="rejected",
        description="Word submission with the author in the body.",
    )


__all__ = ["Fixture", "GroundTruthFlaw", "build_corpus", "evaluation_rules", "docx_fixture"]
