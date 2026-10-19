import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage, getPaperMetadata, getPaperMetadataHistory, savePaperMetadata } from "../lib/api.js";
import PaperMetadataFields, { metadataFields } from "./PaperMetadataFields.jsx";

export default function PaperMetadata({ submissionId, currentRevisionId, onChanged }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setError("");
    getPaperMetadata(submissionId).then((next) => { if (active) { setData(next); setForm(metadataFields(next.metadata)); } })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [submissionId, refresh, currentRevisionId]);
  if (!data) return error ? <p role="alert">{error} <button type="button" className="btn-secondary" onClick={() => setRefresh((n) => n + 1)}>Reload paper details</button></p> : <p role="status">Loading paper details…</p>;
  if (!data.enabled) return null;
  return <section className="panel p-5 space-y-4 pf-paper-metadata" aria-label="Paper metadata">
    <h2 className="font-semibold">Paper details · #{data.paper_number}</h2>
    <p className="text-sm text-surface-500">These submission details are separate from the metadata extracted from each uploaded file. Author names do not grant account access.</p>
    {error && <p role="alert" className="text-danger-600">{error} <button type="button" className="btn-secondary" disabled={busy} onClick={() => { setError(""); setRefresh((n) => n + 1); }}>Reload paper details</button></p>}
    {notice && <p role="status">{notice}</p>}
    {data.can_edit ? <details className="pf-paper-metadata-editor"><summary>Edit paper details</summary><form className="space-y-4" onSubmit={async (event) => {
      event.preventDefault(); setBusy(true); setError(""); setNotice("");
      try { await savePaperMetadata(submissionId, { ...form, expected_version: data.metadata.version, expected_revision_id: currentRevisionId }); setHistory([]); setHistoryLoaded(false); setRefresh((n) => n + 1); setNotice("Paper details saved."); onChanged(); }
      catch (err) { setError(errorMessage(err)); }
      finally { setBusy(false); }
    }}>
      <PaperMetadataFields value={form} onChange={setForm} tracks={data.tracks} disabled={busy} />
      <button className="btn-secondary" disabled={busy}>{busy ? "Saving…" : "Save paper details"}</button>
    </form></details> : <div className="space-y-2">
      <p>{data.metadata.title || "No declared title"}</p><p className="whitespace-pre-wrap">{data.metadata.abstract || "No declared abstract"}</p>
      <ul>{data.metadata.authors.map((author, index) => <li key={index}>{author.name}{author.affiliation && ` · ${author.affiliation}`}</li>)}</ul>
      <p>Track: {data.tracks.find((track) => track.track_id === data.metadata.track_id)?.name || "None"}</p>
      {data.edit_window.reason && <p className="text-sm">{data.edit_window.reason}</p>}
    </div>}
    <p className="text-xs">Metadata version {data.metadata.version} · Source: {data.metadata.source || "not recorded"}</p>
    <button type="button" className="btn-secondary" disabled={busy} onClick={async () => {
      setBusy(true); setError("");
      try { const rows = await getPaperMetadataHistory(submissionId, historyLoaded ? history.at(-1)?.version : undefined); setHistory((previous) => historyLoaded ? [...previous, ...rows] : rows); setHistoryLoaded(true); if (!rows.length) setNotice("No more metadata history."); }
      catch (err) { setError(errorMessage(err)); }
      finally { setBusy(false); }
    }}>{historyLoaded ? "Load more metadata history" : "View metadata history"}</button>
    {history.map((entry) => <details className="border-t pt-2" key={entry.version}>
      <summary className="cursor-pointer">Metadata version {entry.version} · {new Date(entry.updated_at).toLocaleString()} · {entry.source}</summary>
      <p>{entry.title || "No title recorded"}</p><p className="whitespace-pre-wrap">{entry.abstract}</p>
      <ul>{entry.authors.map((author, index) => <li key={index}>{author.name}{author.affiliation && ` · ${author.affiliation}`}</li>)}</ul>
      <p>Track: {data.tracks.find((track) => track.track_id === entry.track_id)?.name || "None"}</p>
      {entry.revision_id && <Link className="text-primary-600" to={`/submissions/${submissionId}?revision=${entry.revision_id}`}>Revision at this edit</Link>}
    </details>)}
  </section>;
}
