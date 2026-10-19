import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listReports, getReport, deleteReport, errorMessage } from "../lib/api.js";
import FileIcon from "../components/FileIcon.jsx";
import FormattingWorkspace, { formattingVerdictLabel } from "../components/layout/FormattingWorkspace.jsx";
import Button, { ButtonLink } from "../components/ui/Button.jsx";

export default function Reports() {
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(new Set());
  const [opening, setOpening] = useState("");
  const [search, setSearch] = useState("");
  const [verdict, setVerdict] = useState("");
  useEffect(() => { loadReports(); }, []);
  async function loadReports() {
    setLoading(true); setError("");
    try { setReports(await listReports()); }
    catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  }
  async function open(report) {
    setOpening(report.filename); setError("");
    try { const fullReport = await getReport(report.filename); navigate("/results", { state: { report: fullReport } }); }
    catch (err) { setError(errorMessage(err)); }
    finally { setOpening(""); }
  }
  async function remove(filename) {
    if (!window.confirm("Delete this report? This cannot be undone.")) return;
    setDeleting((previous) => new Set(previous).add(filename)); setError("");
    try { await deleteReport(filename); setReports((previous) => previous.filter((item) => item.filename !== filename)); }
    catch (err) { setError(errorMessage(err)); }
    finally { setDeleting((previous) => { const next = new Set(previous); next.delete(filename); return next; }); }
  }
  const visible = reports.filter((report) => (!verdict || report.verdict === verdict) && `${report.paper_title || ""} ${report.filename} ${report.template_name || ""} ${report.authors?.join(" ") || ""}`.toLowerCase().includes(search.toLowerCase()));
  return <FormattingWorkspace title="Saved reports" description="Revisit formatting results, inspect findings and manage your saved reports." actions={<ButtonLink variant="primary" to="/submit">+ Check papers</ButtonLink>}>
    {error && <div role="alert" className="pf-message pf-message--error">{error} <Button onClick={loadReports} disabled={loading}>Retry reports</Button></div>}
    <section className="pf-card"><div className="pf-list-toolbar"><div><h2>Report history <span className="pf-count">{loading ? "…" : reports.length}</span></h2><p>Formatting results are separate from conference decisions.</p></div><Button onClick={loadReports} disabled={loading}>Refresh reports</Button></div>
      <div className="pf-format-report-filters"><label className="pf-search"><span className="sr-only">Search reports</span><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search paper, author or template…" /></label><label><span className="sr-only">Filter report result</span><select value={verdict} onChange={(event) => setVerdict(event.target.value)}><option value="">All results</option>{["accepted", "needs_review", "rejected"].map((value) => <option value={value} key={value}>{formattingVerdictLabel(value)}</option>)}</select></label></div>
      {loading ? <div className="pf-empty" role="status">Loading reports…</div> : !visible.length ? <div className="pf-empty"><span className="pf-empty-symbol" aria-hidden="true">▤</span><h2>{search || verdict ? "No matching reports" : "No reports yet"}</h2><p>{search || verdict ? "Try another search or clear the result filter." : "Check a paper or compare documents to generate your first formatting report."}</p>{search || verdict ? <Button onClick={() => { setSearch(""); setVerdict(""); }}>Clear report filters</Button> : <ButtonLink to="/submit">Check a paper →</ButtonLink>}</div> : <ul className="pf-format-report-list">{visible.map((report) => <li className="pf-format-report-row" key={report.filename}><FileIcon name={report.filename} className="pf-report-file-icon" /><div className="pf-format-report-document"><button type="button" className="pf-report-open" disabled={!!opening || deleting.has(report.filename)} onClick={() => open(report)}>{opening === report.filename ? "Opening…" : report.paper_title || report.filename}</button>{report.paper_title && <p>{report.filename}</p>}{report.authors?.length > 0 && <p>{report.authors.slice(0, 2).join(", ")}{report.authors.length > 2 ? ` +${report.authors.length - 2} more` : ""}</p>}<div className="pf-report-meta"><span>{report.format?.toUpperCase() || "Document"}</span>{report.template_name && <span>{report.template_name}</span>}{report.updated_at && <time dateTime={report.updated_at}>{new Date(report.updated_at).toLocaleString()}</time>}</div></div><div className="pf-report-score"><span className={`pf-status-chip${report.verdict === "accepted" ? " pf-status-chip--success" : report.verdict === "rejected" ? " pf-status-chip--danger" : " pf-status-chip--attention"}`}>{formattingVerdictLabel(report.verdict)}</span><strong>{report.score === undefined || report.score === null ? "—" : `${report.score}%`}</strong></div><Button variant="quiet" disabled={deleting.has(report.filename)} aria-label={`Delete report ${report.paper_title || report.filename}`} onClick={() => remove(report.filename)}>{deleting.has(report.filename) ? "Deleting…" : "Delete"}</Button></li>)}</ul>}
      {!loading && <div className="pf-table-footer">{visible.length} of {reports.length} reports</div>}
    </section>
  </FormattingWorkspace>;
}
