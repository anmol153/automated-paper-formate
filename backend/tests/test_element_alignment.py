"""Per-element alignment and heading levels.

Regressions from an LNCS paper whose report passed heading alignment against
the body's alignment, flip-flopped on the title, and failed headings because
12pt sections and 10pt subsections were checked against one size.
"""

from app.checks.engine import evaluate
from app.models.document import SectionBlock, TextFormat
from app.models.facts import PaperFacts
from app.models.rules import RuleSet, TypographyRule
from app.parsing.pdf_parser import LineInfo, _infer_alignment
from app.parsing.structure import RawBlock, classify_blocks, split_heading_levels

REGION = (124.7, 470.6)


def line(x0, x1, baseline):
    return LineInfo(x0=x0, y0=baseline - 10, x1=x1, y1=baseline + 2, baseline=baseline)


def heading(text, size):
    return SectionBlock(type="heading", name=text, text=text, format=TextFormat(font_size_pt=size))


def test_split_section_number_row_reads_as_left():
    # PyMuPDF emits "1" and "Introduction" as two lines on one baseline.
    assert _infer_alignment([line(124.7, 131.5, 100), line(144.9, 219.0, 100)], REGION) == "left"


def test_wide_symmetric_title_row_reads_as_centre():
    assert _infer_alignment([line(135.3, 460.1, 100)], REGION) == "center"


def test_justified_block_indented_both_sides_is_not_centre_or_right():
    rows = [line(153.1, 442.2, 100 + 11 * i) for i in range(4)] + [line(153.1, 300.0, 144)]
    assert _infer_alignment(rows, REGION) == "justified"


def test_two_line_bold_title_is_one_title_not_a_heading():
    blocks = [
        RawBlock("Automated Detection of Formatting Errors in", TextFormat(font_size_pt=14.35, bold=True)),
        RawBlock("Scientific Manuscripts", TextFormat(font_size_pt=14.35, bold=True, alignment="center"),
                 named_style_type="HEADING_1"),
        RawBlock("Jane Doe", TextFormat(font_size_pt=10)),
    ]
    sections = classify_blocks(blocks)
    assert sections[0].type == "title"
    assert sections[0].text.endswith("Scientific Manuscripts")
    assert sections[0].format.alignment == "center"
    assert not any(s.type == "heading" for s in sections)


def test_heading_levels_by_numbering_then_size():
    blocks = [
        heading("1 Introduction", 12), heading("3.1 Feature Extraction", 10),
        heading("References", 12), heading("A Subsection Sample", 10),
        heading("Sample Heading (Third Level).", 10), heading("2.1.1 Deep", 10),
    ]
    sections, subsections = split_heading_levels(blocks)
    assert [b.text for b in sections] == ["1 Introduction", "References"]
    assert [b.text for b in subsections] == ["3.1 Feature Extraction", "A Subsection Sample"]


def _results(facts, **typography):
    rules = RuleSet(typography=TypographyRule(**typography))
    return {r.id: r for r in evaluate(rules, facts)}


def test_title_and_heading_alignment_ignore_body_alignment():
    facts = PaperFacts()
    facts.typography.alignment_distribution = {"justified": 40}
    facts.typography.title_alignment = "center"
    facts.typography.heading_alignment = None

    results = _results(
        facts,
        title=TextFormat(alignment="center"),
        headings=TextFormat(alignment="justified"),
    )
    assert results["typography.title.alignment"].status == "passed"
    # Unmeasured heading alignment must not borrow the body's and pass.
    assert results["typography.heading.alignment"].status == "not_applicable"


def test_subheadings_have_their_own_size_rule():
    facts = PaperFacts()
    facts.typography.heading_font_size_pt = 11.96
    facts.typography.subheading_font_size_pt = 9.96

    results = _results(
        facts,
        headings=TextFormat(font_size_pt=12),
        subheadings=TextFormat(font_size_pt=10),
    )
    assert results["typography.heading.font_size_pt"].status == "passed"
    assert results["typography.subheading.font_size_pt"].status == "passed"
