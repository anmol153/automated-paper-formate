import { Link } from "react-router-dom";
import StateBadge from "./ui/StateBadge.jsx";
import Button from "./ui/Button.jsx";
import UnderlineNav from "./ui/UnderlineNav.jsx";

const tabIcons = {
  conversation: "M7 4h14v12H9l-5 4V4h3", files: "M8 3h8l4 4v14H8V3M16 3v5h4M4 7v14", checks: "M9 5h11M9 12h11M9 19h11M3 5l1 1 2-3M3 12l1 1 2-3M3 19h3", compare: "M8 3v18M16 3v18M4 7h8M12 17h8M4 17h4M16 7h4",
};
export function PaperNavigation({ params, tab, revisionCount, submissionId }) {
  const item = ([id, label]) => {
    const next = new URLSearchParams(params); next.set("tab", id);
    return { id, label, to: `?${next}`, current: tab === id, count: id === "files" ? revisionCount : undefined,
      icon: tabIcons[id] && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={tabIcons[id]} /></svg> };
  };
  return <div className="pf-paper-navigation">
    <UnderlineNav label="Submission sections" className="pf-paper-tabs" items={[["conversation", "Conversation"], ["files", "Files and revisions"], ["checks", "Formatting checks"], ["compare", "Compare revisions"]].map(item)} />
    <UnderlineNav label="Paper tools" className="pf-paper-tools" items={[
      ...[["overview", "Overview"], ["document", "Document"], ["reviews", "Reviews"], ["activity", "Activity"]].map(item),
      { id: "issues", label: "Issues ↗", to: `/issues/${submissionId}` },
    ]} />
  </div>;
}

export function PaperHeader({ paper, currentRevision, revisionCount, canUpload, onNavigate }) {
  const title = paper.title || currentRevision?.metadata?.title || paper.filename;
  return <header className="pf-paper-header">
    <Link className="pf-paper-back" to={`/conferences/${paper.conference_id}/submissions`}>← Conference papers</Link>
    <div className="pf-paper-heading">
      <div><h1 aria-label={title}>{title}{paper.paper_number != null && <span className="pf-paper-number" aria-hidden="true"> #{paper.paper_number}</span>}</h1></div>
      <div className="pf-paper-actions"><Button onClick={() => onNavigate("document")} disabled={!currentRevision}>View document</Button>
        {canUpload && <Button variant="primary" onClick={() => onNavigate("files")}>Upload revision</Button>}</div>
    </div>
    <div className="pf-paper-status"><StateBadge status={paper.status} /><span>{revisionCount} {revisionCount === 1 ? "revision" : "revisions"} in this submission</span><span>Current revision {currentRevision?.number ?? "unavailable"}</span></div>
  </header>;
}

export function RevisionToolbar({ history, selected, selectedId, busy, onChange, onCurrent }) {
  const historical = selected && selectedId !== history.current_revision_id;
  return <div className={`pf-revision-context ${historical ? "is-historical" : ""}`}>
    <label>Viewing revision<select className="input-base" value={selectedId || ""} disabled={busy} onChange={(event) => onChange(event.target.value)}>
      {!selected && <option value={selectedId || ""}>Unknown revision</option>}
      {history.revisions.map((revision) => <option key={revision.revision_id} value={revision.revision_id}>Revision {revision.number} · {revision.filename}{revision.revision_id === history.current_revision_id ? " (current)" : ""}</option>)}
    </select></label>
    {historical ? <div className="pf-paper-historical"><span>Earlier upload · revision {selected.number}. Comments and reports stay with this revision.</span><Button size="small" onClick={onCurrent}>View current revision</Button></div> : <span className="pf-paper-muted">Files and reports are preserved for every revision.</span>}
  </div>;
}

export function PaperSidebar({ paper, selected, workflow, onNavigate }) {
  return <aside className="pf-paper-sidebar" aria-label="Paper information">
    <section className="pf-pr-reviewers"><h2>Reviewers</h2>
      {workflow?.is_chair ? <div className="pf-paper-assignees"><h3>Reviewer assignments</h3>{workflow.assignments?.length ? <ul>{workflow.assignments.map((assignment) => <li key={assignment.assignment_id}><span className="pf-reviewer-avatar" aria-hidden="true">R</span><span>{assignment.reviewer_id}</span><span className="pf-paper-context-label">{assignment.status}</span></li>)}</ul> : <p>No reviewers assigned.</p>}</div> : <p>Reviewer identities follow the conference’s visibility rules.</p>}
      <Button variant="quiet" onClick={() => onNavigate("reviews")}>Open reviews →</Button>
    </section>
    <section><h2>Conference</h2><Link to={`/conferences/${paper.conference_id}`}>Conference workspace ↗</Link></section>
    <section><h2>Authors</h2>{paper.authors?.length ? <ul className="pf-paper-authors">{paper.authors.map((author, index) => <li key={index}><strong>{author.name}</strong>{author.affiliation && <span>{author.affiliation}</span>}</li>)}</ul> : <p>No author details available to your account.</p>}</section>
    <section><h2>Selected revision{selected && <span className="pf-paper-context-label">v{selected.number}</span>}</h2>{selected ? <dl><div><dt>Document</dt><dd className="pf-paper-filename">{selected.filename}</dd></div>
      <div><dt>Uploaded</dt><dd>{new Date(selected.uploaded_at).toLocaleString()}</dd></div>
      <div><dt>Formatting</dt><dd><StateBadge status={selected.latest_check?.status} label={selected.latest_check ? undefined : "Not checked"} /></dd></div></dl> : <p>No available revision.</p>}
      <Button variant="quiet" onClick={() => onNavigate("checks")}>View formatting checks →</Button></section>
    <section><h2>Tracked issues</h2><Link to={`/issues/${paper.submission_id}`}>Open tracked issues →</Link></section>
  </aside>;
}

export function PaperReadiness({ workflow, onRetry, compact = false }) {
  const final = ["accepted", "rejected", "withdrawn"].includes(workflow?.status);
  const windowClosed = ["draft", "changes_requested"].includes(workflow?.status) && workflow?.submission_window?.allowed === false;
  const reviewClosed = ["submitted", "under_review", "changes_requested"].includes(workflow?.status) && workflow?.review_phase_open === false;
  const ready = workflow?.eligible && !final && !windowClosed && !reviewClosed;
  const owner = { draft: "Authors: prepare the paper and submit for review.", submitted: "Chairs: check readiness and assign reviewers.", under_review: "Assigned reviewers: complete reviews. Chairs manage the review process.", changes_requested: "Authors: upload a revision and respond to the requested changes." }[workflow?.status];
  const title = !workflow ? "Workflow summary unavailable" : final ? "Submission finalized" : windowClosed ? "Submission window closed" : reviewClosed ? "Review phase closed" : workflow.status === "under_review" ? "Review in progress" : workflow.status === "changes_requested" ? "Author revision requested" : workflow.eligible ? "Ready for the next review step" : "Attention needed before review";
  if (compact) return <section className={`pf-paper-readiness is-compact ${ready ? "is-ready" : ""}`} aria-label="Submission readiness"><span className="pf-readiness-mark" aria-hidden="true">{ready ? "✓" : "·"}</span><div>
    <div className="pf-readiness-title"><h2>{title}</h2><span className="pf-paper-muted">Current revision</span></div><p>{!workflow ? "Reload to check submission eligibility." : windowClosed ? workflow.submission_window.reason : reviewClosed ? "The conference review phase is closed." : final ? "This submission is closed." : !workflow.eligible ? workflow.reason : owner || workflow.reason}</p>
    {workflow && <details><summary>Readiness details</summary><p>{workflow.reason}</p>{workflow.submission_window?.reason && <p>{workflow.submission_window.reason}</p>}{owner && <p>{owner}</p>}</details>}
    {!workflow && <Button onClick={onRetry}>Reload workflow</Button>}
  </div></section>;
  return <section className={`pf-paper-readiness ${ready ? "is-ready" : ""}`} aria-label="Submission readiness"><span className="pf-readiness-mark" aria-hidden="true">{ready ? "✓" : "·"}</span><div><p className="pf-paper-eyebrow">Current revision workflow</p><h2>{title}</h2>
    <p>{workflow ? final ? "This submission is closed. Files, reviews, and activity follow the conference’s access rules." : workflow.reason || (workflow.eligible ? "Formatting policy allows this revision to proceed. Use an available workflow action below." : "Check the submission requirements and available actions below.") : "Reload to check permitted actions and submission eligibility."}</p>
    {workflow?.submission_window?.reason && ["draft", "submitted", "changes_requested"].includes(workflow.status) && <p>{workflow.submission_window.reason}</p>}
    {reviewClosed && <p>Review actions are unavailable in the conference’s current phase.</p>}
    {owner && <p>{owner}</p>}
    {!workflow && <Button onClick={onRetry}>Reload workflow</Button>}</div></section>;
}
