import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { declareOwnConflict, declareReviewConflict, errorMessage, getFormalReviews, getReviewConflicts, getReviewHistory, releaseFormalReviews, resolveReviewConflict, saveFormalReview } from "../lib/api.js";

export default function FormalReviews({ submissionId, revisionId, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    getFormalReviews(submissionId).then((value) => { if (active) setData(value); }).catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [submissionId, refresh]);
  async function act(operation) {
    setBusy(true); setError(""); setNotice("");
    try { await operation(); setRefresh((n) => n + 1); onChanged(); return true; }
    catch (err) { setError(errorMessage(err)); return false; }
    finally { setBusy(false); }
  }
  return <section className="space-y-5">
    <h2 className="text-lg font-semibold">Formal reviews</h2>
    {error && <p role="alert" className="text-danger-600">{error} <button className="btn-secondary ml-2" disabled={busy} onClick={() => { setError(""); setRefresh((n) => n + 1); }}>Reload reviews</button></p>}
    {notice && <p role="status">{notice}</p>}
    {!data ? !error && <p role="status">Loading formal reviews…</p> : <>
      {data.decision && <section className="panel p-5"><h3 className="font-semibold">Conference decision: {data.decision.decision}</h3><p className="whitespace-pre-wrap mt-2">{data.decision.reason}</p></section>}
      {data.is_chair && <section className="panel p-5 space-y-3">
        <h3 className="font-semibold">Chair review progress</h3>
        <p>{data.progress.submitted} submitted · {data.progress.missing} missing for the current revision</p>
        <p className="text-sm">Minimum reviews for a decision: {data.configuration.policy.minimum_reviews}. Draft contents are private to the reviewer.</p>
        <ul className="text-sm space-y-2">{data.progress.assignments.map((a) => <li key={a.assignment_id}>{a.reviewer_id} · {a.eligible ? a.review_state.replaceAll("_", " ") : a.status}</li>)}</ul>
        <p className="text-sm text-surface-500">Release includes submitted reviews of the current revision. Chair-only fields stay private. Reviewer identities will be {data.configuration.policy.reviewer_identities}.</p>
        <button className="btn-primary" disabled={busy || !data.progress.submitted} onClick={() => act(async () => { const result = await releaseFormalReviews(submissionId, data.revision_id); setNotice(`${result.released} review version(s) released to authors.`); })}>Release submitted reviews to authors</button>
      </section>}
      {data.assignment_id && <ReviewEditor key={`${data.revision_id}-${data.own_review?.version || 0}`} data={data} selectedRevisionId={revisionId} busy={busy} act={act} submissionId={submissionId} />}
      {data.reviews.length === 0 && <p className="panel p-5">No reviews are visible to you yet. Authors see reviews after a chair releases them.</p>}
      {data.reviews.map((review) => <ReviewCard key={review.review_id} review={review} submissionId={submissionId} />)}
      {data.is_chair && <ConflictManagement submissionId={submissionId} refresh={refresh} busy={busy} act={act} />}
    </>}
  </section>;
}

function ReviewEditor({ data, selectedRevisionId, busy, act, submissionId }) {
  const navigate = useNavigate();
  const own = data.own_review;
  const form = own?.form || data.configuration.form;
  const [answers, setAnswers] = useState(own?.answers || {});
  const [recommendation, setRecommendation] = useState(own?.recommendation || "");
  const [confidential, setConfidential] = useState(own?.confidential_comments || "");
  const [conflict, setConflict] = useState("");
  const current = selectedRevisionId === data.revision_id;
  async function save(submit) {
    await act(() => saveFormalReview(submissionId, { assignment_id: data.assignment_id, revision_id: data.revision_id,
      form_id: own?.form_id || data.configuration.form_id, expected_version: own?.version || 0, submit,
      answers, recommendation: recommendation || null, confidential_comments: confidential }));
  }
  return <section className="panel p-5 space-y-4">
    <h3 className="font-semibold">Your review · {form.name}</h3>
    <p className="text-sm">{own ? `Version ${own.version} · ${own.state}` : "Not started"}. This form is bound to the current paper revision.</p>
    {data.configuration.policy.deadline && <p className="text-sm">Deadline: {new Date(data.configuration.policy.deadline).toLocaleString()}</p>}
    {!current && <p>You are viewing an earlier paper revision. Select the current revision before writing a review.</p>}
    {!data.can_review && <p>Review editing is currently closed. The paper status, deadline, and submitted-review policy determine when edits are allowed.</p>}
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save(true); }}>
      <fieldset disabled={busy || !data.can_review || !current} className="space-y-4">
        <label className="block">Overall recommendation<select className="input-base mt-2" value={recommendation} required onChange={(e) => setRecommendation(e.target.value)}><option value="">Choose a recommendation</option>{form.recommendations.map((r) => <option key={r}>{r}</option>)}</select></label>
        {form.criteria.map((c) => <label className="block" key={c.id}>{c.label}{c.required ? " *" : ""}{c.visibility === "chairs" ? " · Chairs only" : " · May be released to authors"}
          {c.kind === "score" ? <input className="input-base mt-2" type="number" min={c.minimum} max={c.maximum} step="any" required={c.required} value={answers[c.id] ?? ""} onChange={(e) => setAnswers((old) => { const next = { ...old }; if (e.target.value === "") delete next[c.id]; else next[c.id] = Number(e.target.value); return next; })} /> :
            <textarea className="input-base mt-2" required={c.required} maxLength={20000} value={answers[c.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [c.id]: e.target.value })} />}
        </label>)}
        <label className="block">Confidential comments for chairs<textarea className="input-base mt-2" maxLength={20000} value={confidential} onChange={(e) => setConfidential(e.target.value)} /></label>
        <div className="flex flex-wrap gap-3"><button className="btn-secondary" type="button" onClick={() => save(false)}>Save private draft</button><button className="btn-primary">Submit formal review</button></div>
      </fieldset>
    </form>
    <form className="space-y-2 border-t pt-4" onSubmit={async (e) => { e.preventDefault(); if (await act(() => declareOwnConflict(data.assignment_id, conflict))) navigate("/reviewer"); }}>
      <label className="block">Declare a conflict of interest<textarea className="input-base mt-2" required maxLength={4000} value={conflict} disabled={busy} onChange={(e) => setConflict(e.target.value)} /></label>
      <p className="text-sm text-surface-500">This immediately revokes your review assignment. The reason is visible to chairs.</p>
      <button className="btn-secondary" disabled={busy || !conflict.trim()}>Declare conflict and recuse</button>
      <Link className="ml-3 text-primary-600" to="/reviewer">Reviewer workspace</Link>
    </form>
  </section>;
}

function ReviewCard({ review, submissionId }) {
  const [history, setHistory] = useState(null);
  const [error, setError] = useState("");
  async function loadHistory() {
    try { setHistory(await getReviewHistory(submissionId, review.review_id)); }
    catch (err) { setError(errorMessage(err)); }
  }
  return <article className="panel p-5 space-y-3">
    <h3 className="font-semibold">{review.reviewer_id} · {review.state} · Version {review.version}</h3>
    {review.latest_state === "draft" && review.state === "submitted" && <p className="text-sm">A newer private draft exists. This is the earlier submitted version.</p>}
    {review.released_at && <p className="text-sm">Released {new Date(review.released_at).toLocaleString()}</p>}
    {review.assignment_active === false && <p className="text-sm">Historical review · assignment is inactive</p>}
    <Link className="text-primary-600 text-sm" to={`/submissions/${submissionId}?revision=${review.revision_id}`}>View reviewed paper revision</Link>
    {review.recommendation && <p className="font-medium">Recommendation: {review.recommendation}</p>}
    {review.form?.criteria.map((c) => <div key={c.id}><p className="text-sm font-semibold">{c.label}{c.visibility === "chairs" ? " · Chairs only" : ""}</p><p className="whitespace-pre-wrap">{review.answers?.[c.id] ?? "Not answered"}</p></div>)}
    {"confidential_comments" in review && <div><h4 className="font-semibold text-sm">Confidential comments for chairs</h4><p className="whitespace-pre-wrap">{review.confidential_comments || "None"}</p></div>}
    <button className="btn-secondary" onClick={loadHistory}>View permitted review history</button>
    {error && <p role="alert" className="text-danger-600">{error}</p>}
    {history && <div className="text-sm space-y-3">{history.map((v) => <details key={v.version}>
      <summary className="cursor-pointer">Version {v.version} · {v.state} · {new Date(v.created_at).toLocaleString()}{v.recommendation ? ` · ${v.recommendation}` : ""}</summary>
      <div className="space-y-2 mt-2">{v.form.criteria.map((c) => <p key={c.id} className="whitespace-pre-wrap"><strong>{c.label}: </strong>{v.answers[c.id] ?? "Not answered"}</p>)}
        {"confidential_comments" in v && <p className="whitespace-pre-wrap"><strong>Confidential comments: </strong>{v.confidential_comments || "None"}</p>}
      </div>
    </details>)}</div>}
  </article>;
}

function ConflictManagement({ submissionId, refresh, busy, act }) {
  const [conflicts, setConflicts] = useState([]);
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [resolutions, setResolutions] = useState({});
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    getReviewConflicts(submissionId).then((rows) => { if (active) setConflicts(rows); }).catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [submissionId, refresh]);
  return <section className="panel p-5 space-y-4">
    <h3 className="font-semibold">Conflicts of interest · Chairs only</h3>
    {error && <p role="alert" className="text-danger-600">{error}</p>}
    {conflicts.map((c) => <div key={c.conflict_id} className="border-l-2 pl-4 space-y-2"><p>{c.reviewer_id} · {c.resolved_at ? "Resolved" : "Active conflict"}</p><p className="whitespace-pre-wrap text-sm">{c.reason}</p>
      {!c.resolved_at && <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); act(() => resolveReviewConflict(submissionId, c.conflict_id, c.version, resolutions[c.conflict_id])); }}><label className="block">Resolution reason<input className="input-base mt-2" required value={resolutions[c.conflict_id] || ""} maxLength={4000} disabled={busy} onChange={(e) => setResolutions({ ...resolutions, [c.conflict_id]: e.target.value })} /></label><button className="btn-secondary" disabled={busy}>Record resolution</button></form>}
    </div>)}
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act(async () => { await declareReviewConflict(submissionId, reviewer, reason); setReviewer(""); setReason(""); }); }}>
      <label className="block">Reviewer account ID<input className="input-base mt-2" required value={reviewer} disabled={busy} onChange={(e) => setReviewer(e.target.value)} /></label>
      <label className="block">Conflict reason<textarea className="input-base mt-2" required maxLength={4000} value={reason} disabled={busy} onChange={(e) => setReason(e.target.value)} /></label>
      <button className="btn-secondary" disabled={busy || !reason.trim()}>Record conflict and revoke assignment</button>
    </form>
  </section>;
}
