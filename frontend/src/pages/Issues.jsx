import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { addIssueComment, errorMessage, getIssue, getIssueComments, getSubmissionWorkflow, listIssues, updateIssue } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import Button from "../components/ui/Button.jsx";
import Field from "../components/ui/Field.jsx";
import { findingValue } from "../components/PaperChecks.jsx";

const statuses = { open: "Open", in_progress: "In progress", resolved: "Resolved", wont_fix: "Won’t fix" };
export default function Issues() {
  const { submissionId } = useParams();
  return <IssueWorkspace key={submissionId} submissionId={submissionId} />;
}

function IssueWorkspace({ submissionId }) {
  const { user, loading: authLoading } = useAuth();
  const [params, setParams] = useSearchParams();
  const [issues, setIssues] = useState(null);
  const [chair, setChair] = useState(false);
  const [permissionError, setPermissionError] = useState("");
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const issueId = params.get("issue");
  const setFilter = (key, value) => setParams((current) => { const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); return next; });
  useEffect(() => {
    if (!user) return;
    let active = true; setError("");
    listIssues(submissionId).then((rows) => { if (active) setIssues(rows); }).catch((err) => { if (active) setError(errorMessage(err)); });
    getSubmissionWorkflow(submissionId).then((workflow) => { if (active) { setChair(Boolean(workflow.is_chair)); setPermissionError(""); } }).catch(() => { if (active) { setChair(false); setPermissionError("Assignment permissions could not be loaded."); } });
    return () => { active = false; };
  }, [submissionId, user, refresh]);
  const visible = issues?.filter((issue) => (!params.get("status") || issue.status === params.get("status")) && (!params.get("severity") || issue.severity === params.get("severity")) && (!params.get("revision") || issue.revision_id === params.get("revision")) && (!params.get("run") || issue.check_run_id === params.get("run")) && [issue.title, issue.description, issue.check_result_id].join(" ").toLowerCase().includes((params.get("q") || "").toLowerCase()));
  const listParams = new URLSearchParams(params); listParams.delete("issue");
  const listUrl = `/issues/${encodeURIComponent(submissionId)}${listParams.size ? `?${listParams}` : ""}`;
  if (authLoading) return <p role="status">Loading account…</p>;
  if (!user) return <p><Link to="/login">Sign in</Link> to view paper issues.</p>;
  return <div className="pf-paper-workspace pf-issues-workspace">
    <Link className="pf-paper-back" to={`/submissions/${encodeURIComponent(submissionId)}?tab=checks${params.get("revision") ? `&revision=${encodeURIComponent(params.get("revision"))}` : ""}${params.get("run") ? `&run=${encodeURIComponent(params.get("run"))}` : ""}`}>← Paper formatting checks</Link>
    <header className="pf-issues-heading"><div><p className="pf-paper-eyebrow">Paper workspace · {submissionId}</p><h1>Issues</h1><p>Track actionable findings without changing the original formatting report.</p></div>{issueId && <Link className="pf-button pf-button--secondary" to={listUrl}>All issues</Link>}</header>
    {permissionError && <p className="pf-checks-notice">{permissionError} <Button onClick={() => setRefresh((n) => n + 1)}>Retry permissions</Button></p>}
    {error && <div role="alert" className="pf-paper-error">{error} <Button onClick={() => setRefresh((n) => n + 1)}>Retry issues</Button></div>}
    {issueId ? <IssueDetail key={issueId} submissionId={submissionId} issueId={issueId} isChair={chair} onSaved={() => setRefresh((n) => n + 1)} /> : <>
      <div className="pf-issue-filters"><Field label="Search issues"><input type="search" value={params.get("q") || ""} placeholder="Title, description or rule ID" onChange={(event) => setFilter("q", event.target.value)} /></Field>
        <Field label="Issue status"><select value={params.get("status") || ""} onChange={(event) => setFilter("status", event.target.value)}><option value="">All statuses</option>{Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
        <Field label="Severity"><select value={params.get("severity") || ""} onChange={(event) => setFilter("severity", event.target.value)}><option value="">All severities</option>{["blocking", "warning", "advisory"].map((value) => <option key={value} value={value}>{value}</option>)}</select></Field></div>
      {(params.has("revision") || params.has("run")) && <p className="pf-checks-notice">Showing issues from {params.has("run") ? "the selected saved report" : "the selected revision"}. <Button onClick={() => setParams((current) => { const next = new URLSearchParams(current); next.delete("revision"); next.delete("run"); return next; })}>Show all revisions</Button></p>}
      <section className="pf-issue-list" aria-label="Tracked issues"><div className="pf-issue-list-heading"><h2>{issues ? `${visible.length} matching issues` : "Tracked issues"}</h2><span>{issues ? `${issues.filter((issue) => ["open", "in_progress"].includes(issue.status)).length} open · ${issues.filter((issue) => ["resolved", "wont_fix"].includes(issue.status)).length} closed` : ""}</span></div>
        {issues === null ? !error && <p role="status" className="pf-checks-empty">Loading issues…</p> : visible.length === 0 ? <div className="pf-checks-empty"><h3>{issues.length ? "No issues match these filters" : "No tracked issues yet"}</h3><p>{issues.length ? "Adjust the search, status or severity to see more findings." : "Findings linked to saved formatting runs will appear here."}</p></div> : <ul>{visible.map((issue) => {
          const next = new URLSearchParams(params); next.set("issue", issue.issue_id);
          return <li key={issue.issue_id}><span className={`pf-issue-mark is-${issue.status}`} aria-hidden="true">{["resolved", "wont_fix"].includes(issue.status) ? "✓" : "○"}</span><div><Link className="pf-issue-title" to={`?${next}`}>{issue.title}</Link><p><code>{issue.issue_id}</code> · {issue.category} · {new Date(issue.created_at).toLocaleDateString()}{issue.revision_id && " · Revision-linked"}</p></div><span className="pf-paper-context-label">{issue.severity}</span><span className={`pf-issue-status is-${issue.status}`}>{statuses[issue.status] || issue.status}</span></li>;
        })}</ul>}
      </section>
    </>}
  </div>;
}

function IssueDetail({ submissionId, issueId, isChair, onSaved }) {
  const [issue, setIssue] = useState(null);
  const [comments, setComments] = useState(null);
  const [status, setStatus] = useState("");
  const [assignee, setAssignee] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [commentsError, setCommentsError] = useState("");
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true; setError(""); setCommentsError("");
    getIssue(issueId).then((row) => { if (!active) return; if (row.submission_id !== submissionId) { setError("This issue is not available in this paper workspace."); return; } setIssue(row); setStatus(row.status); setAssignee(row.assignee_id || ""); }).catch((err) => { if (active) setError(errorMessage(err)); });
    getIssueComments(issueId).then((rows) => { if (active) setComments(rows); }).catch((err) => { if (active) setCommentsError(errorMessage(err)); });
    return () => { active = false; };
  }, [issueId, submissionId, refresh]);
  // A role downgrade must not leave a chair-only assignment draft available.
  useEffect(() => { if (!isChair) setAssignee(""); }, [isChair]);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const payload = { status };
      if (isChair && assignee.trim() && assignee.trim() !== issue.assignee_id) payload.assignee_id = assignee.trim();
      const saved = await updateIssue(issueId, payload); setIssue(saved); setStatus(saved.status); setAssignee(saved.assignee_id || ""); setNotice("Issue updated."); onSaved();
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  async function comment(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const saved = await addIssueComment(issueId, text.trim());
      setText(""); setNotice("Comment added.");
      // Append the confirmed response; do not repeat a successful POST on a GET failure.
      if (comments !== null) setComments((previous) => [...previous, saved]);
      else setRefresh((n) => n + 1);
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  return <section className="pf-issue-detail" aria-label="Issue details">
    {error && <div role="alert" className="pf-paper-error">{error} {!issue && <Button onClick={() => setRefresh((n) => n + 1)}>Retry issue</Button>}</div>}
    {notice && <p role="status" className="pf-checks-notice">{notice}</p>}
    {!issue ? !error && <p role="status">Loading issue…</p> : <>
      <div className="pf-issue-detail-title"><h2>{issue.title}</h2><span className={`pf-issue-status is-${issue.status}`}>{statuses[issue.status] || issue.status}</span><span className="pf-paper-context-label">{issue.severity}</span></div>
      <p className="pf-paper-muted"><code>{issue.issue_id}</code> · {issue.category} · Rule {issue.check_result_id || "ID not recorded"}</p>
      <div className="pf-issue-detail-layout"><div className="pf-issue-content"><section className="pf-issue-description"><h3>Finding</h3><p>{issue.description}</p>
        <dl><div><dt>Expected</dt><dd>{findingValue(issue.expected)}</dd></div><div><dt>Actual</dt><dd>{findingValue(issue.actual)}</dd></div></dl>
        {issue.advice && <p><strong>Suggested correction</strong><br />{issue.advice}</p>}{issue.evidence && <p className="pf-finding-evidence"><strong>Evidence</strong><br />{issue.evidence}</p>}
        {issue.revision_id ? <Link to={`/submissions/${encodeURIComponent(submissionId)}?revision=${encodeURIComponent(issue.revision_id)}&tab=checks${issue.check_run_id ? `&run=${encodeURIComponent(issue.check_run_id)}` : ""}`}>View original revision and formatting report →</Link> : <p className="pf-paper-muted">The original revision was not recorded for this legacy issue.</p>}
        <p className="pf-paper-muted">Changing issue status does not change the saved validation result.</p>
      </section><section className="pf-issue-comments"><h3>Discussion</h3>
        {commentsError && <div role="alert" className="pf-paper-error">{commentsError} <Button disabled={busy} onClick={() => setRefresh((n) => n + 1)}>Retry issue comments</Button></div>}
        {comments === null ? !commentsError && <p role="status">Loading comments…</p> : comments.length ? <ol>{comments.map((entry) => <li key={entry.comment_id}><div className="pf-comment-byline"><strong>{entry.author_id}</strong><time dateTime={entry.created_at}>{new Date(entry.created_at).toLocaleString()}</time></div><p>{entry.text}</p></li>)}</ol> : <p className="pf-paper-muted">No comments yet. Add context or explain how this finding was addressed.</p>}
        <form onSubmit={comment}><Field label="Issue comment" required><textarea value={text} maxLength={20000} disabled={busy} onChange={(event) => setText(event.target.value)} rows={4} /></Field><Button type="submit" variant="primary" busy={busy} disabled={!text.trim()}>Add comment</Button></form>
      </section></div><aside className="pf-issue-controls"><h3>Manage issue</h3><form onSubmit={save}><Field label="Status"><select value={status} disabled={busy} onChange={(event) => setStatus(event.target.value)}>{Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
        {isChair ? <Field label="Assignee account ID" hint="Enter an active account with paper access. Clearing an assignment is not supported by the current API."><input value={assignee} disabled={busy} onChange={(event) => setAssignee(event.target.value)} /></Field> : <p className="pf-paper-muted">Only conference chairs can assign issues.</p>}
        <p className="pf-paper-muted">Status updates require paper-editing access or an active reviewer assignment. The server verifies each change.</p>
        <Button type="submit" busy={busy} disabled={status === issue.status && (!isChair || !assignee.trim() || assignee.trim() === issue.assignee_id)}>Save changes</Button>
      </form><dl><div><dt>Created</dt><dd>{new Date(issue.created_at).toLocaleString()}</dd></div><div><dt>Updated</dt><dd>{new Date(issue.updated_at).toLocaleString()}</dd></div>{issue.resolved_at && <div><dt>Resolved</dt><dd>{new Date(issue.resolved_at).toLocaleString()}{issue.resolved_by && ` · ${issue.resolved_by}`}</dd></div>}</dl></aside></div>
    </>}
  </section>;
}
