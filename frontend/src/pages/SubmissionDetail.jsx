import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { downloadRevision, errorMessage, getRevisionChecks, getRevisions, getSubmission, getSubmissionWorkflow, recheckRevision, uploadRevision } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { PaperCard } from "./Results.jsx";
import SubmissionWorkflow from "../components/SubmissionWorkflow.jsx";
import PaperConversation from "../components/PaperConversation.jsx";
import PaperActivity from "../components/PaperActivity.jsx";
import FormalReviews from "../components/FormalReviews.jsx";
import RevisionComparison from "../components/RevisionComparison.jsx";
import PaperMetadata from "../components/PaperMetadata.jsx";
import DocumentReview from "../components/DocumentReview.jsx";
import { PaperHeader, PaperSidebar, PaperReadiness, RevisionToolbar } from "../components/PaperWorkspace.jsx";

const labels = { passed: "Passed", passed_with_warnings: "Passed with warnings", failed: "Failed", unable_to_validate: "Unable to validate" };
const date = (value) => new Date(value).toLocaleString();

export default function SubmissionDetail() {
  const { submissionId } = useParams();
  return <Workspace key={submissionId} submissionId={submissionId} />;
}

function Workspace({ submissionId }) {
  const { user, loading: authLoading } = useAuth();
  const [params, setParams] = useSearchParams();
  const [paper, setPaper] = useState(null);
  const [history, setHistory] = useState(null);
  const [checks, setChecks] = useState([]);
  const [runId, setRunId] = useState("");
  const tab = params.get("tab") || "overview";
  const setTab = (nextTab) => setParams((current) => {
    const next = new URLSearchParams(current); next.set("tab", nextTab); return next;
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [loadingChecks, setLoadingChecks] = useState(false);
  const [file, setFile] = useState(null);
  const [summary, setSummary] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [isChair, setIsChair] = useState(false);
  const [workflow, setWorkflow] = useState(null);
  const requestKey = useRef(null);
  const fileInput = useRef(null);
  const selectedId = params.get("revision") || history?.current_revision_id;
  const selected = history?.revisions.find((r) => r.revision_id === selectedId);
  const requestedRun = params.get("run");
  const report = requestedRun ? checks.find((r) => r.run_id === requestedRun) : checks.find((r) => r.run_id === runId) || checks[0];

  useEffect(() => {
    if (!user) return;
    let active = true;
    Promise.all([getSubmission(submissionId), getRevisions(submissionId), getSubmissionWorkflow(submissionId).catch(() => null)])
      .then(([p, h, workflow]) => { if (active) { setPaper(p); setHistory(h); setWorkflow(workflow); setIsChair(Boolean(workflow?.is_chair)); } })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [submissionId, user, refresh]);
  useEffect(() => {
    setChecks([]); setRunId("");
    if (!selectedId || !user) return;
    let active = true;
    setLoadingChecks(true);
    setChecks([]);
    getRevisionChecks(submissionId, selectedId)
      .then((rows) => { if (active) setChecks(rows); })
      .catch((err) => { if (active) setError(errorMessage(err)); })
      .finally(() => { if (active) setLoadingChecks(false); });
    return () => { active = false; };
  }, [submissionId, selectedId, user, refresh]);

  async function upload(event) {
    event.preventDefault();
    if (!file) return;
    setBusy(true); setError("");
    requestKey.current ||= { key: crypto.randomUUID(), parentId: history.current_revision_id };
    try {
      const revision = await uploadRevision(submissionId, file, requestKey.current.parentId, summary, requestKey.current.key);
      setParams({ revision: revision.revision_id, tab: "checks" });
      setFile(null); setSummary(""); requestKey.current = null;
      if (fileInput.current) fileInput.current.value = "";
      setRefresh((n) => n + 1);
    } catch (err) {
      if (err?.response?.status === 409) requestKey.current = null;
      setError(errorMessage(err));
    }
    finally { setBusy(false); }
  }
  async function recheck() {
    setBusy(true); setChecking(true); setError("");
    try { await recheckRevision(submissionId, selectedId); setRefresh((n) => n + 1); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); setChecking(false); }
  }
  async function download() {
    setBusy(true); setError("");
    try { await downloadRevision(submissionId, selectedId, selected.filename); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  if (authLoading) return <p role="status">Loading account…</p>;
  if (!user) return <p><Link className="text-primary-600" to="/login">Sign in</Link> to view this paper.</p>;
  return <div className="pf-paper-workspace">
    {error && <div role="alert" className="panel p-4 text-danger-600">{error} <button className="btn-secondary ml-3" disabled={busy} onClick={() => { setError(""); setRefresh((n) => n + 1); }}>Reload</button></div>}
    {!paper || !history ? !error && <p role="status">Loading submission…</p> : <>
      <PaperHeader paper={paper} currentRevision={history.revisions.find((revision) => revision.revision_id === history.current_revision_id)} canUpload={history.can_upload_revision} onNavigate={setTab} />
      <nav className="pf-paper-tabs" aria-label="Submission sections">
        {[["overview", "Overview"], ["conversation", "Conversation"], ["checks", "Formatting checks"], ["document", "Document"], ["files", "Files and revisions"], ["compare", "Compare revisions"], ["reviews", "Reviews"], ["activity", "Activity"]].map(([id, label]) => {
          const next = new URLSearchParams(params); next.set("tab", id);
          return <Link key={id} to={`?${next}`} aria-current={tab === id ? "page" : undefined}>{label}</Link>;
        })}
        <Link to={`/issues/${submissionId}`}>Issues ↗</Link>
      </nav>
      {history.revisions.length > 0 && tab !== "compare" && <RevisionToolbar history={history} selected={selected} selectedId={selectedId} busy={busy}
        onChange={(id) => setParams((current) => { const next = new URLSearchParams(current); next.set("revision", id); next.delete("run"); next.delete("page"); return next; })}
        onCurrent={() => setParams((current) => { const next = new URLSearchParams(current); next.set("revision", history.current_revision_id); next.delete("run"); next.delete("page"); return next; })} />}
      <div className={`pf-paper-layout ${!["overview", "conversation"].includes(tab) ? "pf-paper-layout--wide" : ""}`}>
      <div className="pf-paper-main">
      {tab === "overview" && <PaperReadiness workflow={workflow} onRetry={() => setRefresh((n) => n + 1)} />}
      {tab === "overview" && paper.abstract && <section className="panel p-5 space-y-3"><h2>Abstract</h2><p className="whitespace-pre-wrap">{paper.abstract}</p></section>}
      {tab === "overview" && selected && <section className="panel p-5 space-y-3">
        <h2>Revision {selected.number} summary</h2><p>{selected.change_summary || "No change summary provided."}</p>
        <p className="pf-paper-muted">Uploaded {date(selected.uploaded_at)} by {selected.uploaded_by || "Unknown"}. Formatting: {labels[selected.latest_check?.status] || "Not checked"}.</p>
      </section>}
      {tab === "conversation" && <PaperConversation submissionId={submissionId} revisions={history.revisions} currentRevisionId={history.current_revision_id} isChair={isChair} />}
      {tab === "activity" && <PaperActivity submissionId={submissionId} />}
      {tab === "reviews" && <FormalReviews submissionId={submissionId} revisionId={selectedId} onChanged={() => setRefresh((n) => n + 1)} />}
      {tab === "compare" && <RevisionComparison submissionId={submissionId} revisions={history.revisions} selectedId={selectedId} />}
      {tab === "overview" && <SubmissionWorkflow key={`${paper.metadata_version}:${paper.status}`} submissionId={submissionId} reloadKey={refresh} onChanged={() => setRefresh((n) => n + 1)} onChairLoaded={setIsChair} />}
      {tab === "overview" && <PaperMetadata key={paper.metadata_version} submissionId={submissionId} currentRevisionId={history.current_revision_id} onChanged={() => setRefresh((n) => n + 1)} />}
      {history.revisions.length === 0 ? <p className="panel p-5">This legacy paper has no revision history yet. A chair must reconcile its original file and template before revision uploads are enabled.</p> : <>
        {!selected ? <p role="alert">This revision is unavailable.</p> : <>
          {tab === "document" && <DocumentReview submissionId={submissionId} revision={selected} revisions={history.revisions} currentRevisionId={history.current_revision_id} isChair={isChair}
            layout={report?.revision_id === selectedId ? report.assessment?.facts?.layout : null} pageNumber={params.get("page")}
            onPageChange={(page) => setParams((current) => { const next = new URLSearchParams(current); next.set("page", page); return next; }, { replace: true })} />}

          {tab === "checks" && <section className="space-y-4">
            <div className="flex flex-wrap gap-3 items-center">
              <h2 className="text-lg font-semibold">Formatting checks · Revision {selected.number}</h2>
              {history.can_recheck && <button className="btn-secondary" disabled={busy} onClick={recheck}>{checking ? "Checking…" : "Run checks again"}</button>}
            </div>
            {loadingChecks ? <p role="status">Loading reports…</p> : report ? <>
              <label className="block">Saved report
                <select className="input-base mt-2" value={report.run_id} onChange={(e) => { setRunId(e.target.value); setParams((current) => { const next = new URLSearchParams(current); next.set("run", e.target.value); return next; }); }}>
                  {checks.map((r) => <option key={r.run_id} value={r.run_id}>Run {r.sequence} · {date(r.created_at)} · {labels[r.status]}</option>)}
                </select>
              </label>
              <p className="text-sm">{labels[report.status]} · Template {selected.template_id}</p>
              {report.error && <p role="alert" className="text-danger-600">{report.error}</p>}
              {report.assessment && <PaperCard key={report.run_id} paper={report.assessment} defaultOpen validationLabel={labels[report.status]} />}
              {report.issues.length > 0 && <p><Link className="text-primary-600" to={`/issues/${submissionId}`}>{report.issues.length} tracked issues from this report</Link></p>}
            </> : <p>{requestedRun ? <>The requested saved report is unavailable for this revision. <Link className="text-primary-600" to={`/submissions/${submissionId}?revision=${selectedId}&tab=checks`}>View latest saved report</Link></> : "No saved formatting report for this revision."}</p>}
          </section>}
          {tab === "files" && <section className="panel p-5 space-y-4">
            <h2 className="text-lg font-semibold">Revision {selected.number} file</h2>
            <button className="btn-secondary" disabled={busy} onClick={download}>Download {selected.filename}</button>
            <p className="text-sm">{selected.size_bytes.toLocaleString()} bytes · Uploaded {date(selected.uploaded_at)}</p>
            <details><summary className="cursor-pointer">File integrity</summary><p className="font-mono break-all text-xs mt-2">SHA-256: {selected.sha256}</p></details>
            {history.can_upload_revision && <form className="space-y-4 border-t pt-4" onSubmit={upload}>
              <h3 className="font-semibold">Upload revision {Math.max(0, ...history.revisions.map((revision) => revision.number)) + 1}</h3>
              <p className="text-sm text-surface-500">Earlier files and reports stay available. Revisions use the submission’s pinned template.</p>
              <label className="block">Revised paper
                <input ref={fileInput} className="block mt-2" type="file" accept=".pdf,.docx,.tex,.latex" required disabled={busy}
                  onChange={(e) => { setFile(e.target.files?.[0] || null); requestKey.current = null; }} />
              </label>
              <label className="block">Change summary
                <textarea className="input-base mt-2" value={summary} maxLength={4000} disabled={busy}
                  onChange={(e) => { setSummary(e.target.value); requestKey.current = null; }} />
              </label>
              <button className="btn-primary" disabled={busy || !file}>{busy ? "Uploading and checking…" : "Upload new revision"}</button>
            </form>}
          </section>}
        </>}
      </>}
      </div>
      {["overview", "conversation"].includes(tab) && <PaperSidebar paper={paper} selected={selected} workflow={workflow} onNavigate={setTab} />}
      </div>
    </>}
  </div>;
}
