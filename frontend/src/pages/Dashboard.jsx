import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { errorMessage, getReviewerWorkspace, listConferences } from "../lib/api.js";
import Button, { ButtonLink } from "../components/ui/Button.jsx";

export default function Dashboard() {
  const { user, loading } = useAuth();
  const [directory, setDirectory] = useState(null);
  const [reviews, setReviews] = useState(null);
  const [errors, setErrors] = useState({});
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!user) return;
    let active = true; setErrors({}); setDirectory(null); setReviews(null);
    listConferences().then((rows) => { if (active) setDirectory(rows); }).catch((err) => { if (active) setErrors((prev) => ({ ...prev, directory: errorMessage(err) })); });
    getReviewerWorkspace().then((data) => { if (active) setReviews(data); }).catch((err) => { if (active) setErrors((prev) => ({ ...prev, reviews: errorMessage(err) })); });
    return () => { active = false; };
  }, [user, attempt]);
  if (loading) return <p role="status">Loading workspace…</p>;
  if (!user) return <div className="pf-management pf-empty"><h1>Your research workspace</h1><p>Sign in to see your assignments and manage your conferences.</p><ButtonLink variant="primary" to="/login">Sign in</ButtonLink></div>;
  const assignments = reviews?.assignments || [];
  const outstanding = assignments.filter((item) => !["submitted", "finalized"].includes(item.review_state));
  return <div className="pf-management">
    <header className="pf-management-header"><div><p className="pf-eyebrow">YOUR WORKSPACE</p><h1>Welcome back, {user.full_name?.split(" ")[0] || "researcher"}.</h1><p>Pick up your reviews or get your next conference ready.</p></div><ButtonLink variant="primary" to="/conferences/new">+ Create conference</ButtonLink></header>
    {Object.entries(errors).map(([key, text]) => <div className="pf-message pf-message--error" role="alert" key={key}>{text} <Button onClick={() => setAttempt((n) => n + 1)}>Retry dashboard</Button></div>)}
    <div className="pf-stat-grid">{[["Conference directory", directory?.length, "Conferences available to explore", "/conferences"], ["Assigned reviews", reviews && assignments.length, "Your active paper assignments", "/reviewer"], ["Reviews to complete", reviews && outstanding.length, "Assignments without a submitted review", "/reviewer"]].map(([title, count, hint, to]) => <Link to={to} className="pf-stat-card" key={title}><span>{title}<span aria-hidden="true">↗</span></span><strong>{count ?? "—"}</strong><small>{hint}</small></Link>)}</div>
    <div className="pf-dashboard-columns"><section className="pf-card"><div className="pf-card-heading"><div><h2>Conference directory</h2><p>Explore events and open a conference workspace.</p></div><Link to="/conferences">View all →</Link></div>{!directory ? <p className="pf-card-body" role="status">{errors.directory ? "Directory unavailable." : "Loading conferences…"}</p> : !directory.length ? <div className="pf-empty"><h3>Your next conference starts here</h3><p>No conferences have been created yet. Set up the first one and invite your team.</p><ButtonLink to="/conferences/new">Create conference</ButtonLink></div> : <div className="pf-directory-rows">{directory.slice(0, 5).map((conf) => <Link key={conf.conference_id} to={`/conferences/${conf.conference_id}`}><span className="pf-conference-monogram">{conf.name.slice(0, 2).toUpperCase()}</span><div><strong>{conf.name}</strong><p>{conf.description || "Open conference workspace"}</p></div><span aria-hidden="true">→</span></Link>)}</div>}</section>
    <aside className="pf-card"><div className="pf-card-heading"><div><h2>Your next review</h2><p>Only papers assigned to you.</p></div></div>{!reviews ? <p className="pf-card-body" role="status">{errors.reviews ? "Assignments unavailable." : "Loading assignments…"}</p> : outstanding.length ? <div className="pf-card-body pf-stack">{outstanding.slice(0, 3).map((item) => <div className="pf-review-task" key={item.assignment_id}><span className="pf-eyebrow">{item.paper_number ? `PAPER #${item.paper_number}` : "ASSIGNED PAPER"}</span><Link to={`/submissions/${item.submission_id}`}>{item.title || item.filename}</Link><p>{item.deadline ? `Due ${new Date(item.deadline).toLocaleDateString()}` : "No deadline configured"}</p></div>)}<Link to="/reviewer">All review assignments →</Link></div> : <div className="pf-empty"><span className="pf-empty-symbol" aria-hidden="true">✓</span><h3>You're all caught up</h3><p>No reviews are waiting for you. New assignments will appear here.</p><Link to="/reviewer">Review workspace →</Link></div>}</aside></div>
    <section className="pf-quick-links" aria-label="Quick actions"><Link to="/submit"><strong>Check a manuscript →</strong><span>Validate against formatting rules</span></Link><Link to="/reports"><strong>Saved reports →</strong><span>Revisit your formatting results</span></Link><Link to="/notifications"><strong>Notifications →</strong><span>Follow updates across your work</span></Link></section>
  </div>;
}
