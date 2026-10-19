import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { errorMessage, getReviewerWorkspace } from "../lib/api.js";
import Button, { ButtonLink } from "../components/ui/Button.jsx";

export default function MySchedule() {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!user) return;
    let active = true; setData(null); setError("");
    getReviewerWorkspace().then((value) => { if (active) setData(value); }).catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [user, attempt]);
  if (authLoading) return <p role="status">Loading account…</p>;
  if (!user) return <div className="pf-management pf-card pf-empty"><h1>My schedule</h1><p>Sign in to see deadlines for your review assignments.</p><ButtonLink to="/login" variant="primary">Sign in</ButtonLink></div>;
  const scheduled = (data?.assignments || []).filter((item) => item.deadline && Number.isFinite(Date.parse(item.deadline))).sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline));
  const undated = (data?.assignments || []).filter((item) => !item.deadline || !Number.isFinite(Date.parse(item.deadline)));
  return <div className="pf-management pf-stack"><header className="pf-management-header"><div><p className="pf-eyebrow">YOUR RESEARCH CALENDAR</p><h1>My schedule</h1><p>Review deadlines for papers currently assigned to you.</p></div><Button disabled={!data && !error} onClick={() => setAttempt((value) => value + 1)}>Refresh schedule</Button></header>
    {error && <div role="alert" className="pf-message pf-message--error">{error} Use Refresh schedule to retry.</div>}
    {!data ? !error && <div className="pf-card pf-empty" role="status">Loading schedule…</div> : <div className="pf-dashboard-columns"><section className="pf-card"><div className="pf-card-heading"><div><h2>Review deadlines</h2><p>Times are shown in your local timezone.</p></div><span className="pf-count">{scheduled.length}</span></div>
      {!scheduled.length ? <div className="pf-empty"><span className="pf-empty-symbol" aria-hidden="true">▦</span><h3>No review deadlines scheduled</h3><p>Deadlines appear when a chair assigns a paper and configures its review deadline.</p><ButtonLink to="/reviewer">Open review workspace →</ButtonLink></div> : scheduled.map((item) => {
        const date = new Date(item.deadline); const submitted = item.review_state === "submitted"; const overdue = !submitted && date.getTime() < Date.now();
        return <article className="pf-schedule-row" key={item.assignment_id}><div className="pf-calendar-date" aria-hidden="true"><span>{date.toLocaleDateString(undefined, { month: "short" })}</span><strong>{date.getDate()}</strong></div><div><span className="pf-eyebrow">{item.paper_number ? `PAPER #${item.paper_number}` : "REVIEW DEADLINE"}</span><Link to={`/submissions/${item.submission_id}?tab=reviews`}>{item.title || item.filename}</Link><time dateTime={item.deadline}>{date.toLocaleString()}</time><span className={`pf-status-chip${submitted ? " pf-status-chip--success" : overdue ? " pf-status-chip--attention" : ""}`}>{submitted ? "Review submitted" : overdue ? "Overdue" : "Review due"}</span></div></article>;
      })}</section><aside className="pf-card"><div className="pf-card-heading"><div><h2>Without a deadline</h2><p>Current assignments with no usable review date.</p></div></div><div className="pf-card-body pf-stack">{!undated.length ? <p>No undated assignments.</p> : undated.map((item) => <div key={item.assignment_id}><Link to={`/submissions/${item.submission_id}?tab=reviews`}>{item.title || item.filename}</Link><p className="pf-fine-print">{item.deadline ? "Deadline unavailable" : "No deadline configured"}</p></div>)}<p className="pf-fine-print">Conference event schedules and author submission calendars are not currently included.</p></div></aside></div>}
  </div>;
}
