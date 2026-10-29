import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { assignSubmissionReviewer, errorMessage, getCollaborators, getSubmissionWorkflow, removeCollaborator, revokeSubmissionReviewer, saveCollaborator, transitionSubmission } from "../lib/api.js";

const names = { submitted: "Submit for review", under_review: "Start review", changes_requested: "Request changes", accepted: "Accept paper", rejected: "Reject paper", withdrawn: "Withdraw paper" };

export default function SubmissionWorkflow({ submissionId, onChanged, onChairLoaded, reloadKey }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [workflow, setWorkflow] = useState(null);
  const [authors, setAuthors] = useState(null);
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [coauthor, setCoauthor] = useState("");
  const [canEdit, setCanEdit] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setError("");
    Promise.all([getSubmissionWorkflow(submissionId), getCollaborators(submissionId)])
      .then(([w, a]) => { if (active) { setWorkflow(w); setAuthors(a); onChairLoaded?.(w.is_chair); } })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [submissionId, refresh, onChairLoaded, reloadKey]);
  async function act(operation) {
    setBusy(true); setError("");
    try { await operation(); setRefresh((n) => n + 1); onChanged(); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <section className="panel p-5 space-y-4 pf-paper-workflow">
    <h2 className="text-lg font-semibold">Next actions</h2>
    <p className="pf-paper-action-context">Actions apply to the current revision. Earlier uploads remain available for reference.</p>
    {error && <p role="alert" className="text-danger-600">{error} <button type="button" className="btn-secondary" disabled={busy} onClick={() => setRefresh((n) => n + 1)}>Reload actions</button></p>}
    {!workflow ? !error && <p role="status">Loading workflow…</p> : <>
      <p>{workflow.eligible ? "Formatting policy allows this revision to proceed to review." : workflow.reason}</p>
      {workflow.submission_window?.reason && ["draft", "submitted", "changes_requested"].includes(workflow.status) && <p>{workflow.submission_window.reason}</p>}
      <p className="text-sm text-surface-500">Formatting policy: {workflow.formatting_gate === "block_errors" ? "Blocking errors must be corrected" : "Formatting findings may proceed to review"}</p>
      {workflow.status === "changes_requested" && <p>Upload a new revision, then resubmit it for review.</p>}
      {workflow.decision_reason && <p className="whitespace-pre-wrap">Decision reason: {workflow.decision_reason}</p>}
      {workflow.actions.length > 0 && <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act(async () => {
        await transitionSubmission(submissionId, { target_status: target, expected_status: workflow.status, expected_revision_id: workflow.revision_id, reason });
        setReason(""); setTarget("");
      }); }}>
        <label className="block">Action
          <select className="input-base mt-2" value={target} required disabled={busy} onChange={(e) => setTarget(e.target.value)}>
            <option value="">Choose an action</option>
            {workflow.actions.map((action) => <option key={action} value={action}>{names[action]}</option>)}
          </select>
        </label>
        <label className="block">Reason or response
          <textarea className="input-base mt-2" value={reason} maxLength={4000} disabled={busy} required={["changes_requested", "accepted", "rejected"].includes(target)} onChange={(e) => setReason(e.target.value)} />
        </label>
        <button className="btn-primary" disabled={busy || !target || (["submitted", "under_review"].includes(target) && !workflow.eligible) || (target === "submitted" && workflow.submission_window?.allowed === false) || (["under_review", "changes_requested", "accepted", "rejected"].includes(target) && workflow.review_phase_open === false)}>{busy ? "Saving…" : "Apply action"}</button>
      </form>}
      {workflow.is_chair && ["submitted", "under_review"].includes(workflow.status) && <div className="flex flex-wrap gap-3">
        {workflow.assignments.some((assignment) => assignment.reviewer_id === user?.user_id && ["pending", "accepted", "completed"].includes(assignment.status))
          ? <Link className="btn-secondary" to={`/submissions/${submissionId}?tab=reviews`}>Open my review →</Link>
          : <button type="button" className="btn-secondary" disabled={busy || !user || !workflow.eligible || workflow.review_phase_open === false} onClick={() => act(async () => {
            await assignSubmissionReviewer(submissionId, user.user_id);
            navigate(`/submissions/${submissionId}?tab=reviews`);
          })}>Review this paper</button>}
      </div>}
      {workflow.is_chair && ["submitted", "under_review"].includes(workflow.status) && <form className="space-y-3 border-t pt-4" onSubmit={(e) => { e.preventDefault(); act(async () => { await assignSubmissionReviewer(submissionId, reviewer); setReviewer(""); }); }}>
        <label className="block">Assign reviewer (account ID)
          <input className="input-base mt-2" value={reviewer} required disabled={busy} onChange={(e) => setReviewer(e.target.value)} />
        </label>
        <button className="btn-secondary" disabled={busy || !reviewer || !workflow.eligible || workflow.review_phase_open === false}>Assign and start review</button>
        <ul>{workflow.assignments.map((a) => <li key={a.assignment_id} className="text-sm flex gap-3 items-center">{a.reviewer_id} · {a.status}
          {a.status !== "revoked" && <button className="btn-secondary" type="button" disabled={busy} onClick={() => act(() => revokeSubmissionReviewer(submissionId, a.assignment_id))}>Revoke assignment</button>}
        </li>)}</ul>
      </form>}
      {authors && <section className="border-t pt-4 space-y-3">
        <h3 className="font-semibold">Paper collaborators</h3>
        <p className="text-sm">Submitting author: {authors.submitter_id || "Unclaimed"}</p>
        <ul className="space-y-2">{authors.collaborators.map((a) => <li key={a.user_id} className="flex flex-wrap items-center gap-3 text-sm">
          <span>{a.user_id} · {a.can_edit ? "Can upload and edit" : "Read and discuss"}</span>
          {authors.can_manage && !["accepted", "rejected", "withdrawn"].includes(workflow.status) && <>
            <button className="btn-secondary" disabled={busy} onClick={() => act(() => saveCollaborator(submissionId, a.user_id, !a.can_edit))}>{a.can_edit ? "Make read-only" : "Allow editing"}</button>
            <button className="btn-secondary" disabled={busy} onClick={() => act(() => removeCollaborator(submissionId, a.user_id))}>Remove</button>
          </>}
        </li>)}</ul>
        {authors.can_manage && !["accepted", "rejected", "withdrawn"].includes(workflow.status) && <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act(async () => { await saveCollaborator(submissionId, coauthor, canEdit); setCoauthor(""); }); }}>
          <label className="block">Coauthor account ID
            <input className="input-base mt-2" value={coauthor} required disabled={busy} onChange={(e) => setCoauthor(e.target.value)} />
          </label>
          <label className="flex gap-2"><input type="checkbox" checked={canEdit} disabled={busy} onChange={(e) => setCanEdit(e.target.checked)} /> Allow uploads and edits</label>
          <p className="text-xs text-surface-500">Coauthors need an existing account and conference membership.</p>
          <button className="btn-secondary" disabled={busy || !coauthor}>Grant paper access</button>
        </form>}
      </section>}
    </>}
  </section>;
}
