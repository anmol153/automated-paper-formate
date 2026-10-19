from app.models.document import TextFormat
from app.parsing.structure import RawBlock, classify_blocks, match_canonical_section


def block(text, **fmt):
    return RawBlock(text=text, format=TextFormat(**fmt))


def test_canonical_matches_numbered_and_caps_headings():
    assert match_canonical_section("INTRODUCTION") == "Introduction"
    assert match_canonical_section("1 Introduction") == "Introduction"
    assert match_canonical_section("2. Methodology") == "Methodology"
    assert match_canonical_section("IV. RESULTS AND DISCUSSION") == "Results"
    assert match_canonical_section("Conclusions") == "Conclusion"
    assert match_canonical_section("References") == "References"


def test_plain_text_is_not_a_section():
    assert match_canonical_section("This paper presents a method for things.") is None


def test_classifies_full_paper_flow():
    blocks = [
        block("My Paper Title", bold=True),
        block("Jane Doe, John Smith", alignment="center"),
        block("ABSTRACT", bold=True),
        block("We study formatting compliance.", size=10),
        block("Keywords—compliance, parsing", size=10),
        block("1 INTRODUCTION", bold=True),
        block("Formatting matters for venues.", size=10),
        block("REFERENCES", bold=True),
        block("[1] Some Author, Some Paper.", size=9),
    ]
    sections = classify_blocks(blocks)

    types = [s.type for s in sections]
    assert types[0] == "title"
    assert types[1] == "authors"
    assert any(s.type == "abstract" for s in sections)
    keywords = next(s for s in sections if s.type == "keywords")
    assert keywords.text == "compliance, parsing"
    headings = [s.name for s in sections if s.type == "heading"]
    assert "Introduction" in headings and "References" in headings

    reference_body = [s for s in sections if s.type == "body" and s.name == "References"]
    assert len(reference_body) == 1


def test_title_skipped_when_doc_starts_with_abstract():
    sections = classify_blocks([block("ABSTRACT"), block("Content here.")])
    assert all(s.type != "title" for s in sections)
    assert any(s.type == "abstract" for s in sections)


def test_aggregate_formats_majority():
    from app.parsing.structure import aggregate_formats

    formats = [
        TextFormat(font_family="Arial", font_size_pt=11, alignment="left"),
        TextFormat(font_family="Arial", font_size_pt=11, alignment="left"),
        TextFormat(font_family="Times New Roman", font_size_pt=10, alignment="justified"),
    ]
    agg = aggregate_formats(formats)
    assert agg.font_family == "Arial"
    assert agg.font_size_pt == 11
    assert agg.alignment == "left"
