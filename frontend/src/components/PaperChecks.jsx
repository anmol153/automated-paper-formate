import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PaperCard } from "../pages/Results.jsx";
import { CATEGORY_LABELS, CATEGORY_ORDER } from "../lib/ruleOptions.js";
import Button from "./ui/Button.jsx";
import Field from "./ui/Field.jsx";
import StateBadge from "./ui/StateBadge.jsx";

const statusLabels = { passed: "Passed", failed: "Failed", missing: "Missing", not_applicable: "Not evaluated" };
const marks = { passed: "✓", failed: "×", missing: "!", not_applicable: "−" };
const categoryLabel = (category) => CATEGORY_LABELS[category] || { document: "Document metadata", policy: "Submission policy", other: "Other checks" }[category] || category.replaceAll("_", " ");
export const findingValue = (value) => value == null ? "Not available" : typeof value === "object" ? JSON.stringify(value) : String(value);

export default function PaperChecks({ submissionId, revision, runs, report, requestedRun, loading, error, busy, checking, canRecheck, onRecheck, onRetry, onRunChange }) {
  return <section className="pf-checks" aria-label="Revision formatting checks">
    <div className="pf-checks-heading"><div><h2>Formatting checks · Revision {revision.number}</h2><p>Saved validation results for {revision.filename}.</p></div>
      {canRecheck && <Button busy={checking} disabled={busy} onClick={onRecheck}>{checking ? "Checking…" : "Run checks again"}</Button>}
    </div>
    <p className="pf-checks-policy">Formatting validation checks document requirements. It does not accept or reject a paper for the conference.</p>
    {checking && <p role="status" className="pf-checks-notice">Processing this revision. Saved reports remain available; a new run will be added when validation finishes.</p>}
    {loading ? <p role="status" className="pf-checks-empty">Loading saved reports…</p> : error ? <div role="alert" className="pf-paper-error">{error} <Button onClick={onRetry}>Retry saved reports</Button></div> : <>
      {runs.length > 0 && <div className="pf-checks-run-bar"><Field label="Saved report"><select value={report?.run_id || ""} disabled={busy} onChange={(event) => onRunChange(event.target.value)}>
        {!report && <option value="">Requested report unavailable</option>}
        {runs.map((run) => <option key={run.run_id} value={run.run_id}>Run {run.sequence} · {new Date(run.created_at).toLocaleString()} · {run.status.replaceAll("_", " ")}</option>)}
      </select></Field><span>Reports are retained for this immutable upload.</span></div>}
      {report ? <SavedCheck key={report.run_id} submissionId={submissionId} revision={revision} report={report} /> : <div className="pf-checks-empty">
        <h3>{requestedRun ? "Saved report unavailable" : "No saved formatting report"}</h3>
        <p>{requestedRun ? "The requested saved report is unavailable for this revision." : "No saved formatting report for this revision."}</p>
        {requestedRun && <Link to={`/submissions/${encodeURIComponent(submissionId)}?revision=${encodeURIComponent(revision.revision_id)}&tab=checks`}>View latest saved report</Link>}
      </div>}
    </>}
  </section>;
}

function SavedCheck({ submissionId, revision, report }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const results = report.assessment?.results || [];
  const groups = useMemo(() => {
    const map = new Map();
    for (const item of results) {
      if (filter !== "all" && (filter === "attention" ? !["failed", "missing"].includes(item.status) : item.status !== filter)) continue;
      if (search && ![item.name, item.id, item.category].join(" ").toLowerCase().includes(search.toLowerCase())) continue;
      const category = item.category || "other";
      if (!map.has(category)) map.set(category, []);
      map.get(category).push(item);
    }
    return [...CATEGORY_ORDER, ...[...map.keys()].filter((key) => !CATEGORY_ORDER.includes(key))].filter((key) => map.has(key)).map((key) => [key, map.get(key)]);
  }, [results, filter, search]);
  const issues = report.issues || [];
  return <>
    <section className="pf-check-summary"><div className="pf-check-summary-title"><h3>Run {report.sequence}</h3><StateBadge status={report.status} /></div>
      <p className="pf-paper-muted"><time dateTime={report.created_at}>{new Date(report.created_at).toLocaleString()}</time> · Template {revision.template_id}{report.engine_version && ` · Engine ${report.engine_version}`}</p>
      {report.error && <p role="alert" className="pf-paper-error">{report.error}</p>}
      {report.assessment ? <div className="pf-check-totals" aria-label="Saved check totals">{Object.entries(statusLabels).map(([status, label]) => <span key={status} className={`pf-finding-status is-${status}`}><span aria-hidden="true">{marks[status]}</span> {results.filter((item) => item.status === status).length} {label.toLowerCase()}</span>)}</div> : <p>No assessment was saved for this run. Its status is preserved; an older successful run is not substituted.</p>}
      {issues.length > 0 && <Link to={`/issues/${encodeURIComponent(submissionId)}?revision=${encodeURIComponent(revision.revision_id)}&run=${encodeURIComponent(report.run_id)}`}>{issues.length} tracked {issues.length === 1 ? "issue" : "issues"} from this report →</Link>}
    </section>
    {report.assessment && <>
      <div className="pf-check-filters"><Field label="Search checks"><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Check name or rule ID" /></Field>
        <Field label="Check status"><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All checks</option><option value="attention">Needs attention</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field></div>
      <p className="pf-paper-muted">Not evaluated means disabled or unmeasurable for this file. It is excluded from the compliance score.</p>
      {groups.length === 0 && <div className="pf-checks-empty">{results.length ? "No checks match these filters." : "This assessment contains no individual check results."}</div>}
      <div className="pf-check-suites">{groups.map(([category, items]) => <details className="pf-check-suite" key={category} open>
        <summary><strong>{categoryLabel(category)}</strong><span className="pf-counter">{items.length}</span><span className="pf-paper-muted">{items.filter((item) => ["failed", "missing"].includes(item.status)).length} to review</span></summary>
        {items.map((item, index) => <details key={`${item.id}:${index}`} className="pf-finding">
          <summary><span className={`pf-finding-mark is-${item.status}`} aria-hidden="true">{marks[item.status] || "?"}</span><strong>{item.name}</strong><span className={`pf-finding-status is-${item.status}`}>{statusLabels[item.status] || "Unknown"}</span>{["failed", "missing"].includes(item.status) && item.severity && <span className="pf-paper-context-label">{item.severity}</span>}</summary>
          <div className="pf-finding-body"><dl><div><dt>Expected</dt><dd>{findingValue(item.expected)}</dd></div><div><dt>Actual</dt><dd>{findingValue(item.actual)}</dd></div></dl>
            {item.advice && <p><strong>Suggested correction</strong><br />{item.advice}</p>}
            {item.evidence && <p className="pf-finding-evidence"><strong>Evidence</strong><br />{item.evidence}</p>}
            {item.confidence && <p className="pf-paper-muted">Measurement confidence: {item.confidence}</p>}
            {item.id && <p className="pf-paper-muted">Rule ID: <code>{item.id}</code></p>}
            {item.rule && <p className="pf-paper-muted">Requirement: {item.rule}</p>}
            {item.id && issues.filter((issue) => issue.rule_id === item.id).map((issue) => <Link key={issue.issue_id} to={`/issues/${encodeURIComponent(submissionId)}?issue=${encodeURIComponent(issue.issue_id)}`}>Open tracked issue →</Link>)}
          </div>
        </details>)}
      </details>)}</div>
      <details className="pf-original-report"><summary>Original detailed formatting report</summary><PaperCard key={report.run_id} paper={report.assessment} defaultOpen validationLabel={report.status.replaceAll("_", " ")} /></details>
    </>}
  </>;
}
