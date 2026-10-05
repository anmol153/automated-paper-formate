import { useState } from "react";
import { CANONICAL_SECTIONS, EXTENSION_CHOICES, METADATA_FIELDS } from "../lib/ruleOptions.js";

export default function RuleEditor({ rules, onChange, disabled }) {
  const set = (path, value) => {
    const next = structuredClone(rules);
    let node = next;
    const keys = path.split(".");
    for (const key of keys.slice(0, -1)) node = node[key] ??= {};
    node[keys.at(-1)] = value;
    onChange(next);
  };

  return (
    <div className="space-y-5">
      <Panel title="Template" subtitle="Basic template identification">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Template name" hint="Shown to authors when they submit.">
            <input
              className="input-base"
              value={rules.name ?? ""}
              disabled={disabled}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g., IEEE Conference Template"
            />
          </Field>
          <Field label="Description" hint="Brief description of this template.">
            <input
              className="input-base"
              value={rules.description ?? ""}
              disabled={disabled}
              onChange={(e) => set("description", e.target.value)}
              placeholder="Optional description"
            />
          </Field>
        </div>
        <Field label="Source file" hint="Where these rules were imported from.">
          <input
            className="input-base"
            value={rules.source_template_filename ?? ""}
            disabled
            placeholder="not imported from a file"
          />
        </Field>
      </Panel>

      <Panel title="Publisher" subtitle="Conference/journal metadata">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Publisher">
            <input
              className="input-base"
              value={rules.publisher?.publisher_name ?? ""}
              disabled={disabled}
              onChange={(e) => set("publisher.publisher_name", e.target.value)}
              placeholder="e.g., IEEE"
            />
          </Field>
          <Field label="Conference/Journal">
            <input
              className="input-base"
              value={rules.publisher?.conference_name ?? ""}
              disabled={disabled}
              onChange={(e) => set("publisher.conference_name", e.target.value)}
              placeholder="e.g., ICML 2026"
            />
          </Field>
          <Field label="Contact email">
            <input
              className="input-base"
              type="email"
              value={rules.publisher?.contact_email ?? ""}
              disabled={disabled}
              onChange={(e) => set("publisher.contact_email", e.target.value)}
              placeholder="contact@conference.org"
            />
          </Field>
          <Field label="Support URL">
            <input
              className="input-base"
              value={rules.publisher?.support_url ?? ""}
              disabled={disabled}
              onChange={(e) => set("publisher.support_url", e.target.value)}
              placeholder="https://conference.org/support"
            />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Submission deadline" hint="ISO format (YYYY-MM-DD)">
            <input
              className="input-base"
              value={rules.publisher?.deadline ?? ""}
              placeholder="2026-05-01"
              disabled={disabled}
              onChange={(e) => set("publisher.deadline", e.target.value || null)}
            />
          </Field>
        </div>
        <Field label="Notes for authors" hint="Displayed to authors on the submission page.">
          <textarea
            className="input-base min-h-[80px] resize-y font-sans"
            value={rules.publisher?.notes_for_authors ?? ""}
            disabled={disabled}
            onChange={(e) => set("publisher.notes_for_authors", e.target.value)}
            placeholder="Additional instructions for authors..."
          />
        </Field>
      </Panel>

      <Panel title="Accepted files" subtitle="File type restrictions and size limits">
        <Field label="Accepted extensions" hint="A file outside this list is rejected before it is parsed.">
          <div className="flex flex-wrap gap-2">
            {EXTENSION_CHOICES.map((ext) => {
              const on = (rules.file_type?.accepted_extensions ?? []).includes(ext);
              return (
                <button
                  key={ext}
                  type="button"
                  disabled={disabled}
                  onClick={() =>
                    set(
                      "file_type.accepted_extensions",
                      on
                        ? (rules.file_type.accepted_extensions ?? []).filter((e) => e !== ext)
                        : [...(rules.file_type.accepted_extensions ?? []), ext],
                    )
                  }
                  className={`tag tag-removable transition-all duration-150 ${
                    on ? "tag-primary" : "tag-neutral"
                  }`}
                >
                  .{ext}
                </button>
              );
            })}
          </div>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Max file size (MB)" hint="Leave blank for no limit.">
            <NumberInput
              value={rules.file_type?.max_file_size_mb}
              disabled={disabled}
              step="0.5"
              onChange={(v) => set("file_type.max_file_size_mb", v)}
            />
          </Field>
          <Toggle
            label="Allow LaTeX/Word source uploads"
            hint="Otherwise a .tex or .docx is rejected."
            checked={rules.file_type?.allow_source_upload ?? true}
            disabled={disabled}
            onChange={(v) => set("file_type.allow_source_upload", v)}
          />
          <Toggle
            label="Reject unaccepted extensions"
            checked={rules.file_type?.reject_if_extension_not_accepted ?? true}
            disabled={disabled}
            onChange={(v) => set("file_type.reject_if_extension_not_accepted", v)}
          />
          <Toggle
            label="Require source when a PDF is given"
            hint="Asks for both the PDF and its source."
            checked={rules.file_type?.require_source_when_pdf_given ?? false}
            disabled={disabled}
            onChange={(v) => set("file_type.require_source_when_pdf_given", v)}
          />
        </div>
      </Panel>

      <Panel title="Page setup" subtitle="Page dimensions, margins, and limits">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Max pages" hint="Blank means no limit.">
            <NumberInput
              value={rules.pages?.max_pages}
              disabled={disabled}
              onChange={(v) => set("pages.max_pages", v)}
            />
          </Field>
          <Field label="Min pages">
            <NumberInput
              value={rules.pages?.min_pages}
              disabled={disabled}
              onChange={(v) => set("pages.min_pages", v)}
            />
          </Field>
          <Field label="Page size">
            <select
              className="input-base"
              value={rules.pages?.page_size_label ?? ""}
              disabled={disabled}
              onChange={(e) => set("pages.page_size_label", e.target.value || null)}
            >
              <option value="">don't care</option>
              <option value="A4">A4</option>
              <option value="Letter">Letter</option>
              <option value="A5">A5</option>
            </select>
          </Field>
          <Field label="Orientation">
            <select
              className="input-base"
              value={rules.pages?.orientation ?? ""}
              disabled={disabled}
              onChange={(e) => set("pages.orientation", e.target.value || null)}
            >
              <option value="">don't care</option>
              <option value="portrait">portrait</option>
              <option value="landscape">landscape</option>
            </select>
          </Field>
          <Field label="Columns">
            <NumberInput
              value={rules.pages?.columns}
              disabled={disabled}
              onChange={(v) => set("pages.columns", v)}
            />
          </Field>
          <Field label="Page-count tolerance" hint="Pages allowed either way when the count is estimated, not measured.">
            <NumberInput
              value={rules.pages?.estimate_tolerance_pages}
              disabled={disabled}
              onChange={(v) => set("pages.estimate_tolerance_pages", v)}
            />
          </Field>
        </div>

        <Subhead>Margins (pt)</Subhead>
        <div className="grid gap-4 sm:grid-cols-4">
          {(["top", "bottom", "left", "right"]).map((side) => (
            <Field key={side} label={side.charAt(0).toUpperCase() + side.slice(1)}>
              <NumberInput
                value={rules.pages?.margins?.[`${side}_pt`]}
                disabled={disabled}
                step="0.5"
                onChange={(v) =>
                  set("pages.margins", { ...(rules.pages?.margins ?? {}), [`${side}_pt`]: v })
                }
              />
            </Field>
          ))}
        </div>
        <div className="flex items-center justify-between">
          <p className="text-xs text-surface-400">Leave all four blank to skip margin checks.</p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => set("pages.margins", null)}
            className="text-xs font-medium text-surface-400 transition-colors hover:text-danger-600 dark:hover:text-danger-400"
          >
            Clear margins
          </button>
        </div>
        <Field label="Margin tolerance (pt)">
          <NumberInput
            value={rules.pages?.margin_tolerance_pt}
            disabled={disabled}
            step="0.5"
            onChange={(v) => set("pages.margin_tolerance_pt", v)}
          />
        </Field>
        <Toggle
          label="Count references toward the page limit"
          checked={rules.pages?.count_references_toward_limit ?? true}
          disabled={disabled}
          onChange={(v) => set("pages.count_references_toward_limit", v)}
        />
      </Panel>

      <Panel title="Structure" subtitle="Required sections, abstract, keywords, and references">
        <Field label="Required sections" hint="A required section that cannot be found is reported as missing.">
          <TagList
            values={rules.sections?.required_sections ?? []}
            options={CANONICAL_SECTIONS}
            allowCustom
            disabled={disabled}
            onChange={(v) => set("sections.required_sections", v)}
          />
        </Field>
        <Field label="Forbidden sections">
          <TagList
            values={rules.sections?.forbid_sections ?? []}
            options={CANONICAL_SECTIONS}
            allowCustom
            disabled={disabled}
            onChange={(v) => set("sections.forbid_sections", v)}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Toggle
            label="Abstract required"
            checked={rules.sections?.abstract_required ?? true}
            disabled={disabled}
            onChange={(v) => set("sections.abstract_required", v)}
          />
          <Field label="Abstract max words">
            <NumberInput
              value={rules.sections?.abstract_max_words}
              disabled={disabled}
              onChange={(v) => set("sections.abstract_max_words", v)}
            />
          </Field>
          <Toggle
            label="Keywords required"
            checked={rules.sections?.keywords_required ?? false}
            disabled={disabled}
            onChange={(v) => set("sections.keywords_required", v)}
          />
          <Field label="Minimum reference entries">
            <NumberInput
              value={rules.sections?.min_reference_entries}
              disabled={disabled}
              onChange={(v) => set("sections.min_reference_entries", v)}
            />
          </Field>
          <Toggle
            label="Allow numbered sections"
            checked={rules.sections?.allow_section_numbering ?? true}
            disabled={disabled}
            onChange={(v) => set("sections.allow_section_numbering", v)}
          />
          <Toggle
            label="Require canonical heading names"
            hint="&lsquo;Related Work&rsquo; must not be &lsquo;Background&rsquo;."
            checked={rules.sections?.require_canonical_heading_names ?? false}
            disabled={disabled}
            onChange={(v) => set("sections.require_canonical_heading_names", v)}
          />
        </div>
      </Panel>

      <Panel title="Anonymisation" subtitle="Double-blind submission checks">
        <Toggle
          label="Anonymised submission required"
          checked={rules.anonymisation?.required ?? false}
          disabled={disabled}
          onChange={(v) => set("anonymisation.required", v)}
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["allow_author_block", "Allow an author block"],
            ["allow_anonymous_placeholder", "Accept 'Anonymous Authors' placeholder"],
            ["detect_emails", "Detect email addresses"],
            ["detect_affiliations", "Detect affiliations"],
            ["detect_acknowledgements", "Detect acknowledgements"],
            ["detect_funding_statements", "Detect funding statements"],
            ["detect_orcid", "Detect ORCID identifiers"],
            ["detect_self_citation", "Detect self-citation"],
            ["detect_file_metadata", "Detect document metadata"],
            ["detect_pdf_metadata", "Detect PDF properties"],
          ].map(([key, label]) => (
            <Toggle
              key={key}
              label={label}
              checked={rules.anonymisation?.[key] ?? false}
              disabled={disabled}
              onChange={(v) => set(`anonymisation.${key}`, v)}
            />
          ))}
        </div>
        <Field label="PDF properties treated as leaks" hint="&lsquo;title&rsquo; and &lsquo;producer&rsquo; rarely identify anyone; drop them to stop false alarms.">
          <div className="flex flex-wrap gap-2">
            {METADATA_FIELDS.map((field) => {
              const on = (rules.anonymisation?.forbidden_metadata_fields ?? []).includes(field);
              return (
                <button
                  key={field}
                  type="button"
                  disabled={disabled}
                  onClick={() =>
                    set(
                      "anonymisation.forbidden_metadata_fields",
                      on
                        ? (rules.anonymisation?.forbidden_metadata_fields ?? []).filter(
                            (f) => f !== field,
                          )
                        : [...(rules.anonymisation?.forbidden_metadata_fields ?? []), field],
                    )
                  }
                  className={`tag tag-removable transition-all duration-150 ${
                    on ? "tag-warning" : "tag-neutral"
                  }`}
                >
                  {field}
                </button>
              );
            })}
          </div>
        </Field>
        <Field label="Extra forbidden terms" hint="One per entry; each is searched for verbatim.">
          <TagList
            values={rules.anonymisation?.extra_forbidden_terms ?? []}
            options={[]}
            allowCustom
            disabled={disabled}
            onChange={(v) => set("anonymisation.extra_forbidden_terms", v)}
          />
        </Field>
      </Panel>

      <Panel title="Typography" subtitle="Font family, size, and weight for each element">
        <p className="mb-4 text-xs text-surface-400">
          A blank field means that attribute is not checked for that element.
        </p>
        {[
          ["title", "Title"],
          ["authors", "Author block"],
          ["abstract", "Abstract"],
          ["headings", "Headings"],
          ["body", "Body text"],
        ].map(([key, label]) => (
          <FormatRow
            key={key}
            label={label}
            format={rules.typography?.[key]}
            disabled={disabled}
            onChange={(value) => set(`typography.${key}`, value)}
          />
        ))}
        <Subhead>Tolerance</Subhead>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Font size tolerance (pt)">
            <NumberInput
              value={rules.typography?.tolerance?.font_size_pt}
              disabled={disabled}
              step="0.05"
              onChange={(v) =>
                set("typography.tolerance", {
                  ...(rules.typography?.tolerance ?? {}),
                  font_size_pt: v,
                })
              }
            />
          </Field>
          <Field label="Smallest permitted body size (pt)">
            <NumberInput
              value={rules.typography?.tolerance?.min_font_size_pt}
              disabled={disabled}
              step="0.5"
              onChange={(v) =>
                set("typography.tolerance", {
                  ...(rules.typography?.tolerance ?? {}),
                  min_font_size_pt: v,
                })
              }
            />
          </Field>
          <Field label="Largest permitted body size (pt)">
            <NumberInput
              value={rules.typography?.tolerance?.max_font_size_pt}
              disabled={disabled}
              step="0.5"
              onChange={(v) =>
                set("typography.tolerance", {
                  ...(rules.typography?.tolerance ?? {}),
                  max_font_size_pt: v,
                })
              }
            />
          </Field>
          <Field label="Allowed font families" hint="Overrides the single font above when set.">
            <TagList
              values={rules.typography?.tolerance?.allowed_font_families ?? []}
              options={[]}
              allowCustom
              disabled={disabled}
              onChange={(v) =>
                set("typography.tolerance", {
                  ...(rules.typography?.tolerance ?? {}),
                  allowed_font_families: v,
                })
              }
            />
          </Field>
        </div>
      </Panel>

      <Panel title="Paragraph formatting" subtitle="Line spacing, indentation, and alignment">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Line spacing" hint="1.0 is single spacing.">
            <NumberInput
              value={rules.paragraph?.line_spacing}
              disabled={disabled}
              step="0.05"
              onChange={(v) => set("paragraph.line_spacing", v)}
            />
          </Field>
          <Field label="Line spacing tolerance">
            <NumberInput
              value={rules.paragraph?.line_spacing_tolerance}
              disabled={disabled}
              step="0.01"
              onChange={(v) => set("paragraph.line_spacing_tolerance", v)}
            />
          </Field>
          <Field label="First-line indent (pt)">
            <NumberInput
              value={rules.paragraph?.indent_first_line_pt}
              disabled={disabled}
              step="1"
              onChange={(v) => set("paragraph.indent_first_line_pt", v)}
            />
          </Field>
          <Field label="Space above (pt)">
            <NumberInput
              value={rules.paragraph?.space_above_pt}
              disabled={disabled}
              step="1"
              onChange={(v) => set("paragraph.space_above_pt", v)}
            />
          </Field>
          <Field label="Space below (pt)">
            <NumberInput
              value={rules.paragraph?.space_below_pt}
              disabled={disabled}
              step="1"
              onChange={(v) => set("paragraph.space_below_pt", v)}
            />
          </Field>
          <Field label="Space tolerance (pt)">
            <NumberInput
              value={rules.paragraph?.space_tolerance_pt}
              disabled={disabled}
              step="0.5"
              onChange={(v) => set("paragraph.space_tolerance_pt", v)}
            />
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Toggle
            label="Body text must be justified"
            checked={rules.paragraph?.require_justified_body ?? false}
            disabled={disabled}
            onChange={(v) => set("paragraph.require_justified_body", v)}
          />
          <Toggle
            label="Require uniform alignment"
            checked={rules.paragraph?.require_uniform_alignment ?? false}
            disabled={disabled}
            onChange={(v) => set("paragraph.require_uniform_alignment", v)}
          />
        </div>
      </Panel>

      <Panel title="Decision" subtitle="How findings become a verdict">
        <Toggle
          label="Reject if any blocking check fails"
          checked={rules.decision?.reject_if_any_blocking ?? true}
          disabled={disabled}
          onChange={(v) => set("decision.reject_if_any_blocking", v)}
        />
        <Toggle
          label="Reject if any warning check fails"
          hint="Stricter: a wrong font alone will send a paper back."
          checked={rules.decision?.reject_if_any_warning ?? false}
          disabled={disabled}
          onChange={(v) => set("decision.reject_if_any_warning", v)}
        />
        <Field label="Minimum score to accept" hint="0-100. Blank disables the score floor; findings are then all that matter.">
          <NumberInput
            value={rules.decision?.min_score_to_accept}
            disabled={disabled}
            onChange={(v) => set("decision.min_score_to_accept", v)}
          />
        </Field>
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* small building blocks                                               */
/* ------------------------------------------------------------------ */

function Panel({ title, subtitle, children }) {
  return (
    <section className="panel animate-fade-in">
      <header className="panel-header">
        <h3 className="panel-title">{title}</h3>
        {subtitle && <p className="panel-subtitle">{subtitle}</p>}
      </header>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

function Subhead({ children }) {
  return (
    <p className="pt-1 text-xs font-semibold uppercase tracking-wide text-surface-400">
      {children}
    </p>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint" dangerouslySetInnerHTML={{ __html: hint }} />}
    </label>
  );
}

function Toggle({ label, hint, checked, disabled, onChange }) {
  return (
    <label className={`flex cursor-pointer items-start gap-3 ${disabled ? "cursor-not-allowed opacity-60" : ""}`}>
      <span className="relative mt-0.5 flex-shrink-0">
        <input
          type="checkbox"
          className="sr-only"
          checked={Boolean(checked)}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span
          className={`toggle-track block h-5 w-9 rounded-full transition-colors duration-200 ${
            checked ? "bg-primary-600" : "bg-surface-300 dark:bg-surface-600"
          }`}
        />
        <span
          className={`absolute left-0.5 top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-white shadow-lg transition-transform duration-200 ${
            checked ? "translate-x-5" : "translate-x-0"
          } dark:bg-surface-300`}
        />
      </span>
      <span>
        <span className="block text-sm text-surface-700 dark:text-surface-300">{label}</span>
        {hint && <span className="block text-xs text-surface-500 dark:text-surface-400" dangerouslySetInnerHTML={{ __html: hint }} />}
      </span>
    </label>
  );
}

function NumberInput({ value, disabled, step = "1", onChange }) {
  return (
    <input
      type="number"
      step={step}
      className="input-base"
      value={value === null || value === undefined ? "" : value}
      disabled={disabled}
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === "") return onChange(null);
        const parsed = Number(raw);
        onChange(Number.isNaN(parsed) ? null : parsed);
      }}
    />
  );
}

function FormatRow({ label, format, disabled, onChange }) {
  const isOn = Boolean(format);
  return (
    <div className="rounded-xl border border-surface-200 p-4 dark:border-surface-800 animate-fade-in">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-surface-700 dark:text-surface-300">{label}</span>
        <Toggle
          label={isOn ? "Enabled" : "Disabled"}
          checked={isOn}
          disabled={disabled}
          onChange={(v) => onChange(v ? { font_family: null, font_size_pt: null, bold: null } : null)}
        />
      </div>
      {isOn && (
        <div className="grid gap-3 sm:grid-cols-3 animate-slide-down">
          <input
            className="input-base"
            placeholder="font, e.g. Times New Roman"
            value={format?.font_family ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ ...format, font_family: e.target.value || null })}
          />
          <NumberInput
            value={format?.font_size_pt}
            disabled={disabled}
            step="0.5"
            onChange={(v) => onChange({ ...format, font_size_pt: v })}
          />
          <select
            className="input-base"
            value={format?.bold === null || format?.bold === undefined ? "" : String(format.bold)}
            disabled={disabled}
            onChange={(e) =>
              onChange({ ...format, bold: e.target.value === "" ? null : e.target.value === "true" })
            }
          >
            <option value="">weight: any</option>
            <option value="true">bold</option>
            <option value="false">not bold</option>
          </select>
        </div>
      )}
    </div>
  );
}

function TagList({ values, options, allowCustom, disabled, onChange }) {
  const [draft, setDraft] = useState("");

  function add(value) {
    const v = value.trim();
    if (!v || values.includes(v)) return;
    onChange([...values, v]);
    setDraft("");
  }

  const suggestions = options.filter((o) => !values.includes(o));

  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {values.map((value) => (
          <span
            key={value}
            className="tag tag-primary tag-removable"
          >
            {value}
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange(values.filter((v) => v !== value))}
              aria-label={`Remove ${value}`}
              className="ml-1 text-primary-500 hover:text-danger-600 dark:text-primary-400 dark:hover:text-danger-400"
            >
              &times;
            </button>
          </span>
        ))}
        {values.length === 0 && (
          <span className="text-xs italic text-surface-400">none</span>
        )}
      </div>
      {allowCustom && (
        <div className="mt-2 flex gap-2">
          <input
            className="input-base flex-1"
            placeholder="Add and press Enter"
            value={draft}
            disabled={disabled}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                add(draft);
              }
            }}
          />
          <button
            type="button"
            disabled={disabled || !draft.trim()}
            onClick={() => add(draft)}
            className="btn-secondary whitespace-nowrap"
          >
            Add
          </button>
        </div>
      )}
      {suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              disabled={disabled}
              onClick={() => add(s)}
              className="tag tag-neutral tag-removable border-dashed"
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}