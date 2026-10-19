import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createConversation, deleteConversationComment, editConversationComment, errorMessage, getConversation, getDiscussionThread, replyToConversation, resolveConversation } from "../lib/api.js";

export default function PaperConversation({ submissionId, revisions, currentRevisionId, isChair }) {
  const [threads, setThreads] = useState(null);
  const [legacy, setLegacy] = useState(null);
  const [text, setText] = useState("");
  const [anchor, setAnchor] = useState("");
  const [page, setPage] = useState("");
  const [visibility, setVisibility] = useState("participants");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
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
  return <section className="space-y-4 pf-paper-conversation">
    <div className="pf-conversation-heading"><div><h2 className="text-lg font-semibold">Conversation</h2><p>Discuss the paper, follow up on feedback, and keep revision context.</p></div>{threads && <span className="pf-count">{threads.length} threads</span>}</div>
    {error && <div role="alert" className="pf-paper-error">{error} <button type="button" className="btn-secondary" disabled={busy} onClick={() => setRefresh((n) => n + 1)}>Retry conversation</button></div>}
    {threads === null && !error && <p role="status">Loading conversation…</p>}
    {threads?.length === 0 && !legacy?.messages?.length && <div className="pf-conversation-empty"><h3>No discussions yet</h3><p>Start a conversation about the paper or link your feedback to a revision.</p></div>}
    {threads?.map((thread) => <ConversationThread key={thread.thread_id} thread={thread} busy={busy} act={act} submissionId={submissionId} revisions={revisions} currentRevisionId={currentRevisionId} />)}
    {legacy?.messages?.length > 0 && <section className="panel p-5 space-y-3">
      <h3 className="font-semibold">Earlier conversation</h3>
      {legacy.messages.map((m, i) => <div key={i}><p className="text-sm text-surface-500">{m.author} · {new Date(m.timestamp).toLocaleString()}</p><p className="whitespace-pre-wrap">{m.text}</p></div>)}
    </section>}
    <form className="panel p-5 space-y-4 pf-conversation-composer" onSubmit={(e) => { e.preventDefault(); act(async () => {
      await createConversation(submissionId, { body: text, revision_id: anchor || null, page_number: anchor && page ? Number(page) : null, visibility });
      setText(""); setPage("");
    }); }}>
      <h3 className="font-semibold">Start a discussion</h3>
      <p className="pf-paper-muted">General discussion is separate from formal reviews. Revision references remain attached to the original upload.</p>
      <label className="block">Comment<textarea className="input-base mt-2" value={text} required maxLength={20000} disabled={busy} onChange={(e) => setText(e.target.value)} /></label>
      <label className="block">Document reference
        <select className="input-base mt-2" value={anchor} disabled={busy} onChange={(e) => { setAnchor(e.target.value); setPage(""); }}>
          <option value="">General discussion</option>
          {revisions.map((r) => <option value={r.revision_id} key={r.revision_id}>Revision {r.number}{r.revision_id === currentRevisionId ? " (current)" : " (earlier)"}</option>)}
        </select>
      </label>
      {anchor && <label className="block">Page number (optional)<input className="input-base mt-2" type="number" min="1" max="10000" value={page} disabled={busy} onChange={(e) => setPage(e.target.value)} /></label>}
      {isChair && <label className="block">Visibility<select className="input-base mt-2" value={visibility} disabled={busy} onChange={(e) => setVisibility(e.target.value)}><option value="participants">Paper participants</option><option value="chairs">Confidential · chairs only</option></select></label>}
      {visibility === "chairs" && isChair && <p className="pf-confidential-notice">This discussion will be visible to chairs only.</p>}
      <button className="btn-primary" disabled={busy || !text.trim()}>{busy ? "Saving…" : "Post comment"}</button>
    </form>
  </section>;
}

export function ConversationThread({ thread, busy, act, submissionId, revisions, currentRevisionId }) {
  const [reply, setReply] = useState("");
  const [parent, setParent] = useState("");
  const [editing, setEditing] = useState(null);
  const [edited, setEdited] = useState("");
  const revision = revisions.find((r) => r.revision_id === thread.revision_id);
  return <article className={`panel p-5 space-y-4 pf-conversation-thread ${thread.resolved ? "is-resolved" : ""}`} aria-label={`${thread.resolved ? "Resolved" : "Unresolved"} discussion${thread.visibility === "chairs" ? " · chairs only" : ""}`}>
    <div className="flex flex-wrap gap-3 items-center justify-between">
      <p className="text-sm">{thread.visibility === "chairs" ? "Confidential · chairs only · " : ""}{thread.resolved ? "Resolved" : "Unresolved"}
        {thread.revision_id && <> · <Link className="text-primary-600" to={`/submissions/${submissionId}?revision=${encodeURIComponent(thread.revision_id)}&tab=document${thread.page_number ? `&page=${thread.page_number}` : ""}`}>Revision {revision?.number || "unknown"}{thread.page_number ? `, page ${thread.page_number}` : ""}</Link>{thread.revision_id !== currentRevisionId && " · Earlier version"}</>}
      </p>
      {thread.can_resolve && <button className="btn-secondary" disabled={busy} onClick={() => act(() => resolveConversation(submissionId, thread.thread_id, !thread.resolved, Boolean(thread.resolved)))}>{thread.resolved ? "Reopen thread" : "Resolve thread"}</button>}
    </div>
    {thread.comments.map((c) => <div key={c.comment_id} className={`space-y-2 pf-conversation-comment ${c.parent_comment_id ? "is-reply" : ""}`}>
      <div className="pf-comment-byline"><span className="pf-comment-avatar" aria-hidden="true">{String(c.author_id || "?").slice(0, 1).toUpperCase()}</span><strong>{c.author_id}</strong><span className="pf-comment-role">{c.author_role}</span><time dateTime={c.created_at}>{new Date(c.created_at).toLocaleString()}</time>{c.edited_at && <span>edited</span>}</div>
      {editing === c.comment_id ? <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); act(async () => { await editConversationComment(submissionId, thread.thread_id, c.comment_id, edited, c.version); setEditing(null); }); }}>
        <label className="block">Edit comment<textarea className="input-base mt-2" required maxLength={20000} value={edited} disabled={busy} onChange={(e) => setEdited(e.target.value)} /></label>
        <button className="btn-primary" disabled={busy || !edited.trim()}>Save comment</button><button className="btn-secondary ml-2" type="button" onClick={() => setEditing(null)}>Cancel</button>
      </form> : <p className="whitespace-pre-wrap">{c.deleted_at ? "Comment removed" : c.body}</p>}
      <div className="flex flex-wrap gap-3 text-sm">
        {!c.deleted_at && !thread.resolved && <button className="text-primary-600" disabled={busy} onClick={() => setParent(c.comment_id)}>Reply to this comment</button>}
        {c.can_edit && <button className="text-primary-600" disabled={busy} onClick={() => { setEditing(c.comment_id); setEdited(c.body); }}>Edit</button>}
        {c.can_delete && <button className="text-danger-600" disabled={busy} onClick={() => act(() => deleteConversationComment(submissionId, thread.thread_id, c.comment_id, c.version))}>Delete</button>}
      </div>
    </div>)}
    {!thread.resolved && <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); act(async () => { await replyToConversation(submissionId, thread.thread_id, { body: reply, parent_comment_id: parent || null }); setReply(""); setParent(""); }); }}>
      {parent && <p className="text-sm">Replying to a comment <button type="button" className="text-primary-600" onClick={() => setParent("")}>Cancel selection</button></p>}
      <label className="block">Reply<textarea className="input-base mt-2" required maxLength={20000} value={reply} disabled={busy} onChange={(e) => setReply(e.target.value)} /></label>
      <button className="btn-secondary" disabled={busy || !reply.trim()}>Post reply</button>
    </form>}
  </article>;
}
