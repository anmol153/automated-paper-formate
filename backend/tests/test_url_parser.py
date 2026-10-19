import pytest

from app.google.url_parser import extract_doc_id


def test_extracts_id_from_edit_url():
    assert (
        extract_doc_id("https://docs.google.com/document/d/1AbC_deF-1234567890abcdefghijk/edit#heading=h.x")
        == "1AbC_deF-1234567890abcdefghijk"
    )


def test_extracts_id_from_published_url():
    assert (
        extract_doc_id("https://docs.google.com/document/d/e/2PACX-1vSQwErTyUiOpAsDfGhJkLzXcVbNm/pub")
        == "2PACX-1vSQwErTyUiOpAsDfGhJkLzXcVbNm"
    )


def test_extracts_id_from_export_query():
    url = "https://docs.google.com/document/export?id=1AbC_deF-1234567890abcdefghijk&format=pdf"
    assert extract_doc_id(url) == "1AbC_deF-1234567890abcdefghijk"


def test_accepts_bare_document_id():
    assert extract_doc_id("1AbC_deF-1234567890abcdefghij") == "1AbC_deF-1234567890abcdefghij"


def test_strips_quotes_and_whitespace():
    assert extract_doc_id("  '1AbC_deF-1234567890abcdefghij' ") == "1AbC_deF-1234567890abcdefghij"


def test_rejects_garbage():
    with pytest.raises(ValueError):
        extract_doc_id("not-a-google-docs-url")


def test_rejects_empty():
    with pytest.raises(ValueError):
        extract_doc_id("   ")
