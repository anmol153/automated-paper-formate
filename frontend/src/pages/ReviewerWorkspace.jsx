import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { declareOwnConflict, errorMessage, getReviewerWorkspace, withdrawOwnConflict } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import Button, { ButtonLink } from "../components/ui/Button.jsx";
import StateBadge from "../components/ui/StateBadge.jsx";
import Field from "../components/ui/Field.jsx";
import ChairAssignments from "../components/ChairAssignments.jsx";

export default function ReviewerWorkspace() {
  const { user, loading } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reasons, setReasons] = useState({});
  const [refresh, setRefresh] = useState(0);
  const [search, setSearch] = useState("");
  const [reviewFilter, setReviewFilter] = useState("");
  const [chairCount, setChairCount] = useState(null);
  const [view, setView] = useState("auto");
  const chairView = view === "chair" || (view === "auto" && chairCount > 0);
  const personalView = view === "personal" || (view === "auto" && chairCount === 0);
  useEffect(() => {
    if (!user) return;
    let active = true;
    setData(null); setError("");
    getReviewerWorkspace().then((value) => { if (active) setData(value); }).catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [user, refresh]);
  async function act(operation) {
    setBusy(true); setError("");
    try { await operation(); setRefresh((n) => n + 1); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  if (loading) return <p role="status">Loading account…</p>;
  if (!user) return <div className="pf-management pf-card pf-empty"><h1>Reviewer workspace</h1><p>Sign in to see your review assignments.</p><ButtonLink variant="primary" to="/login">Sign in</ButtonLink></div>;
  const visible = data?.assignments.filter((item) => (!reviewFilter || item.review_state === reviewFilter) && `${item.title || ""} ${item.filename || ""} ${item.paper_number || ""}`.toLowerCase().includes(search.toLowerCase())) || [];
  return <div className="pf-management pf-reviewer-page pf-stack">
    <header className="pf-management-header"><div><p className="pf-eyebrow">PEER REVIEW</p><h1>{chairCount > 0 ? "Review assignments" : "Reviewer workspace"}</h1><p>{chairCount > 0 ? "Assign conference reviewers or review an eligible paper yourself." : "Your assigned papers, review progress and conflict declarations."}</p></div><Button disabled={busy} onClick={() => setRefresh((value) => value + 1)}>Refresh assignments</Button></header>
    {chairCount > 0 && <div className="pf-assignment-views" role="group" aria-label="Assignment workspace view"><Button aria-pressed={chairView} onClick={() => setView("chair")}>Conference assignments</Button><Button aria-pressed={personalView} onClick={() => setView("personal")}>My assigned reviews{data ? ` (${data.assignments.length})` : ""}</Button></div>}
    <ChairAssignments userId={user.user_id} refreshKey={refresh} visible={chairView} onLoaded={setChairCount} onAssigned={() => setRefresh((value) => value + 1)} />
    {personalView && error && <div role="alert" className="pf-message pf-message--error">{error} Use Refresh assignments to retry.</div>}
    {personalView && (!data ? !error && <div className="pf-card pf-empty" role="status">Loading review assignments…</div> : <>
      <section className="pf-card"><div className="pf-card-heading"><div><h2>Assigned papers</h2><p>Only papers currently assigned to your account.</p></div><span className="pf-count">{data.assignments.length} assignments</span></div>
      <div className="pf-review-filters"><label className="pf-search"><span className="sr-only">Search assigned papers</span><input type="search" placeholder="Search title, file or paper number…" value={search} onChange={(event) => setSearch(event.target.value)} /></label><label><span className="sr-only">Filter by review progress</span><select value={reviewFilter} onChange={(event) => setReviewFilter(event.target.value)}><option value="">All review progress</option><option value="not_started">Not started</option><option value="draft">Draft</option><option value="submitted">Submitted</option></select></label></div>
      {!visible.length && <div className="pf-empty"><span className="pf-empty-symbol" aria-hidden="true">✓</span><h3>{data.assignments.length ? "No papers match these filters." : "No active review assignments."}</h3><p>{data.assignments.length ? "Try another title or reset the filters." : "A conference chair will assign papers to you. New assignments will appear here."}</p>{(search || reviewFilter) && <Button onClick={() => { setSearch(""); setReviewFilter(""); }}>Clear review filters</Button>}</div>}
      {visible.map((a) => <article className="pf-assignment-row" key={a.assignment_id}>
        <div className="pf-assignment-heading"><div><span className="pf-eyebrow">{a.paper_number ? `PAPER #${a.paper_number}` : "ASSIGNED PAPER"}</span><Link to={`/submissions/${a.submission_id}`}>{a.title || a.filename}</Link>{a.title && <p>{a.filename}</p>}</div><ButtonLink to={`/submissions/${a.submission_id}?tab=reviews`}>{a.review_state === "submitted" ? "View review →" : "Open review →"}</ButtonLink></div>
        <div className="pf-assignment-meta"><StateBadge status={a.status} /><span className={`pf-status-chip${a.review_state === "submitted" ? " pf-status-chip--success" : ""}`}>Review: {a.review_state.replaceAll("_", " ")}</span><span>Deadline: {a.deadline ? new Date(a.deadline).toLocaleString() : "No deadline configured"}</span></div>
        <details className="pf-conflict-details"><summary>Declare a conflict of interest</summary><form className="pf-stack" onSubmit={(e) => { e.preventDefault(); act(() => declareOwnConflict(a.assignment_id, reasons[a.assignment_id])); }}>
          <Field label="Confidential reason for chairs" required><textarea rows={3} maxLength={4000} disabled={busy} value={reasons[a.assignment_id] || ""} onChange={(e) => setReasons({ ...reasons, [a.assignment_id]: e.target.value })} /></Field>
          <div><Button type="submit" disabled={busy}>Declare conflict and remove my assignment</Button></div>
        </form></details>
      </article>)}</section>
      {data.conflicts.length > 0 && <section className="pf-card"><div className="pf-card-heading"><div><h2>Your active conflict declarations</h2><p>These reasons are confidential to conference chairs.</p></div><span className="pf-count">{data.conflicts.length}</span></div><div className="pf-card-body pf-stack">
        {data.conflicts.map((c) => <form className="pf-stack pf-track-editor" key={c.conflict_id} onSubmit={(e) => { e.preventDefault(); act(() => withdrawOwnConflict(c.conflict_id, c.version, reasons[c.conflict_id])); }}>
          <p>{c.submission_id}</p><p className="text-sm whitespace-pre-wrap">{c.reason}</p>
          <Field label="Reason to withdraw this declaration" required><input maxLength={4000} disabled={busy} value={reasons[c.conflict_id] || ""} onChange={(e) => setReasons({ ...reasons, [c.conflict_id]: e.target.value })} /></Field>
          <div><Button type="submit" disabled={busy}>Withdraw declaration</Button></div>
          <p className="pf-fine-print">A chair must explicitly reassign you after resolution.</p>
        </form>)}
      </div></section>}
    </>)}
  </div>;
}
