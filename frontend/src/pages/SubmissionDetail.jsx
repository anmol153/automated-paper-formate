import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { downloadRevision, errorMessage, getRevisionChecks, getRevisions, getSubmission, getSubmissionWorkflow, recheckRevision, uploadRevision } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import PaperChecks from "../components/PaperChecks.jsx";
import SubmissionWorkflow from "../components/SubmissionWorkflow.jsx";
import PaperConversation from "../components/PaperConversation.jsx";
import PaperActivity from "../components/PaperActivity.jsx";
import FormalReviews from "../components/FormalReviews.jsx";
import RevisionComparison from "../components/RevisionComparison.jsx";
import PaperMetadata from "../components/PaperMetadata.jsx";
import DocumentReview from "../components/DocumentReview.jsx";
import { PaperHeader, PaperNavigation, PaperSidebar, PaperReadiness, RevisionToolbar } from "../components/PaperWorkspace.jsx";
import StateBadge from "../components/ui/StateBadge.jsx";
import Button from "../components/ui/Button.jsx";
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
  const tab = params.get("tab") || "conversation";
  const setTab = (nextTab) => setParams((current) => {
    const next = new URLSearchParams(current); next.set("tab", nextTab); return next;
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [loadingChecks, setLoadingChecks] = useState(false);
  const [checksError, setChecksError] = useState("");
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
    setChecks([]); setRunId(""); setChecksError("");
    if (!selectedId || !user) return;
    let active = true;
    setLoadingChecks(true);
    setChecks([]);
    getRevisionChecks(submissionId, selectedId)
      .then((rows) => { if (active) setChecks(rows); })
      .catch((err) => { if (active) setChecksError(errorMessage(err)); })
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
      <PaperHeader paper={paper} revisionCount={history.revisions.length} currentRevision={history.revisions.find((revision) => revision.revision_id === history.current_revision_id)} canUpload={history.can_upload_revision} onNavigate={setTab} />
      <PaperNavigation params={params} tab={tab} revisionCount={history.revisions.length} submissionId={submissionId} />
      {history.revisions.length > 0 && tab !== "compare" && <RevisionToolbar history={history} selected={selected} selectedId={selectedId} busy={busy}
        onChange={(id) => setParams((current) => { const next = new URLSearchParams(current); next.set("revision", id); next.delete("run"); next.delete("page"); return next; })}
        onCurrent={() => setParams((current) => { const next = new URLSearchParams(current); next.set("revision", history.current_revision_id); next.delete("run"); next.delete("page"); return next; })} />}
      <div className={`pf-paper-layout ${!["overview", "conversation", "reviews"].includes(tab) ? "pf-paper-layout--wide" : ""}`}>
      <div className="pf-paper-main">
      {tab === "overview" && <PaperReadiness workflow={workflow} onRetry={() => setRefresh((n) => n + 1)} />}
      {tab === "overview" && paper.abstract && <section className="panel p-5 space-y-3"><h2>Abstract</h2><p className="whitespace-pre-wrap">{paper.abstract}</p></section>}
      {tab === "overview" && selected && <section className="panel p-5 space-y-3">
        <div className="pf-revision-summary-heading"><h2>Revision {selected.number} summary</h2><span className="pf-paper-context-label">{selectedId === history.current_revision_id ? "Current upload" : "Earlier upload"}</span></div><p>{selected.change_summary || "No change summary provided."}</p>
        <p className="pf-paper-muted">Uploaded <time dateTime={selected.uploaded_at}>{date(selected.uploaded_at)}</time> by {selected.uploaded_by || "Unknown"}. Formatting: {labels[selected.latest_check?.status] || "Not checked"}.</p>
      </section>}
      {tab === "conversation" && <PaperConversation submissionId={submissionId} paper={paper} revisions={history.revisions} currentRevisionId={history.current_revision_id} isChair={isChair}
        footer={<div className="pf-pr-review-status"><PaperReadiness compact workflow={workflow} onRetry={() => setRefresh((n) => n + 1)} /><div className="pf-pr-review-links"><Link to={`?${new URLSearchParams({ ...Object.fromEntries(params), tab: "checks" })}`}>View formatting checks</Link><Link to={`?${new URLSearchParams({ ...Object.fromEntries(params), tab: "reviews" })}`}>View formal reviews</Link><Link to={`?${new URLSearchParams({ ...Object.fromEntries(params), tab: "overview" })}`}>Manage submission</Link></div></div>} />}
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

          {tab === "checks" && <PaperChecks submissionId={submissionId} revision={selected} runs={checks} report={report} requestedRun={requestedRun}
            loading={loadingChecks} error={checksError} busy={busy} checking={checking} canRecheck={history.can_recheck} onRecheck={recheck}
            onRetry={() => setRefresh((n) => n + 1)} onRunChange={(id) => { setRunId(id); setParams((current) => { const next = new URLSearchParams(current); next.set("run", id); return next; }); }} />}
          {tab === "files" && <section className="pf-revision-workspace" aria-label="Paper files and revision history">
            <div className="pf-revision-page-heading"><div><p className="pf-paper-eyebrow">IMMUTABLE UPLOAD HISTORY</p><h2>Files and revisions</h2><p>Each upload is preserved with its own formatting report and review context.</p></div><span className="pf-count">{history.revisions.length} {history.revisions.length === 1 ? "revision" : "revisions"}</span></div>
            <div className="pf-revision-list" aria-label="Revision history">{[...history.revisions].sort((a, b) => b.number - a.number).map((revision) => {
              const isCurrent = revision.revision_id === history.current_revision_id;
              const isSelected = revision.revision_id === selectedId;
              const revisionLink = `/submissions/${submissionId}?tab=files&revision=${encodeURIComponent(revision.revision_id)}`;
              return <article className={`pf-revision-row${isSelected ? " is-selected" : ""}`} key={revision.revision_id}>
                <span className={`pf-revision-row-mark${isCurrent ? " is-current" : ""}`} aria-hidden="true">{isCurrent ? "●" : "○"}</span>
                <div className="pf-revision-row-content"><div className="pf-revision-row-title"><Link to={revisionLink}>Revision {revision.number}</Link>{isCurrent && <span className="pf-revision-current-label">Current</span>}{isSelected && <span className="pf-revision-selected-label">Viewing</span>}</div>
                  <strong className="pf-revision-row-filename">{revision.filename}</strong>
                  <p>{revision.change_summary || (revision.number === 1 ? "Initial submission" : "No change summary provided.")}</p>
                  <div className="pf-revision-row-meta"><span>Uploaded by {revision.uploaded_by || "Unknown"}</span><time dateTime={revision.uploaded_at}>{date(revision.uploaded_at)}</time>{Number.isFinite(revision.size_bytes) && <span>{revision.size_bytes.toLocaleString()} bytes</span>}</div>
                </div>
                <div className="pf-revision-row-status"><StateBadge status={revision.latest_check?.status} label={revision.latest_check ? undefined : "Not checked"} /><div><Link to={`/submissions/${submissionId}?tab=document&revision=${encodeURIComponent(revision.revision_id)}`}>Document</Link><Link to={`/submissions/${submissionId}?tab=checks&revision=${encodeURIComponent(revision.revision_id)}`}>Checks</Link></div></div>
              </article>;
            })}</div>
            <section className="pf-revision-file-detail" aria-label={`Selected revision ${selected.number} file details`}>
              <div className="pf-revision-file-heading"><div><p className="pf-paper-eyebrow">SELECTED SNAPSHOT</p><h3>Revision {selected.number} · {selected.filename}</h3><p>{Number.isFinite(selected.size_bytes) ? `${selected.size_bytes.toLocaleString()} bytes · ` : ""}Uploaded {date(selected.uploaded_at)}</p></div><Button variant="primary" disabled={busy} onClick={download}>Download file</Button></div>
              <details className="pf-revision-integrity"><summary>File integrity</summary><code>SHA-256: {selected.sha256 || "Not available"}</code></details>
            </section>
            {history.can_upload_revision && <form className="pf-revision-upload" onSubmit={upload}>
              <div><p className="pf-paper-eyebrow">AUTHOR ACTION</p><h3>Upload a new revision</h3><p>Earlier files and reports stay available. New revisions use the submission’s pinned template.</p></div>
              <label className="pf-revision-upload-file">Revised paper<input ref={fileInput} type="file" accept=".pdf,.docx,.tex,.latex" required disabled={busy}
                  onChange={(e) => { setFile(e.target.files?.[0] || null); requestKey.current = null; }} /><span>PDF, DOCX or LaTeX source</span></label>
              <label className="pf-revision-upload-summary">Change summary<textarea className="input-base" value={summary} maxLength={4000} disabled={busy} placeholder="Describe what changed in this revision"
                  onChange={(e) => { setSummary(e.target.value); requestKey.current = null; }} /></label>
              <div className="pf-revision-upload-actions"><span>{file ? file.name : "A new immutable snapshot will be added to the history."}</span><button className="btn-primary" disabled={busy || !file}>{busy ? "Uploading and checking…" : "Upload new revision"}</button></div>
            </form>}
          </section>}
        </>}
      </>}
      </div>
      {["overview", "conversation", "reviews"].includes(tab) && <PaperSidebar paper={paper} selected={selected} workflow={workflow} onNavigate={setTab} />}
      </div>
    </>}
  </div>;
}
