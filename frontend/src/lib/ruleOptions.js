export const CANONICAL_SECTIONS = [
  "Abstract",
  "Keywords",
  "Introduction",
  "Related Work",
  "Methodology",
  "Results",
  "Conclusion",
  "References",
];

export const EXTENSION_CHOICES = ["pdf", "tex", "docx", "latex", "doc"];

export const METADATA_FIELDS = [
  "author",
  "creator",
  "producer",
  "title",
  "subject",
  "keywords",
];

export const CATEGORY_LABELS = {
  file: "File",
  page: "Page Limit",
  layout: "Page Setup",
  structure: "Structure & Sections",
  typography: "Typography",
  paragraph: "Paragraph Formatting",
  anonymisation: "Anonymisation",
};

export const CATEGORY_ORDER = [
  "file",
  "page",
  "layout",
  "structure",
  "typography",
  "paragraph",
  "anonymisation",
];

export const VERDICT_META = {
  accepted: {
    label: "Accepted",
    chip: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300",
    dot: "bg-emerald-500",
  },
  needs_review: {
    label: "Needs review",
    chip: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300",
    dot: "bg-amber-500",
  },
  rejected: {
    label: "Rejected",
    chip: "border-red-200 bg-red-50 text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300",
    dot: "bg-red-500",
  },
};

export const CHECK_STATUS_META = {
  passed: { icon: "✓", row: "", text: "text-emerald-500 dark:text-emerald-400" },
  failed: { icon: "✗", row: "bg-red-50/30 dark:bg-red-500/5", text: "text-red-500 dark:text-red-400" },
  missing: { icon: "⚠", row: "bg-amber-50/40 dark:bg-amber-500/5", text: "text-amber-500 dark:text-amber-400" },
  not_applicable: { icon: "–", row: "bg-slate-50/60 dark:bg-slate-800/40", text: "text-slate-400" },
};

/** Default rule set used before a template is imported, mirroring the backend model. */
export function emptyRuleSet() {
  return {
    name: "Untitled template",
    description: "",
    source_template_filename: null,
    publisher: {
      publisher_name: "",
      conference_name: "",
      contact_email: "",
      support_url: "",
      deadline: null,
      notes_for_authors: "",
    },
    file_type: {
      accepted_extensions: ["pdf"],
      max_file_size_mb: 20,
      require_exactly_one_paper_per_submission: true,
      reject_if_extension_not_accepted: true,
      reject_if_extension_missing: true,
      allow_source_upload: true,
      require_source_when_pdf_given: false,
    },
    pages: {
      max_pages: null,
      min_pages: null,
      count_references_toward_limit: true,
      page_size_label: null,
      orientation: null,
      columns: null,
      margins: null,
      margin_tolerance_pt: 2,
      estimate_tolerance_pages: 1,
    },
    sections: {
      required_sections: [],
      forbid_sections: [],
      abstract_required: true,
      abstract_max_words: null,
      keywords_required: false,
      min_reference_entries: null,
      allow_section_numbering: true,
      require_canonical_heading_names: false,
    },
    anonymisation: {
      required: false,
      allow_author_block: false,
      allow_anonymous_placeholder: true,
      detect_emails: true,
      detect_affiliations: true,
      detect_acknowledgements: true,
      detect_self_citation: false,
      detect_file_metadata: true,
      detect_pdf_metadata: true,
      detect_funding_statements: true,
      detect_orcid: true,
      extra_forbidden_terms: [],
      forbidden_metadata_fields: ["author", "creator", "producer", "title", "subject", "keywords"],
    },
    typography: {
      title: null,
      authors: null,
      abstract: null,
      headings: null,
      body: null,
      tolerance: {
        font_family: true,
        font_size_pt: 0.51,
        line_spacing: 0.01,
        indent_pt: 2,
        space_pt: 2,
        min_font_size_pt: null,
        max_font_size_pt: null,
        allowed_font_families: [],
      },
    },
    paragraph: {
      line_spacing: null,
      indent_first_line_pt: null,
      space_above_pt: null,
      space_below_pt: null,
      require_justified_body: false,
      require_uniform_alignment: false,
      max_alignment_mismatches: 0,
      indent_tolerance_pt: 2,
      space_tolerance_pt: 2,
      line_spacing_tolerance: 0.01,
    },
    decision: {
      blocking_severity: "blocking",
      reject_if_any_blocking: true,
      reject_if_any_warning: false,
      min_score_to_accept: null,
    },
  };
}
