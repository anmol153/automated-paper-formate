import { Link } from "react-router-dom";
import StateBadge from "./ui/StateBadge.jsx";
import Button from "./ui/Button.jsx";

export function PaperHeader({ paper, currentRevision, canUpload, onNavigate }) {
  return <header className="pf-paper-header">
    <Link className="pf-paper-back" to={`/conferences/${paper.conference_id}/submissions`}>← Conference papers</Link>
    <div className="pf-paper-heading">
      <div><p className="pf-paper-eyebrow">Paper submission {paper.paper_number ? `#${paper.paper_number}` : ""}</p>
        <h1>{paper.title || currentRevision?.metadata?.title || paper.filename}</h1></div>
      <div className="pf-paper-actions"><Button onClick={() => onNavigate("document")} disabled={!currentRevision}>View document</Button>
        {canUpload && <Button variant="primary" onClick={() => onNavigate("files")}>Upload revision</Button>}</div>
    </div>
    <div className="pf-paper-status"><StateBadge status={paper.status} /><span>Current revision {currentRevision?.number ?? "unavailable"}</span><span className="pf-paper-id">{paper.submission_id}</span></div>
  </header>;
}

export function RevisionToolbar({ history, selected, selectedId, busy, onChange, onCurrent }) {
  return <div className="pf-revision-context">
    <label>Viewing revision<select className="input-base" value={selectedId || ""} disabled={busy} onChange={(event) => onChange(event.target.value)}>
      {!selected && <option value={selectedId || ""}>Unknown revision</option>}
      {history.revisions.map((revision) => <option key={revision.revision_id} value={revision.revision_id}>Revision {revision.number} · {revision.filename}{revision.revision_id === history.current_revision_id ? " (current)" : ""}</option>)}
    </select></label>
    {selected && selectedId !== history.current_revision_id ? <div className="pf-paper-historical"><span>Earlier upload · revision {selected.number}. Comments and reports stay with this revision.</span><Button size="small" onClick={onCurrent}>View current revision</Button></div> : <span className="pf-paper-muted">Files and reports are preserved for every revision.</span>}
  </div>;
}

export function PaperSidebar({ paper, selected, workflow, onNavigate }) {
  return <aside className="pf-paper-sidebar" aria-label="Paper information">
    <section><h2>Submission</h2><dl><div><dt>Conference</dt><dd><Link to={`/conferences/${paper.conference_id}`}>Conference workspace ↗</Link></dd></div>
      <div><dt>Paper number</dt><dd>{paper.paper_number ? `#${paper.paper_number}` : "Not assigned"}</dd></div>
      <div><dt>Review state</dt><dd><StateBadge status={paper.status} /></dd></div></dl></section>
    <section><h2>Authors</h2>{paper.authors?.length ? <ul className="pf-paper-authors">{paper.authors.map((author, index) => <li key={index}><strong>{author.name}</strong>{author.affiliation && <span>{author.affiliation}</span>}</li>)}</ul> : <p>No author details available to your account.</p>}</section>
    <section><h2>Selected revision</h2>{selected ? <dl><div><dt>Document</dt><dd className="pf-paper-filename">{selected.filename}</dd></div>
      <div><dt>Uploaded</dt><dd>{new Date(selected.uploaded_at).toLocaleString()}</dd></div>
      <div><dt>Formatting</dt><dd><StateBadge status={selected.latest_check?.status} label={selected.latest_check ? undefined : "Not checked"} /></dd></div></dl> : <p>No available revision.</p>}
      <Button variant="quiet" onClick={() => onNavigate("checks")}>View formatting checks →</Button></section>
    <section><h2>Review access</h2><p>Reviews and identities follow this conference’s visibility rules.</p><Button variant="quiet" onClick={() => onNavigate("reviews")}>Open reviews →</Button>
      {workflow?.is_chair && <div className="pf-paper-assignees"><h3>Reviewer assignments</h3>{workflow.assignments?.length ? <ul>{workflow.assignments.map((assignment) => <li key={assignment.assignment_id}><span>{assignment.reviewer_id}</span><span className="pf-paper-muted">{assignment.status}</span></li>)}</ul> : <p>No reviewers assigned.</p>}</div>}</section>
    <section><h2>About this workspace</h2><p>Formatting checks assess document requirements. Conference chairs record the final decision.</p><Link to={`/issues/${paper.submission_id}`}>Open tracked issues →</Link></section>
  </aside>;
}

export function PaperReadiness({ workflow, onRetry }) {
  const final = ["accepted", "rejected", "withdrawn"].includes(workflow?.status);
  const windowClosed = ["draft", "changes_requested"].includes(workflow?.status) && workflow?.submission_window?.allowed === false;
  const ready = workflow?.eligible && !final && !windowClosed;
  const owner = { draft: "Authors: prepare the paper and submit for review.", submitted: "Chairs: check readiness and assign reviewers.", under_review: "Assigned reviewers: complete reviews. Chairs manage the review process.", changes_requested: "Authors: upload a revision and respond to the requested changes." }[workflow?.status];
  const title = !workflow ? "Workflow summary unavailable" : final ? "Submission finalized" : windowClosed ? "Submission window closed" : workflow.status === "under_review" ? "Review in progress" : workflow.status === "changes_requested" ? "Author revision requested" : workflow.eligible ? "Ready for the next review step" : "Attention needed before review";
  return <section className={`pf-paper-readiness ${ready ? "is-ready" : ""}`} aria-label="Submission readiness"><span className="pf-readiness-mark" aria-hidden="true">{ready ? "✓" : "·"}</span><div><p className="pf-paper-eyebrow">Current revision workflow</p><h2>{title}</h2>
    <p>{workflow ? final ? "This submission is closed. Files, reviews, and activity follow the conference’s access rules." : workflow.reason || (workflow.eligible ? "Formatting policy allows this revision to proceed. Use an available workflow action below." : "Check the submission requirements and available actions below.") : "Reload to check permitted actions and submission eligibility."}</p>
    {workflow?.submission_window?.reason && ["draft", "submitted", "changes_requested"].includes(workflow.status) && <p>{workflow.submission_window.reason}</p>}
    {owner && <p>{owner}</p>}
    {!workflow && <Button onClick={onRetry}>Reload workflow</Button>}</div></section>;
}
