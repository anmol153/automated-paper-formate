"""Template inference against the real Springer LNCS (SPLNPROC) files.

These fixtures are the actual files Springer distributes to LNCS authors, and
they exposed three defects that synthetic fixtures never would:

* a two-column *table* inside single-column prose made the whole document look
  two-column;
* a template is mostly captions and back matter, so an unweighted vote put the
  body at 9pt when LNCS sets it at 10pt;
* LNCS prints an unnumbered bibliography with no "References" heading, so the
  reference count came back as zero.

A page limit, abstract budget and keyword policy appear in none of these files,
so they come from the family's published guidelines instead -- see
``venue_families``.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

from app.parsing.docx_parser import parse_docx
from app.parsing.pdf_parser import parse_pdf
from app.parsing.rule_inference import infer_ruleset_from_template
from app.parsing.venue_families import apply_preset, detect_family

SPRINGER_DIR = pathlib.Path(
    "/home/anmoldhiman/Downloads/Microsoft_Word_Proceedings_Templates-DeeD0b6b(1)"
)
INSTRUCTIONS_PDF = SPRINGER_DIR / "SPLNPROC Technical Instructions.pdf"
SPLNPROC_DOCM = SPRINGER_DIR / "splnproc2510.docm"

needs_springer_files = pytest.mark.skipif(
    not SPLNPROC_DOCM.is_file(),
    reason="Springer LNCS template files are not present on this machine",
)


@pytest.fixture(scope="module")
def docm_rules():
    return infer_ruleset_from_template(parse_docx(SPLNPROC_DOCM.read_bytes()), "splnproc2510.docm")


@needs_springer_files
def test_lncs_template_is_recognised():
    match = detect_family(parse_docx(SPLNPROC_DOCM.read_bytes()))
    assert match is not None
    assert match.key == "springer-lncs"
    assert match.confidence >= 0.75
    assert match.source, "a preset must say where its numbers came from"


@needs_springer_files
def test_instructions_pdf_is_single_column_despite_a_two_column_table():
    """Page 9 of the instructions is a two-column table in one-column prose."""
    doc = parse_pdf(INSTRUCTIONS_PDF.read_bytes()).document
    assert doc.columns == 1, "LNCS is single-column; a table must not change that"


@needs_springer_files
def test_measured_geometry_matches_the_official_text_area():
    """LNCS is A4 with a 122 x 193 mm text area, i.e. 44 mm sides, 52 mm top."""
    doc = parse_docx(SPLNPROC_DOCM.read_bytes()).document
    assert doc.page_size.label == "A4"
    assert doc.columns == 1
    width_mm = (doc.page_size.width_pt - doc.margins.left_pt - doc.margins.right_pt) / 72 * 25.4
    height_mm = (doc.page_size.height_pt - doc.margins.top_pt - doc.margins.bottom_pt) / 72 * 25.4
    assert width_mm == pytest.approx(122, abs=1.5)
    assert height_mm == pytest.approx(193, abs=1.5)


@needs_springer_files
def test_body_typography_is_10pt_not_the_9pt_of_captions(docm_rules):
    """Captions, references and back matter are 9pt; the body is 10pt."""
    assert docm_rules.typography.body.font_size_pt == pytest.approx(10.0)
    assert docm_rules.typography.body.font_family == "Times New Roman"
    assert docm_rules.typography.title.font_size_pt == pytest.approx(14.0)
    assert docm_rules.typography.title.bold is True


@needs_springer_files
def test_bibliography_is_found_without_a_references_heading():
    doc = parse_docx(SPLNPROC_DOCM.read_bytes())
    references = [b for b in doc.sections if b.type == "references"]
    assert len(references) >= 5, "the template ships a five-entry sample bibliography"
    assert all(b.format.font_size_pt == pytest.approx(9.0) for b in references)


@needs_springer_files
def test_policy_defaults_come_from_the_preset_not_the_file(docm_rules):
    assert docm_rules.pages.max_pages == 9
    assert docm_rules.sections.abstract_required is True
    assert docm_rules.sections.abstract_max_words == 250
    assert docm_rules.sections.keywords_required is True


@needs_springer_files
def test_an_exemplar_with_named_authors_is_not_treated_as_double_blind(docm_rules):
    assert docm_rules.anonymisation.required is False
    assert docm_rules.anonymisation.allow_author_block is True


@needs_springer_files
def test_preset_never_overwrites_measured_geometry():
    """The file is the authority for anything measurable."""
    doc = parse_docx(SPLNPROC_DOCM.read_bytes())
    rules = infer_ruleset_from_template(doc, "splnproc2510.docm")
    match = detect_family(doc)
    assert match is not None
    before = rules.pages.model_dump()
    apply_preset(rules, match)
    after = rules.pages.model_dump()
    for key in ("page_size_label", "orientation", "columns", "margins"):
        assert before[key] == after[key], f"preset changed measured field {key}"


def test_an_unrelated_template_is_not_given_a_venue_preset(tmp_path):
    """Detection must not fire on a document that merely resembles LNCS."""
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    sample = pathlib.Path(__file__).resolve().parents[2] / "samples" / "template.tex"
    from app.parsing.latex_parser import parse_latex

    doc = parse_latex(sample.read_text())
    assert detect_family(doc) is None


def test_reference_entry_detection_ignores_prose():
    from app.parsing.structure import looks_like_reference_entry

    assert looks_like_reference_entry("Author, F.: Article title. Journal 2 (5), 99-110 (2016)")
    assert looks_like_reference_entry("Smith, J., Doe, A.: A chapter. In: Editor, F. (2019)")
    assert not looks_like_reference_entry(
        "We follow the method of Smith et al. and extend it to the multi-column case."
    )
    assert not looks_like_reference_entry("Introduction")
