"""LaTeX parser: converts .tex source text into the shared NormalizedDocument model.

The parser understands the pieces of LaTeX that matter for formatting compliance:
document class / geometry options (page size, margins, orientation, columns), the
default font family packages, relative font-size commands, bold/italic styling,
alignment environments, \\linespread and \\parindent, plus the structural macros
(\\title, \\author, \\begin{abstract}, \\begin{keywords}, \\section ...). Everything
else is rendered as plain text so the block classifier (structure.py) can do its job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.document import (
    DocumentInfo,
    Margins,
    NormalizedDocument,
    PageSize,
    TextFormat,
)
from app.parsing.errors import LatexParseError
from app.parsing.normalizer import page_size_label
from app.parsing.page_estimate import estimate_pages
from app.parsing.structure import RawBlock, classify_blocks

_PAPER_DIMS: dict[str, tuple[float, float]] = {
    "A4": (595.28, 841.89),
    "A5": (419.53, 595.28),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "Tabloid": (792.0, 1224.0),
    "Executive": (522.0, 756.0),
}

_PAPER_OPTIONS = {
    "a4paper": "A4",
    "a5paper": "A5",
    "letterpaper": "Letter",
    "legalpaper": "Legal",
    "tabloidpaper": "Tabloid",
    "executivepaper": "Executive",
}

_LENGTH_UNITS = {
    "pt": 1.0,
    "in": 72.0,
    "mm": 72.0 / 25.4,
    "cm": 72.0 / 2.54,
    "bp": 7200.0 / 7227.0,
    "pc": 12.0,
    "dd": 1238.0 / 1157.0,
    "cc": 12.0 * 1238.0 / 1157.0,
}

_SIZE_COMMANDS: dict[str, tuple[float, float, float]] = {
    "tiny": (5.0, 6.0, 6.0),
    "scriptsize": (7.0, 8.0, 8.0),
    "footnotesize": (8.0, 9.0, 10.0),
    "small": (9.0, 10.0, 10.95),
    "normalsize": (10.0, 10.95, 12.0),
    "large": (12.0, 12.0, 14.4),
    "Large": (14.4, 14.4, 17.28),
    "LARGE": (17.28, 17.28, 20.74),
    "huge": (20.74, 20.74, 24.88),
    "Huge": (24.88, 24.88, 24.88),
}

_FAMILY_ALIASES = {
    "times": "Times New Roman",
    "mathptmx": "Times New Roman",
    "mathptm": "Times New Roman",
    "newtxtext": "Times New Roman",
    "txfonts": "Times New Roman",
    "ptm": "Times New Roman",
    "helvet": "Helvetica",
    "helveto": "Helvetica",
    "phv": "Helvetica",
    "newcent": "New Century Schoolbook",
    "pnc": "New Century Schoolbook",
    "palatino": "Palatino",
    "mathpazo": "Palatino",
    "ppl": "Palatino",
    "bookman": "Bookman",
    "pbk": "Bookman",
    "avant": "AvantGarde",
    "pag": "AvantGarde",
    "charter": "Charter",
    "courier": "Courier",
    "pcr": "Courier",
    "lmodern": "Computer Modern",
    "cm": "Computer Modern",
}

_INLINE_BOLD = {"textbf", "mathbf", "bm", "boldsymbol", "textbold", "unboldmath"}
_INLINE_ITALIC = {"textit", "mathit", "emph", "textsl"}
_INLINE_RENDER = {
    "textnormal",
    "textup",
    "textmd",
    "textrm",
    "textsf",
    "texttt",
    "textsc",
    "mbox",
    "makebox",
    "hbox",
    "underline",
    "uline",
    "textsuperscript",
    "textsubscript",
    "mathop",
}
_DECL_BOLD = {"bfseries", "bseries"}
_DECL_ITALIC = {"itshape", "slshape", "em"}
_DECL_UP = {"upshape", "normalfont"}
_DECL_MD = {"mdseries"}
_DECL_SIZES = set(_SIZE_COMMANDS)
_HEADING_COMMANDS = re.compile(
    r"^(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?$"
)
_ALIGN_ENVS = {
    "center": "center",
    "flushleft": "left",
    "flushright": "right",
    "justify": "justified",
}
_SKIP_WITH_ARGS = {
    "includegraphics",
    "rule",
    "resizebox",
    "rotatebox",
    "scalebox",
    "fcolorbox",
    "colorbox",
    "raisebox",
    "footnote",
    "thanks",
    "href",
}
_SKIP_TEXT_COMMANDS = {
    "label",
    "ref",
    "pageref",
    "eqref",
    "autoref",
    "cite",
    "citet",
    "citep",
    "nocite",
    "footnotemark",
    "tableofcontents",
    "listoffigures",
    "listoftables",
    "input",
    "include",
    "newpage",
    "clearpage",
    "cleardoublepage",
    "pagebreak",
    "nopagebreak",
    "noindent",
    "indent",
    "medskip",
    "smallskip",
    "bigskip",
    "vfill",
    "hfill",
    "hrule",
    "hspace",
    "vspace",
    "vskip",
    "hskip",
    "kern",
    "enlargethispage",
}

_SYMBOLS = {
    "%": "%",
    "&": "&",
    "$": "$",
    "#": "#",
    "_": "_",
    "{": "{",
    "}": "}",
    "~": "\u00a0",
    "textbackslash": "\\",
    "textgreater": ">",
    "textless": "<",
    "textcopyright": "\u00a9",
    "textregistered": "\u00ae",
    "texttrademark": "\u2122",
    "ldots": "\u2026",
    "dots": "\u2026",
    "textellipsis": "\u2026",
    "degree": "\u00b0",
    "textdegree": "\u00b0",
    "S": "§",
    "P": "¶",
}


def _length_to_pt(value: str) -> float | None:
    match = re.match(r"^\s*([+-]?[0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*$", value)
    if not match:
        return None
    number, unit = float(match.group(1)), match.group(2).lower()
    return round(number * _LENGTH_UNITS.get(unit, 1.0), 3)


def _size_for(base_size: float, command: str) -> float:
    if command not in _SIZE_COMMANDS:
        return base_size
    if base_size <= 10.5:
        index = 0
    elif base_size <= 11.5:
        index = 1
    else:
        index = 2
    return _SIZE_COMMANDS[command][index]


def _decode(source: str | bytes) -> str:
    if isinstance(source, bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return source.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise LatexParseError("Could not decode LaTeX source.")
    return source.lstrip("\ufeff")


def _strip_preambles(text: str) -> str:
    text = re.sub(r"(?s)\\begin\{(verbatim|lstlisting|comment|Verbatim)\}.*?\\end\{\1\}", " ", text)
    text = re.sub(r"\\iffalse(?:(?!\\fi).)*\\fi", " ", text, flags=re.S)
    return text


def _plain_text(source: str) -> str:
    text = re.sub(r"\\[a-zA-Z@*]+\*?", " ", source)
    text = re.sub(r"[{}~^$`&]", " ", text)
    text = re.sub(r"\\[^a-zA-Z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _dominant(weighted) -> object | None:
    totals: dict[object, float] = {}
    for value, weight in weighted:
        if value is None:
            continue
        totals[value] = totals.get(value, 0.0) + weight
    if not totals:
        return None
    return max(totals.items(), key=lambda item: item[1])[0]


def _majority(weighted) -> bool | None:
    true_weight = sum(weight for value, weight in weighted if value)
    false_weight = sum(weight for value, weight in weighted if not value)
    if true_weight == 0 and false_weight == 0:
        return None
    return true_weight >= false_weight


@dataclass
class DocumentSetup:
    base_size: float = 10.0
    page_size: tuple[float, float] = _PAPER_DIMS["A4"]
    orientation: str = "portrait"
    margins: Margins | None = None
    columns: int = 1
    column_spacing_pt: float | None = None
    font_family: str = "Computer Modern"
    line_spacing: float | None = None
    indent_first_line_pt: float | None = None
    title_content: str = ""
    author_content: str = ""


def _take_argument(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    return None, -1


def _extract_setup(text: str) -> DocumentSetup:
    setup = DocumentSetup()
    setup.base_size = 10.0

    doc_class = re.search(r"\\documentclass(\[[^\]]*\])?\{[^}]*\}", text)
    if doc_class:
        options = doc_class.group(1) or ""
        for option in options.strip("[]").split(","):
            option = option.strip().lower()
            if option in ("10pt", "11pt", "12pt"):
                setup.base_size = float(option[:-2])
            elif option == "twocolumn":
                setup.columns = 2
            elif option == "onecolumn":
                setup.columns = 1
            elif option == "landscape":
                setup.orientation = "landscape"
            elif option in _PAPER_OPTIONS:
                setup.page_size = _PAPER_DIMS[_PAPER_OPTIONS[option]]

    geometry: str | None = None
    match = re.search(r"\\geometry(\[[^\]]*\])?\s*\{([^}]*)\}", text)
    if match:
        geometry = f"{(match.group(1) or '').strip('[]')},{match.group(2)}"
    else:
        match = re.search(r"\\usepackage(\[[^\]]*\])?\{geometry\}", text)
        if match:
            geometry = (match.group(1) or "").strip("[]")
    if geometry is not None:
        _apply_geometry_options(setup, geometry)

    stretch = re.search(r"\\(linespread|setstretch)\s*\{?([0-9]*\.?[0-9]+)\}?", text)
    if stretch:
        setup.line_spacing = float(stretch.group(2))
    stretch = re.search(r"\\renewcommand\s*\{\\baselinestretch\}\s*\{([0-9]*\.?[0-9]+)\}", text)
    if stretch:
        setup.line_spacing = float(stretch.group(1))

    parindent = re.search(r"\\setlength\s*\{\\parindent\}\s*\{([^}]*)\}", text)
    if parindent:
        setup.indent_first_line_pt = _length_to_pt(parindent.group(1))
    columnsep = re.search(r"\\setlength\s*\{\\columnsep\}\s*\{([^}]*)\}", text)
    if columnsep:
        setup.column_spacing_pt = _length_to_pt(columnsep.group(1))

    for usepackage in re.finditer(r"\\usepackage(\[[^\]]*\])?\{([^}]*)\}", text):
        for package in usepackage.group(2).split(","):
            cleaned = package.strip()
            if cleaned in _FAMILY_ALIASES:
                setup.font_family = _FAMILY_ALIASES[cleaned]

    for command in ("title", "author"):
        match = re.search(f"\\\\{command}\\b", text)
        if match:
            opening = text.find("{", match.end())
            content, _ = _take_argument(text, opening)
            if content is not None:
                if command == "title":
                    setup.title_content = content
                else:
                    setup.author_content = content

    return setup


def _apply_geometry_options(setup: DocumentSetup, options: str) -> None:
    margin_overrides: dict[str, float] = {}
    for raw in options.split(","):
        option = raw.strip()
        if not option:
            continue
        lowered = option.lower()
        if lowered == "twocolumn":
            setup.columns = 2
        elif lowered == "onecolumn":
            setup.columns = 1
        elif lowered == "landscape":
            setup.orientation = "landscape"
        elif lowered == "portrait":
            setup.orientation = "portrait"
        elif lowered in _PAPER_OPTIONS:
            setup.page_size = _PAPER_DIMS[_PAPER_OPTIONS[lowered]]
        elif "=" in option:
            key, value = option.split("=", 1)
            key = key.strip().lower()
            parsed = _length_to_pt(value.strip())
            if parsed is None:
                continue
            if key == "margin":
                margin_overrides = {"top": parsed, "bottom": parsed, "left": parsed, "right": parsed}
            elif key == "columnsep":
                setup.column_spacing_pt = parsed
            elif key in ("top", "bottom", "left", "right"):
                margin_overrides[key] = parsed
    if margin_overrides:
        setup.margins = Margins(
            top_pt=margin_overrides.get("top", 72),
            bottom_pt=margin_overrides.get("bottom", 72),
            left_pt=margin_overrides.get("left", 72),
            right_pt=margin_overrides.get("right", 72),
        )


@dataclass
class Style:
    bold: bool = False
    italic: bool = False
    size: float | None = None
    family: str | None = None


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\":
            if i + 1 < len(text) and text[i + 1] in "\\{}% ":
                tokens.append(("sym", text[i : i + 2]))
                i += 2
                continue
            j = i + 1
            while j < len(text) and text[j].isalpha():
                j += 1
            if j < len(text) and text[j] == "*" and j > i + 1:
                j += 1
            tokens.append(("cmd", text[i + 1 : j]))
            i = j
        elif char == "{":
            tokens.append(("open", char))
            i += 1
        elif char == "}":
            tokens.append(("close", char))
            i += 1
        elif char == "%":
            newline = text.find("\n", i)
            i = newline + 1 if newline != -1 else len(text)
        else:
            j = i
            while j < len(text) and text[j] not in "\\{}%":
                j += 1
            tokens.append(("text", text[i:j]))
            i = j
    return tokens


class _LatexWalker:
    def __init__(self, setup: DocumentSetup):
        self.setup = setup
        self.blocks: list[RawBlock] = []
        self.segments: list[tuple[str, Style]] = []
        self.style_stack = [
            Style(bold=False, italic=False, size=setup.base_size, family=setup.font_family)
        ]
        self.alignment_stack: list[str | None] = [None]
        self.env_stack: list[str] = []
        self.keyword_mode = False
        self.keywords_first = True
        self.item_state: str | None = None
        self.item_counter = 0
        self.title_emitted = False
        self.prefix: list[RawBlock] = []

    @property
    def style(self) -> Style:
        return self.style_stack[-1]

    def _snapshot(self) -> Style:
        return Style(bold=self.style.bold, italic=self.style.italic, size=self.style.size, family=self.style.family)

    def _append_text(self, text: str) -> None:
        parts = re.split(r"\n[ \t]*\n", text)
        for index, part in enumerate(parts):
            if index > 0:
                self._flush()
            cleaned = " ".join(part.split())
            cleaned = cleaned.replace("---", "\u2014").replace("--", "\u2013").replace("~", " ")
            if cleaned:
                self.segments.append((cleaned, self._snapshot()))

    def _current_text(self) -> str:
        return re.sub(r"\s+", " ", "".join(text for text, _ in self.segments)).strip()

    def _aggregate_format(self, alignment: str | None = None) -> TextFormat:
        fonts = [(style.family, len(text)) for text, style in self.segments if text.strip()]
        sizes = [
            (style.size or self.setup.base_size, len(text))
            for text, style in self.segments
            if text.strip() and style.size is not None
        ]
        bolds = [(style.bold, len(text)) for text, style in self.segments if text.strip()]
        italics = [(style.italic, len(text)) for text, style in self.segments if text.strip()]

        size = _dominant(sizes)
        return TextFormat(
            font_family=_dominant(fonts) or self.setup.font_family,
            font_size_pt=round(float(size), 2) if size is not None else None,
            bold=_majority(bolds),
            italic=_majority(italics),
            alignment=alignment if alignment is not None else self.alignment_stack[-1],
            line_spacing=self.setup.line_spacing,
            indent_first_line_pt=self.setup.indent_first_line_pt,
        )

    def _flush(self) -> None:
        if self.keyword_mode:
            text = self._current_text()
            if not text:
                self.segments = []
                return
            format_ = self._aggregate_format()
            self.segments = []
            label = "Keywords" if self.keywords_first else ""
            self.keywords_first = False
            self.blocks.append(
                RawBlock(
                    text=f"Keywords\u2014{text}" if label else text,
                    format=format_,
                    named_style_type="NORMAL_TEXT",
                )
            )
            return
        text = self._current_text()
        if not text:
            self.segments = []
            return
        format_ = self._aggregate_format()
        self.segments = []
        self.blocks.append(
            RawBlock(text=text, format=format_, named_style_type="NORMAL_TEXT")
        )

    def _emit_heading(self, text: str) -> None:
        if not text:
            return
        self.blocks.append(
            RawBlock(
                text=text,
                format=TextFormat(
                    font_family=self.style.family or self.setup.font_family,
                    font_size_pt=self.style.size,
                    bold=True,
                    alignment=self.alignment_stack[-1],
                ),
                named_style_type="HEADING_1",
            )
        )

    def _emit_title_author(self) -> None:
        if self.title_emitted:
            return
        self.title_emitted = True
        if not self.setup.title_content:
            return
        title_tokens = _tokenize(self.setup.title_content)
        self.style_stack.append(
            Style(bold=True, italic=False, size=_size_for(self.setup.base_size, "LARGE"), family=self.setup.font_family)
        )
        self.alignment_stack.append("center")
        self.segments = []
        self._process(title_tokens)
        title_text = self._current_text()
        title_format = self._aggregate_format("center")
        self.alignment_stack.pop()
        self.style_stack.pop()
        self.segments = []

        if title_text:
            self.prefix.append(RawBlock(text=title_text, format=title_format, named_style_type=None))
        if self.setup.author_content:
            author_tokens = _tokenize(self.setup.author_content)
            self.style_stack.append(Style(bold=False, italic=False, size=self.setup.base_size, family=self.setup.font_family))
            self.alignment_stack.append("center")
            self.segments = []
            self._process(author_tokens)
            author_text = self._current_text()
            author_format = self._aggregate_format("center")
            self.alignment_stack.pop()
            self.style_stack.pop()
            self.segments = []
            if author_text:
                self.prefix.append(RawBlock(text=author_text, format=author_format, named_style_type=None))

    def _read_group(self, tokens: list[tuple[str, str]], i: int) -> tuple[list[tuple[str, str]] | None, int]:
        if i >= len(tokens) or tokens[i][0] != "open":
            return None, i
        depth = 0
        i += 1
        start = i
        while i < len(tokens):
            kind, _ = tokens[i]
            if kind == "open":
                depth += 1
            elif kind == "close":
                if depth == 0:
                    return tokens[start:i], i + 1
                depth -= 1
            i += 1
        return tokens[start:i], i + 1

    def _read_optional(self, tokens: list[tuple[str, str]], i: int) -> int:
        if i < len(tokens) and tokens[i][0] == "text" and tokens[i][1].lstrip().startswith("["):
            while i < len(tokens):
                kind, value = tokens[i]
                if kind == "text" and "]" in value:
                    return i + 1
                i += 1
            return i
        return i

    def _process(self, tokens: list[tuple[str, str]]) -> None:
        i = 0
        while i < len(tokens):
            kind, value = tokens[i]
            if kind == "cmd":
                i = self._command(tokens, i)
                continue
            if kind == "text":
                self._append_text(value)
            elif kind == "open":
                self.style_stack.append(self._snapshot())
            elif kind == "close":
                if len(self.style_stack) > 1:
                    self.style_stack.pop()
            elif kind == "sym":
                self._control_symbol(value)
            i += 1

    def _control_symbol(self, value: str) -> None:
        if value == "\\\\":
            self.segments.append((" ", self._snapshot()))
        elif value == "\\ " or value == "\\~":
            self.segments.append((" ", self._snapshot()))
        elif value == "\\{":
            self.segments.append(("{", self._snapshot()))
        elif value == "\\}":
            self.segments.append(("}", self._snapshot()))
        elif value == "\\%":
            self.segments.append(("%", self._snapshot()))
        elif value == "\\&":
            self.segments.append(("&", self._snapshot()))
        elif value == "\\_":
            self.segments.append(("_", self._snapshot()))
        elif value == "\\#":
            self.segments.append(("#", self._snapshot()))
        elif value == "\\$":
            self.segments.append(("$", self._snapshot()))

    def _command(self, tokens: list[tuple[str, str]], i: int) -> int:
        name = tokens[i][1]
        i += 1

        if name == "":
            self.segments.append((" ", self._snapshot()))
            return i
        if name == "begin":
            group, i = self._read_group(tokens, i)
            env = "".join(value for kind, value in group) if group else ""
            env = env.strip()
            if env == "multicols":
                arg, i = self._read_group(tokens, i)
                count = "".join(value for kind, value in arg).strip() if arg else ""
                try:
                    self.setup.columns = int(count)
                except ValueError:
                    pass
            elif env == "twocolumn":
                self.setup.columns = 2
            self._begin_env(env)
            return i
        if name == "end":
            group, i = self._read_group(tokens, i)
            env = "".join(value for kind, value in group) if group else ""
            self._end_env(env.strip())
            return i
        if name == "maketitle":
            self._emit_title_author()
            return i
        if name == "item":
            self._begin_item()
            return self._read_optional(tokens, i)
        if _HEADING_COMMANDS.match(name):
            self._flush()
            group, i = self._read_group(tokens, i)
            if group is None:
                i = self._read_optional(tokens, i)
                group, i = self._read_group(tokens, i)
            self.segments = []
            if group:
                self._process(group)
            self._emit_heading(self._current_text())
            self.segments = []
            return i
        if name in _INLINE_BOLD:
            group, i = self._read_group(tokens, i)
            if group:
                self.style_stack.append(self._snapshot())
                self.style_stack[-1].bold = True
                self._process(group)
                self.style_stack.pop()
            return i
        if name in _INLINE_ITALIC:
            group, i = self._read_group(tokens, i)
            if group:
                self.style_stack.append(self._snapshot())
                self.style_stack[-1].italic = True
                self._process(group)
                self.style_stack.pop()
            return i
        if name in _INLINE_RENDER:
            group, i = self._read_group(tokens, i)
            if group:
                self._process(group)
            return i
        if name == "textcolor":
            group, i = self._read_group(tokens, i)
            if group:
                group, i = self._read_group(tokens, i)
                if group:
                    self._process(group)
            return i
        if name in _DECL_BOLD:
            self.style.bold = True
            return i
        if name in _DECL_ITALIC:
            self.style.italic = True
            return i
        if name in _DECL_UP:
            self.style.italic = False
            return i
        if name in _DECL_MD:
            self.style.bold = False
            return i
        if name == "rmfamily" or name == "normalfont":
            self.style.family = self.setup.font_family
            return i
        if name in _DECL_SIZES:
            self.style.size = _size_for(self.setup.base_size, name)
            return i
        if name == "centering":
            self.alignment_stack[-1] = "center"
            return i
        if name == "raggedright":
            self.alignment_stack[-1] = "left"
            return i
        if name == "raggedleft":
            self.alignment_stack[-1] = "right"
            return i
        if name == "justify" or name == "justifying":
            self.alignment_stack[-1] = "justified"
            return i
        if name == "par":
            self._flush()
            return i
        if name == "and":
            self.segments.append((", ", self._snapshot()))
            return i
        if name == "quad" or name == "qquad" or name == "enspace":
            self.segments.append((" ", self._snapshot()))
            return i
        if name == "frac":
            num, i = self._read_group(tokens, i)
            denom, i = self._read_group(tokens, i)
            num_text = _plain_text("".join(v for _, v in (num or []))) if num else ""
            denom_text = _plain_text("".join(v for _, v in (denom or []))) if denom else ""
            self.segments.append((f"{num_text} / {denom_text} ".strip(), self._snapshot()))
            return i
        if name == "sqrt":
            group, i = self._read_group(tokens, i)
            inner = _plain_text("".join(v for _, v in (group or []))) if group else ""
            self.segments.append((f"sqrt({inner})", self._snapshot()))
            return i
        if name in _SKIP_WITH_ARGS:
            i = self._read_optional(tokens, i)
            group, i = self._read_group(tokens, i)
            return i
        if name in _SKIP_TEXT_COMMANDS:
            i = self._read_optional(tokens, i)
            group, i = self._read_group(tokens, i)
            if name == "href" and group:
                self._process(group)
            return i
        if name in _SYMBOLS:
            self.segments.append((_SYMBOLS[name], self._snapshot()))
            return i
        if name.startswith("text") or name.startswith("math"):
            return i
        return i

    def _begin_env(self, env: str) -> int:
        self.env_stack.append(env)
        if env == "abstract":
            self._flush()
            self.blocks.append(
                RawBlock(
                    text="Abstract",
                    format=TextFormat(
                        font_family=self.style.family or self.setup.font_family,
                        font_size_pt=self.setup.base_size,
                        bold=True,
                        alignment=self.alignment_stack[-1],
                    ),
                    named_style_type="HEADING_1",
                )
            )
        elif env == "keywords":
            self._flush()
            self.keyword_mode = True
            self.keywords_first = True
        elif env in _ALIGN_ENVS:
            self.alignment_stack.append(_ALIGN_ENVS[env])
        elif env in ("itemize", "enumerate"):
            self.item_state = env
            self.item_counter = 0
        elif env == "description":
            self.item_state = "description"
        return 0

    def _end_env(self, env: str) -> None:
        if self.env_stack and self.env_stack[-1] == env:
            self.env_stack.pop()
        if env == "keywords":
            self._flush()
            self.keyword_mode = False
        elif env in _ALIGN_ENVS:
            if len(self.alignment_stack) > 1:
                self.alignment_stack.pop()
        elif env in ("itemize", "enumerate", "description"):
            self._flush()
            self.item_state = None

    def _begin_item(self) -> None:
        self._flush()
        if self.item_state == "enumerate":
            self.item_counter += 1
            self.segments.append((f"{self.item_counter}. ", self._snapshot()))
        elif self.item_state == "itemize":
            self.segments.append(("\u2022 ", self._snapshot()))
        elif self.item_state == "description":
            self.segments.append(("\u2022 ", self._snapshot()))


def parse_latex(source: str | bytes) -> NormalizedDocument:
    text = _decode(source)
    text = _strip_preambles(text)
    if not text.strip():
        raise LatexParseError("LaTeX source is empty.")

    setup = _extract_setup(text)

    body = text
    begin = text.find(r"\begin{document}")
    if begin != -1:
        body = text[begin + len(r"\begin{document}"):].lstrip()
    end = body.find(r"\end{document}")
    if end != -1:
        body = body[:end]

    walker = _LatexWalker(setup)
    walker._process(_tokenize(body))
    walker._flush()
    if not walker.title_emitted and setup.title_content:
        walker._emit_title_author()
    walker.blocks = walker.prefix + walker.blocks

    sections = classify_blocks(walker.blocks)
    if not walker.blocks:
        raise LatexParseError("No readable LaTeX content found.")

    width, height = setup.page_size
    margins = setup.margins or Margins(top_pt=72, bottom_pt=72, left_pt=72, right_pt=72)
    info = DocumentInfo(
        page_size=PageSize(
            width_pt=round(width, 2),
            height_pt=round(height, 2),
            label=page_size_label(width, height),
        ),
        margins=margins,
        orientation=setup.orientation,
        columns=setup.columns,
        column_spacing_pt=setup.column_spacing_pt,
        title=_plain_text(setup.title_content),
    )
    normalized = NormalizedDocument(document=info, sections=sections)
    estimated = estimate_pages(
        normalized, font_size_pt=setup.base_size, line_spacing=setup.line_spacing
    )
    info.page_count = estimated
    info.page_count_exact = False
    return normalized


__all__ = ["parse_latex", "LatexParseError"]