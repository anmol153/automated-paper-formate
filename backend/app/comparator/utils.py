import re

from app.models.report import CheckResult

_FONT_WHITESPACE_RE = re.compile(r"\s+")


def normalize_font_name(name: str | None) -> str:
    return _FONT_WHITESPACE_RE.sub(" ", (name or "")).strip().casefold()


def compare_font(a: str | None, b: str | None) -> bool | None:
    if a is None or b is None:
        return None
    return normalize_font_name(a) == normalize_font_name(b)


def compare_size(a: float | None, b: float | None, tolerance: float = 0.51) -> bool | None:
    if a is None or b is None:
        return None
    return abs(float(a) - float(b)) <= tolerance


def compare_close(a: float | None, b: float | None, tolerance: float = 2.0) -> bool | None:
    if a is None or b is None:
        return None
    return abs(float(a) - float(b)) <= tolerance


def compare_equal(a, b) -> bool | None:
    if a is None or b is None:
        return None
    return a == b


def fmt_pt(value: float | None) -> str | None:
    return f"{value:g} pt" if value is not None else None


def build_check(
    name: str,
    category: str,
    expected,
    actual,
    matched: bool | None,
) -> CheckResult:
    if matched is None:
        status = "missing"
    else:
        status = "passed" if matched else "failed"
    return CheckResult(
        name=name,
        category=category,
        status=status,
        expected=expected,
        actual=actual,
    )
