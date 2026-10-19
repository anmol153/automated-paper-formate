import re

_DOC_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{25,}$")
_URL_RE = re.compile(r"/document/d/(?:e/)?([a-zA-Z0-9_-]{25,})")
_QUERY_KEYS = ("id", "documentid", "docid")


def extract_doc_id(source: str) -> str:
    source = (source or "").strip().strip("\"'")
    if not source:
        raise ValueError("Document URL or ID is empty.")
    match = _URL_RE.search(source)
    if match:
        return match.group(1)
    parsed_query = re.findall(r"[?&]([^&=]+)=([^&=]+)", source)
    lowered = {k.lower(): v for k, v in parsed_query}
    for key in _QUERY_KEYS:
        value = lowered.get(key)
        if value and _DOC_ID_RE.match(value):
            return value
    if _DOC_ID_RE.match(source):
        return source
    raise ValueError(
        f"'{source[:80]}' is not a valid Google Docs URL or document ID."
    )
