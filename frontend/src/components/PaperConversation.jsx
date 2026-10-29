import { useEffect, useId, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { Link, useSearchParams } from "react-router-dom";
import { createConversation, deleteConversationComment, editConversationComment, errorMessage, getConversation, getDiscussionThread, replyToConversation, resolveConversation } from "../lib/api.js";

export default function PaperConversation({ submissionId, paper, revisions, currentRevisionId, isChair, footer }) {
  const [params] = useSearchParams();
  const { user } = useAuth();
  const [preview, setPreview] = useState(false);
  const detailsParams = new URLSearchParams(params); detailsParams.set("tab", "overview");
  const [threads, setThreads] = useState(null);
  const [legacy, setLegacy] = useState(null);
  const [text, setText] = useState("");
  const [anchor, setAnchor] = useState("");
  const [page, setPage] = useState("");
  const [visibility, setVisibility] = useState("participants");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [filter, setFilter] = useState("all");
  const visibleThreads = threads?.filter((thread) => filter === "all" || thread.resolved === (filter === "resolved"));
  const timeline = [
    ...revisions.filter((revision) => revision.uploaded_at).map((revision) => ({ kind: "revision", id: revision.revision_id, date: revision.uploaded_at, revision })),
    ...(visibleThreads || []).map((thread) => ({ kind: "thread", id: thread.thread_id, date: thread.created_at || thread.comments[0]?.created_at, thread })),
  ].sort((a, b) => (Date.parse(a.date) || 0) - (Date.parse(b.date) || 0) || (a.kind === "revision" && b.kind === "revision" ? a.revision.number - b.revision.number : 0));
  useEffect(() => {
    if (!isChair && visibility === "chairs") { setText(""); setVisibility("participants"); }
  }, [isChair, visibility]);
  useEffect(() => {
    let active = true;
    setError("");
    Promise.all([getConversation(submissionId), getDiscussionThread(submissionId)])
      .then(([t, l]) => { if (active) { setThreads(t); setLegacy(l); } })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [submissionId, refresh]);
  async function act(operation) {
    setBusy(true); setError("");
    try { await operation(); setRefresh((n) => n + 1); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <section className="pf-paper-conversation">
    {paper && <div className="pf-discussion-entry pf-pr-description"><span className="pf-timeline-avatar" aria-hidden="true">{String(paper.authors?.[0]?.name || "P").slice(0, 1).toUpperCase()}</span><section className="pf-pr-description-card" aria-label="Submission description"><header><strong>{paper.authors?.map((author) => author.name).join(", ") || "Paper summary"}</strong><span>submission description</span><Link to={`/submissions/${submissionId}?${detailsParams}`}>Paper details →</Link></header><div>{paper.abstract ? <p>{paper.abstract}</p> : <p>No abstract has been added.</p>}</div></section></div>}

    <div className="pf-pr-discussion-tools"><h2>Discussion</h2>
    {threads?.length > 0 && <div className="pf-discussion-filters" role="group" aria-label="Filter discussions">
      {[["all", "All", threads.length], ["open", "Unresolved", threads.filter((thread) => !thread.resolved).length], ["resolved", "Resolved", threads.filter((thread) => thread.resolved).length]].map(([value, label, count]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}<span className="pf-counter">{count}</span></button>)}
    </div>}</div>
    {error && <div role="alert" className="pf-paper-error">{error} <button type="button" className="btn-secondary" disabled={busy} onClick={() => setRefresh((n) => n + 1)}>Retry conversation</button></div>}
    {threads === null && !error && <p role="status">Loading conversation…</p>}
    {threads?.length === 0 && !legacy?.messages?.length && <div className="pf-conversation-empty"><h3>No discussions yet</h3><p>Start a conversation about the paper or link your feedback to a revision.</p></div>}
    {!error && threads?.length > 0 && visibleThreads.length === 0 && <p className="pf-conversation-empty">No {filter === "open" ? "unresolved" : "resolved"} discussions. <button type="button" className="btn-secondary" onClick={() => setFilter("all")}>Show all discussions</button></p>}
    <div className="pf-discussion-timeline">{timeline.map((entry) => entry.kind === "revision" ? <div className="pf-pr-revision-event" key={`revision:${entry.id}`}><span className="pf-revision-event-mark" aria-hidden="true">↥</span><div><Link to={`/submissions/${submissionId}?tab=files&revision=${encodeURIComponent(entry.id)}`}>Uploaded revision {entry.revision.number}</Link><span>{entry.revision.change_summary || entry.revision.filename}</span><time dateTime={entry.date}>{new Date(entry.date).toLocaleString()}</time></div></div> : <div className="pf-discussion-entry" key={`thread:${entry.id}`}><span className="pf-timeline-avatar" aria-hidden="true">{String(entry.thread.comments[0]?.author_id || "?").slice(0, 1).toUpperCase()}</span>
      <ConversationThread thread={entry.thread} busy={busy} act={act} submissionId={submissionId} revisions={revisions} currentRevisionId={currentRevisionId} compactReplies />
    </div>)}</div>
    {legacy?.messages?.length > 0 && <section className="panel p-5 space-y-3">
      <h3 className="font-semibold">Earlier conversation</h3>
      {legacy.messages.map((m, i) => <div key={i}><p className="text-sm text-surface-500">{m.author} · {new Date(m.timestamp).toLocaleString()}</p><p className="whitespace-pre-wrap">{m.text}</p></div>)}
    </section>}
    <div className="pf-discussion-entry pf-comment-editor-entry"><span className="pf-timeline-avatar" aria-hidden="true">{String(user?.full_name || user?.user_id || "?").slice(0, 1).toUpperCase()}</span>
    <form className="panel pf-conversation-composer" onSubmit={(e) => { e.preventDefault(); act(async () => {
      await createConversation(submissionId, { body: text, revision_id: anchor || null, page_number: anchor && page ? Number(page) : null, visibility });
      setText(""); setPage(""); setPreview(false);
    }); }}>
      <div className="pf-comment-editor-tabs" role="tablist" aria-label="Comment editor" onKeyDown={(event) => {
        if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
          event.preventDefault(); const next = event.key === "Home" ? false : event.key === "End" ? true : !preview;
          setPreview(next); event.currentTarget.querySelectorAll('[role="tab"]')[next ? 1 : 0].focus();
        }
      }}><button type="button" role="tab" id="comment-write-tab" tabIndex={preview ? -1 : 0} aria-selected={!preview} aria-controls="comment-write-panel" onClick={() => setPreview(false)}>Write</button><button type="button" role="tab" id="comment-preview-tab" tabIndex={preview ? 0 : -1} aria-selected={preview} aria-controls="comment-preview-panel" onClick={() => setPreview(true)}>Preview</button></div>
      <div id="comment-write-panel" role="tabpanel" aria-labelledby="comment-write-tab" hidden={preview}><label className="block"><span className="sr-only">Comment</span><textarea placeholder="Leave a comment" className="input-base mt-2" value={text} required maxLength={20000} disabled={busy} onChange={(e) => setText(e.target.value)} /></label></div>
      <div id="comment-preview-panel" role="tabpanel" aria-labelledby="comment-preview-tab" hidden={!preview} className="pf-comment-preview">{text.trim() || "Nothing to preview"}</div>
      <div className="pf-composer-footer"><details className="pf-composer-settings"><summary>Reference and visibility</summary><div className="pf-composer-options"><label className="block">Document reference
        <select className="input-base mt-2" value={anchor} disabled={busy} onChange={(e) => { setAnchor(e.target.value); setPage(""); }}>
          <option value="">General discussion</option>
          {revisions.map((r) => <option value={r.revision_id} key={r.revision_id}>Revision {r.number}{r.revision_id === currentRevisionId ? " (current)" : " (earlier)"}</option>)}
        </select>
      </label>
      {anchor && <label className="block">Page number (optional)<input className="input-base mt-2" type="number" min="1" max="10000" value={page} disabled={busy} onChange={(e) => setPage(e.target.value)} /></label>}
      {isChair && <label className="block">Visibility<select className="input-base mt-2" value={visibility} disabled={busy} onChange={(e) => setVisibility(e.target.value)}><option value="participants">Paper participants</option><option value="chairs">Confidential · chairs only</option></select></label>}
      </div></details>
      <button className="btn-primary" disabled={busy || !text.trim()}>{busy ? "Saving…" : "Post comment"}</button></div>
      {visibility === "chairs" && isChair && <p className="pf-confidential-notice">This discussion will be visible to chairs only.</p>}
    </form>
    </div>
    {footer && <details className="pf-conversation-status"><summary>Paper status and next steps</summary>{footer}</details>}

  </section>;
}

export function ConversationThread({ thread, busy, act, submissionId, revisions, currentRevisionId, compactReplies = false }) {
  const [reply, setReply] = useState("");
  const [parent, setParent] = useState("");
  const [editing, setEditing] = useState(null);
  const [edited, setEdited] = useState("");
  const replyDisclosure = useRef(null);
  const replyId = useId();
  const revision = revisions.find((r) => r.revision_id === thread.revision_id);
  const actions = (c) => <>
    {!c.deleted_at && !thread.resolved && <button className="pf-comment-reply" aria-label="Reply to this comment" disabled={busy} onClick={() => { setParent(c.comment_id); if (replyDisclosure.current) replyDisclosure.current.open = true; document.getElementById(replyId)?.focus(); }}>Reply</button>}

  </>;
  const commentMenu = (c) => ((c.can_edit || c.can_delete) && <details className="pf-comment-more"><summary aria-label="Comment actions">•••</summary><div>    {c.can_edit && <button className="text-primary-600" disabled={busy} onClick={() => { setEditing(c.comment_id); setEdited(c.body); }}>Edit</button>}
    {c.can_delete && <button className="text-danger-600" disabled={busy} onClick={() => act(() => deleteConversationComment(submissionId, thread.thread_id, c.comment_id, c.version))}>Delete</button>}</div></details>);
  return <article className={`panel p-5 space-y-4 pf-conversation-thread ${compactReplies ? "is-pr-thread" : ""} ${thread.resolved ? "is-resolved" : ""}`} aria-label={`${thread.resolved ? "Resolved" : "Unresolved"} discussion${thread.visibility === "chairs" ? " · chairs only" : ""}`}>
    <div className="flex flex-wrap gap-3 items-center justify-between pf-thread-context">
      <p className="text-sm">{thread.visibility === "chairs" ? "Confidential · chairs only · " : ""}{thread.resolved ? "Resolved" : "Unresolved"}
        {thread.revision_id && <> · <Link className="text-primary-600" to={`/submissions/${submissionId}?revision=${encodeURIComponent(thread.revision_id)}&tab=document${thread.page_number ? `&page=${thread.page_number}` : ""}`}>Revision {revision?.number || "unknown"}{thread.page_number ? `, page ${thread.page_number}` : ""}</Link>{thread.revision_id !== currentRevisionId && " · Earlier version"}</>}
      </p>
      {compactReplies && thread.comments.length === 1 && <div className="pf-thread-inline-actions">{actions(thread.comments[0])}</div>}
      {thread.can_resolve && <button className="btn-secondary" disabled={busy} onClick={() => act(() => resolveConversation(submissionId, thread.thread_id, !thread.resolved, Boolean(thread.resolved)))}>{thread.resolved ? "Reopen thread" : "Resolve thread"}</button>}
    </div>
    {thread.comments.map((c) => <div key={c.comment_id} className={`space-y-2 pf-conversation-comment ${c.parent_comment_id ? "is-reply" : ""}`}>
      <div className="pf-comment-byline"><span className="pf-comment-avatar" aria-hidden="true">{String(c.author_id || "?").slice(0, 1).toUpperCase()}</span><strong>{c.author_id}</strong><span className="pf-comment-role">{c.author_role}</span><span className="pf-commented-label">commented</span><time dateTime={c.created_at}>{new Date(c.created_at).toLocaleString()}</time>{c.edited_at && <span>edited</span>}{commentMenu(c)}</div>
      {editing === c.comment_id ? <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); act(async () => { await editConversationComment(submissionId, thread.thread_id, c.comment_id, edited, c.version); setEditing(null); }); }}>
        <label className="block">Edit comment<textarea className="input-base mt-2" required maxLength={20000} value={edited} disabled={busy} onChange={(e) => setEdited(e.target.value)} /></label>
        <button className="btn-primary" disabled={busy || !edited.trim()}>Save comment</button><button className="btn-secondary ml-2" type="button" onClick={() => setEditing(null)}>Cancel</button>
      </form> : <p className="whitespace-pre-wrap">{c.deleted_at ? "Comment removed" : c.body}</p>}
      {(!compactReplies || thread.comments.length > 1) && <div className="pf-comment-actions">{actions(c)}</div>}
    </div>)}
    {!thread.resolved && <details ref={replyDisclosure} open={compactReplies ? undefined : true} className={`pf-thread-reply ${compactReplies ? "is-compact" : ""} ${thread.comments.some((comment) => !comment.deleted_at) ? "has-inline-reply" : ""}`}><summary>Reply to discussion</summary><form className="space-y-2" onSubmit={(e) => { e.preventDefault(); act(async () => { await replyToConversation(submissionId, thread.thread_id, { body: reply, parent_comment_id: parent || null }); setReply(""); setParent(""); }); }}>
      {parent && <p className="text-sm">Replying to a comment <button type="button" className="text-primary-600" onClick={() => setParent("")}>Cancel selection</button></p>}
      <label className="block">Reply<textarea id={replyId} className="input-base mt-2" required maxLength={20000} value={reply} disabled={busy} onChange={(e) => setReply(e.target.value)} /></label>
      <button className="btn-secondary" disabled={busy || !reply.trim()}>Post reply</button>
    </form></details>}
  </article>;
}
