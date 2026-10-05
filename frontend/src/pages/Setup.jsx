import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import RuleEditor from "../components/RuleEditor.jsx";
import { emptyRuleSet } from "../lib/ruleOptions.js";
import {
  createTemplate,
  deleteTemplate,
  errorMessage,
  getTemplate,
  importTemplate,
  listTemplates,
  updateTemplate,
} from "../lib/api.js";

export default function Setup() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [rules, setRules] = useState(() => emptyRuleSet());
  const [activeId, setActiveId] = useState("");
  const [templateFile, setTemplateFile] = useState(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setTemplates(await listTemplates());
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleImport() {
    if (!templateFile) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const imported = await importTemplate(templateFile);
      setRules(imported);
      setActiveId("");
      setStatus({
        tone: "ok",
        text: `Imported rules from ${templateFile.name}. Review and override them below, then save.`,
      });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const saved = activeId
        ? await updateTemplate(activeId, rules)
        : await createTemplate(rules);
      setRules(saved);
      setActiveId(saved.template_id);
      setTemplateFile(null);
      await refresh();
      setStatus({
        tone: "ok",
        text: `Saved "${saved.name}". Authors will be checked against these rules.`,
      });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoad(templateId) {
    if (!templateId) {
      setActiveId("");
      setRules(emptyRuleSet());
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setRules(await getTemplate(templateId));
      setActiveId(templateId);
      setTemplateFile(null);
      setStatus(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(templateId) {
    if (!window.confirm("Delete this template? This action cannot be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      await deleteTemplate(templateId);
      if (activeId === templateId) {
        setActiveId("");
        setRules(emptyRuleSet());
      }
      await refresh();
      setStatus({ tone: "ok", text: "Template deleted." });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="animate-fade-in">
      <header className="section-header mb-8">
        <div>
          <h1 className="section-title">Template setup</h1>
          <p className="section-subtitle">
            Upload the venue's template and its formatting rules are inferred for you. Every
            inferred value can be overridden before the rules are saved, and a blank value means
            that rule is not checked at all.
          </p>
        </div>
        <Link
          to="/submit"
          className="btn-secondary whitespace-nowrap"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Go to submission
        </Link>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        <div className="space-y-6 lg:col-span-1">
          <section className="panel animate-slide-up" aria-labelledby="import-heading">
            <h2 id="import-heading" className="panel-title">1. Import from a template file</h2>
            <div className="space-y-4">
              <Field label="Template file" hint="PDF, LaTeX, or Word document containing the venue's formatting guidelines.">
                <div className="flex flex-col sm:flex-row gap-3">
                  <input
                    type="file"
                    accept=".pdf,.tex,.latex,.docx"
                    onChange={(e) => {
                      setTemplateFile(e.target.files?.[0] ?? null);
                      setStatus(null);
                    }}
                    className="input-base file:mr-4 file:rounded-lg file:border-0 file:bg-primary-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-primary-700 hover:file:bg-primary-100 dark:file:bg-primary-500/15 dark:file:text-primary-300"
                    disabled={busy}
                  />
                  <button
                    type="button"
                    onClick={handleImport}
                    disabled={!templateFile || busy}
                    className="btn-secondary whitespace-nowrap"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Import rules
                  </button>
                </div>
              </Field>
            </div>
          </section>

          <section className="panel animate-slide-up" aria-labelledby="saved-heading">
            <h2 id="saved-heading" className="panel-title">2. Saved templates</h2>
            {templates.length === 0 ? (
              <div className="empty-state animate-fade-in">
                <svg className="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <p className="empty-state-title">No templates saved yet</p>
                <p className="empty-state-description">Authors cannot submit until a template exists. Import a template file above and save it.</p>
              </div>
            ) : (
              <div className="space-y-1">
                {templates.map((template) => (
                  <div
                    key={template.template_id}
                    className={`flex items-center gap-3 rounded-xl p-3 transition-all duration-150 ${
                      activeId === template.template_id
                        ? "bg-primary-50 border border-primary-200 dark:bg-primary-500/10 dark:border-primary-500/20"
                        : "hover:bg-surface-50 dark:hover:bg-surface-800/50"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-surface-800 dark:text-surface-100">
                        {template.name}
                      </p>
                      <p className="truncate text-xs text-surface-500 dark:text-surface-400">
                        {template.template_id}
                        {template.publisher?.conference_name
                          ? ` &middot; ${template.publisher.conference_name}`
                          : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleLoad(template.template_id)}
                      disabled={busy}
                      className={`btn-ghost text-xs whitespace-nowrap ${
                        activeId === template.template_id
                          ? "bg-primary-100 text-primary-700 dark:bg-primary-500/20 dark:text-primary-300"
                          : ""
                      }`}
                    >
                      {activeId === template.template_id ? "Loaded" : "Load"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(template.template_id)}
                      disabled={busy}
                      className="btn-ghost text-xs text-surface-400 hover:text-danger-600 hover:bg-danger-50 dark:hover:text-danger-400 dark:hover:bg-danger-500/10 whitespace-nowrap"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-3 pt-4 border-t border-surface-200 dark:border-surface-800">
              <button
                type="button"
                onClick={handleSave}
                disabled={busy || !rules.name.trim()}
                className="btn-primary"
              >
                {activeId ? "Save changes" : "Save template"}
              </button>
              <Link to="/submit" className="btn-secondary">
                Author view
              </Link>
            </div>
          </section>

          {error && (
            <div className="alert alert-danger animate-slide-down" role="alert">
              <div className="flex items-start gap-3">
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <p>{error}</p>
              </div>
            </div>
          )}
          {status && (
            <div className="alert alert-success animate-slide-down" role="status">
              <div className="flex items-start gap-3">
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                </svg>
                <p>{status.text}</p>
              </div>
            </div>
          )}

          <section className="panel animate-slide-up" aria-labelledby="review-heading">
            <h2 id="review-heading" className="panel-title">3. Review and override</h2>
            <RuleEditor rules={rules} onChange={setRules} disabled={busy} />
          </section>
        </div>

        <aside className="lg:col-span-1 animate-fade-in" aria-label="Quick reference">
          <div className="sticky top-24 space-y-4">
            <div className="panel p-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-surface-700 dark:text-surface-200 mb-3">Quick reference</h3>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between gap-4 py-2 border-b border-surface-200 dark:border-surface-800">
                  <dt className="text-surface-600 dark:text-surface-400">Empty value</dt>
                  <dd className="font-medium text-surface-900 dark:text-surface-100 text-right">Means "not checked"</dd>
                </div>
                <div className="flex justify-between gap-4 py-2 border-b border-surface-200 dark:border-surface-800">
                  <dt className="text-surface-600 dark:text-surface-400">Blocking checks</dt>
                  <dd className="font-medium text-danger-600 dark:text-danger-400 text-right">Fail = reject paper</dd>
                </div>
                <div className="flex justify-between gap-4 py-2 border-b border-surface-200 dark:border-surface-800">
                  <dt className="text-surface-600 dark:text-surface-400">Warning checks</dt>
                  <dd className="font-medium text-warning-600 dark:text-warning-400 text-right">Fail = needs review</dd>
                </div>
                <div className="flex justify-between gap-4 py-2">
                  <dt className="text-surface-600 dark:text-surface-400">Score threshold</dt>
                  <dd className="font-medium text-primary-600 dark:text-primary-400 text-right">Minimum % to accept</dd>
                </div>
              </dl>
            </div>

            <div className="panel p-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-surface-700 dark:text-surface-200 mb-3">Tips</h3>
              <ul className="space-y-2 text-sm text-surface-600 dark:text-surface-400">
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-primary-500 shrink-0" aria-hidden="true" />
                  Import first, then review every field before saving
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-primary-500 shrink-0" aria-hidden="true" />
                  Leave margins blank to skip margin checks entirely
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-primary-500 shrink-0" aria-hidden="true" />
                  Use "Allowed font families" for multiple acceptable fonts
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-primary-500 shrink-0" aria-hidden="true" />
                  Set page-count tolerance for LaTeX/Word estimates
                </li>
              </ul>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}