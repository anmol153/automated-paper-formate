class ParseError(ValueError):
    """Raised when an uploaded document cannot be parsed regardless of format."""


class PdfParseError(ParseError):
    pass


class LatexParseError(ParseError):
    pass


class DocxParseError(ParseError):
    pass


__all__ = ["ParseError", "PdfParseError", "LatexParseError", "DocxParseError"]