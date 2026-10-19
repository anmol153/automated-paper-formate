import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { createConversation, downloadRevision, errorMessage, getConversation, getRevisionPreview } from "../lib/api.js";
import { ConversationThread } from "./PaperConversation.jsx";

const MAX_PREVIEW_BYTES = 25 * 1024 * 1024;

export default function DocumentReview(props) {
  // A draft and a blob belong to exactly one immutable revision.
  return <RevisionDocument key={`${props.submissionId}:${props.revision.revision_id}:${Boolean(props.isChair)}`} {...props} />;
}

function RevisionDocument({ submissionId, revision, revisions, currentRevisionId, isChair, layout, pageNumber, onPageChange }) {
  const [fileUrl, setFileUrl] = useState("");
  const [pdfPages, setPdfPages] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewAttempt, setPreviewAttempt] = useState(0);
  const [threads, setThreads] = useState(null);
  const [threadError, setThreadError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState({});
  const [copyStatus, setCopyStatus] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const mounted = useRef(false);
  const isPdf = /\.pdf$/i.test(revision.filename);
  const withinLimit = revision.size_bytes <= MAX_PREVIEW_BYTES;
  const savedPages = layout?.page_count_exact && Number.isInteger(layout.page_count) && layout.page_count > 0 ? layout.page_count : null;
  const exactPages = pdfPages || savedPages;
  const pageLimit = Math.min(exactPages || 10000, 10000);
  const rawPage = pageNumber ?? "1";
  const page = /^\d+$/.test(String(rawPage)) && Number(rawPage) >= 1 && Number(rawPage) <= pageLimit ? Number(rawPage) : null;
  const draft = drafts[page] || { body: "", visibility: "participants" };
  const updateDraft = (patch) => setDrafts((current) => ({ ...current, [page]: { ...draft, ...patch } }));
  const pageThreads = threads?.filter((thread) => thread.revision_id === revision.revision_id && thread.page_number === page) || [];
  const anchorUrl = page ? new URL(`/submissions/${encodeURIComponent(submissionId)}?tab=document&revision=${encodeURIComponent(revision.revision_id)}&page=${page}`, window.location.origin).href : "";

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (!isPdf || !withinLimit) return;
    let active = true;
    let objectUrl;
    const controller = new AbortController();
    setLoadingPreview(true); setPreviewError(""); setFileUrl("");
    getRevisionPreview(submissionId, revision.revision_id, controller.signal).then(({ data, pageCount }) => {
      if (!active) return;
      if (typeof URL.createObjectURL !== "function") throw new Error("This browser cannot display an embedded PDF. Download the original file instead.");
      const blob = new Blob([data], { type: "application/pdf" });
      if (blob.size > MAX_PREVIEW_BYTES) throw new Error("PDF preview is limited to 25 MB. Download the original file instead.");
      objectUrl = URL.createObjectURL(blob);
      setPdfPages(pageCount); setFileUrl(objectUrl);
    }).catch((err) => { if (active && !controller.signal.aborted) setPreviewError(errorMessage(err)); })
      .finally(() => { if (active) setLoadingPreview(false); });
    return () => { active = false; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [submissionId, revision.revision_id, isPdf, withinLimit, previewAttempt]);

  useEffect(() => {
    let active = true;
    setThreadError(""); setThreads(null);
    getConversation(submissionId).then((rows) => { if (active) setThreads(rows); })
      .catch((err) => { if (active) setThreadError(errorMessage(err)); });
    return () => { active = false; };
  }, [submissionId, refresh]);

  async function act(operation) {
    setBusy(true); setThreadError("");
    try { await operation(); if (mounted.current) setRefresh((value) => value + 1); }
    catch (err) { if (mounted.current) setThreadError(errorMessage(err)); }
    finally { if (mounted.current) setBusy(false); }
  }
  const changePage = (value) => { setCopyStatus(""); onPageChange(value); };

  return <section className="space-y-4" aria-label="Document review">
    <header className="panel p-5 space-y-3">
      <h2 className="text-lg font-semibold">Document · Revision {revision.number}</h2>
      <p className="break-all">{revision.filename}</p>
      {revision.revision_id !== currentRevisionId && <p>You are reviewing an earlier version. Comments here remain on revision {revision.number}.</p>}
      <div className="flex flex-wrap gap-3 items-end">
        <label className="block">Comment page{exactPages ? ` (1–${exactPages})` : ""}
          <input className="input-base mt-1 w-28" type="number" min="1" max={pageLimit} step="1" value={rawPage} disabled={busy} onChange={(event) => changePage(event.target.value)} />
        </label>
        <button className="btn-secondary" disabled={busy || !page || page <= 1} onClick={() => changePage(String(page - 1))}>Previous page</button>
        <button className="btn-secondary" disabled={busy || !page || page >= pageLimit} onClick={() => changePage(String(page + 1))}>Next page</button>
        <button className="btn-secondary" disabled={!page} onClick={async () => {
          try { await navigator.clipboard.writeText(anchorUrl); setCopyStatus("Link copied. It opens this revision and page for authorized participants."); }
          catch { setCopyStatus("Copy the page link from the field below."); }
        }}>Copy page link</button>
        <button className="btn-secondary" disabled={busy} onClick={async () => {
          setBusy(true); setDownloadError("");
          try { await downloadRevision(submissionId, revision.revision_id, revision.filename); }
          catch (err) { if (mounted.current) setDownloadError(errorMessage(err)); }
          finally { if (mounted.current) setBusy(false); }
        }}>Download original</button>
      </div>
      {!page && <p role="alert">The requested page is invalid or outside this document. Choose a page from 1 to {pageLimit}; comments have not been moved to another page.</p>}
      {!exactPages && <p className="text-sm text-surface-500">An exact page count is not available yet. Check the page number against your document; source-file page estimates are not used as exact limits.</p>}
      {copyStatus && <div><p role="status">{copyStatus}</p><label className="block">Page link<input className="input-base w-full" readOnly value={anchorUrl} onFocus={(event) => event.target.select()} /></label></div>}
      {downloadError && <p role="alert" className="text-danger-600">{downloadError}</p>}
      <p className="text-sm text-surface-500">Use Comment page to choose where your comment belongs. Scrolling inside the PDF does not change that selection. Unsent drafts are kept separately for each page while you stay in this Document tab.</p>
    </header>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]">
      <div className="panel p-3 min-w-0">
        {!isPdf ? <p>Inline preview supports PDF files. Download this DOCX or LaTeX source to review it, or ask the author to upload a PDF revision. You can still record revision- and page-linked feedback.</p> : !withinLimit ? <p>This file is larger than the 25 MB preview limit. Download the original to review it.</p> : loadingPreview ? <p role="status">Loading protected PDF preview…</p> : previewError ? <div className="space-y-3"><p role="alert" className="text-danger-600">{previewError}</p><button className="btn-secondary" onClick={() => setPreviewAttempt((value) => value + 1)}>Retry PDF preview</button></div> : fileUrl && page && <>
          <iframe key={`${fileUrl}:${page}`} title={`Paper revision ${revision.number}, page ${page}`} src={`${fileUrl}#page=${page}`} className="w-full h-[75vh] min-h-[420px] border-0" />
          <p className="text-sm mt-2">If your browser does not show the PDF or honor its page link, use Download original. No external document viewer receives this paper.</p>
        </>}
      </div>
      <aside className="space-y-4 min-w-0" aria-label="Page discussion">
        <h3 className="text-lg font-semibold">Revision {revision.number}{page ? ` · Page ${page}` : ""} comments</h3>
        {threadError && <p role="alert" className="text-danger-600">{threadError} <button className="btn-secondary" disabled={busy} onClick={() => setRefresh((value) => value + 1)}>Reload page discussion</button></p>}
        {threads === null && !threadError && <p role="status">Loading page discussion…</p>}
        {page && threads !== null && pageThreads.length === 0 && <p>No comments on this page yet.</p>}
        {page && pageThreads.map((thread) => <ConversationThread key={thread.thread_id} thread={thread} busy={busy} act={act} submissionId={submissionId} revisions={revisions} currentRevisionId={currentRevisionId} />)}
        <form className="panel p-5 space-y-3" onSubmit={(event) => {
          event.preventDefault();
          if (!page || !draft.body.trim() || threads === null || busy || (draft.visibility === "chairs" && !isChair)) return;
          const targetPage = page;
          const payload = { body: draft.body, visibility: draft.visibility, revision_id: revision.revision_id, page_number: targetPage };
          act(async () => {
            await createConversation(submissionId, payload);
            if (mounted.current) setDrafts((current) => ({ ...current, [targetPage]: { body: "", visibility: "participants" } }));
          });
        }}>
          <label className="block">Comment on revision {revision.number}{page ? `, page ${page}` : ""}<textarea className="input-base mt-1" required maxLength={20000} disabled={busy || !page || threads === null} value={draft.body} onChange={(event) => updateDraft({ body: event.target.value })} /></label>
          {isChair && <label className="block">Comment visibility<select className="input-base mt-1" disabled={busy || !page} value={draft.visibility} onChange={(event) => updateDraft({ visibility: event.target.value })}><option value="participants">Paper participants</option><option value="chairs">Confidential · chairs only</option></select></label>}
          <button className="btn-primary" disabled={busy || !page || threads === null || !draft.body.trim()}>{busy ? "Saving…" : "Post page comment"}</button>
        </form>
        <Link className="text-primary-600" to={`/submissions/${submissionId}?tab=conversation`}>View all permitted discussions</Link>
      </aside>
    </div>
  </section>;
}
