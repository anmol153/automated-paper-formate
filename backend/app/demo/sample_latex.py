"""Sample LaTeX sources used by demo mode and tests, mirroring the PDF/Google-doc demos."""

from __future__ import annotations


def latex_template() -> str:
    return r"""\documentclass[a4paper,twocolumn,11pt]{article}

\usepackage[left=54pt,right=54pt,top=64pt,bottom=64pt,columnsep=24pt]{geometry}
\usepackage{times}
\setlength{\parindent}{14pt}

\title{Sample Journal Paper Template}
\author{Jane Doe, John Smith\\ Example University, Example City}
\date{}

\begin{document}
\maketitle

\begin{abstract}
The proposed approach evaluates formatting compliance by parsing the document model directly and comparing extracted rules against observed typography across all sections. The proposed approach evaluates formatting compliance by parsing the document model directly and comparing extracted rules against observed typography across all sections.
\end{abstract}

\begin{keywords}
format checking, templates, compliance
\end{keywords}

\section{Introduction}
The proposed approach evaluates formatting compliance by parsing the document model directly and comparing extracted rules against observed typography across all sections. The proposed approach evaluates formatting compliance by parsing the document model directly and comparing extracted rules against observed typography across all sections.

\section{Methodology}
The proposed approach evaluates formatting compliance by parsing the document model directly and comparing extracted rules against observed typography across all sections.

\section{Results}
The proposed approach evaluates formatting compliance by parsing the document model directly and comparing extracted rules against observed typography across all sections.

\section{Conclusion}
The proposed approach evaluates formatting compliance by parsing the document model directly and comparing extracted rules against observed typography across all sections.

\section{References}
[1] A. Author, B. Author, Some Paper, Venue 2024.

[2] C. Author, Another Paper, Venue 2025.

\end{document}
"""


def latex_paper() -> str:
    return r"""\documentclass[letterpaper,11pt]{article}

\usepackage[left=72pt,right=72pt,top=72pt,bottom=72pt]{geometry}
\usepackage{helvet}

\title{Deep Learning for Format Compliance Checking}
\author{Alice Lee, Bob Chen\\ State University, Springfield}
\date{}

\begin{document}
\maketitle

\begin{abstract}
We study whether research papers comply with venue formatting requirements automatically using deterministic parsing of cloud document APIs. Our prototype compares normalized documents against extracted rules and reports violations.
\end{abstract}

\section{1. Introduction}
Formatting requirements are tedious to verify manually. We introduce a pipeline that parses documents and compares them against journal templates.

Prior systems rely on heuristics over PDFs. In contrast, we operate on the structured document model directly, which preserves typography faithfully.

\section{Results}
On a corpus of fifty papers the system reaches high agreement with manual review and produces actionable per-requirement diagnostics for authors.

\section{Conclusion}
Automated compliance checking saves reviewers time and helps authors fix issues early before submission deadlines arrive.

\section{References}
[1] X. Yang, Format Matters, Journal of Documents, 2024.

\end{document}
"""


def latex_documents() -> tuple[str, str]:
    return latex_template(), latex_paper()