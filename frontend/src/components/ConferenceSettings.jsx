import { useEffect, useState } from "react";
import { createConferenceTrack, errorMessage, getConferenceSettings, saveConferenceSettings, updateConferenceTrack } from "../lib/api.js";
import Field from "./ui/Field.jsx";
import Button from "./ui/Button.jsx";

const localDate = (date) => date ? new Date(new Date(date).getTime() - new Date(date).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "";
const dateKeys = ["submissions_open_at", "submissions_close_at", "revisions_close_at"];
const localSettings = (settings) => ({ ...settings, ...Object.fromEntries(dateKeys.map((key) => [key, localDate(settings[key])])) });

function TrackEditor({ confId, track, onSaved, onError, disabled }) {
  const [form, setForm] = useState({ name: track.name, description: track.description, active: track.active });
  const [busy, setBusy] = useState(false);
  return <form className="pf-track-editor pf-stack" onSubmit={async (e) => {
    e.preventDefault(); setBusy(true);
    try { await updateConferenceTrack(confId, track.track_id, { ...form, expected_version: track.version }); await onSaved(); }
    catch (err) { onError(errorMessage(err)); }
    finally { setBusy(false); }
  }}>
    <Field label="Track name" required><input maxLength={120} value={form.name} disabled={disabled || busy} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
    <Field label="Track description"><textarea maxLength={4000} value={form.description} disabled={disabled || busy} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
    <label className="pf-check-option"><input type="checkbox" checked={form.active} disabled={disabled || busy} onChange={(e) => setForm({ ...form, active: e.target.checked })} /><span>Accept new papers in this track</span></label>
    <div><Button type="submit" disabled={disabled || busy}>{busy ? "Saving…" : "Save track"}</Button></div>
  </form>;
}

export default function ConferenceSettings({ confId, data, onChanged, expanded = false, readOnly = false }) {
  const [form, setForm] = useState(null);
  const [track, setTrack] = useState({ name: "", description: "", active: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => { if (data) setForm(localSettings(data.settings)); }, [confId, data?.version]);
  const reload = async () => onChanged(await getConferenceSettings(confId));
  const change = (key, value) => { setForm((previous) => ({ ...previous, [key]: value })); setMessage(""); };
  if (!data || !form) return <p role="status">Loading conference settings…</p>;
  if (!data.enabled) return <p className="panel p-4">Conference scheduling and track configuration are not available yet.</p>;
  return <section className="pf-management pf-card pf-conference-settings">
    <div className="pf-card-heading"><div><h2>Conference settings and tracks</h2><p>Dates, requirements and the structure of your conference.</p></div><span className="pf-status-chip">{data.settings.lifecycle_status}</span></div>
    <div className="pf-settings-summary pf-stack"><p>{data.settings.abbreviation && `${data.settings.abbreviation} · `}{data.submission_window.allowed ? "Initial submissions open" : "Initial submissions closed"}</p>
    {data.settings.website && <a className="text-primary-600" href={data.settings.website} rel="noreferrer" target="_blank">Conference website</a>}
    {data.settings.research_scope && <p className="whitespace-pre-wrap">{data.settings.research_scope}</p>}
    {dateKeys.map((key, index) => data.settings[key] && <p className="text-sm" key={key}>{["Submissions open", "Submissions close", "Requested revisions close"][index]}: {new Date(data.settings[key]).toLocaleString()}</p>)}
    <p className="text-sm">Required before review: {[data.settings.require_title && "title", data.settings.require_abstract && "abstract", data.settings.require_authors && "author list", data.settings.require_track && "track"].filter(Boolean).join(", ") || "No additional metadata requirements"}.</p>
    {data.settings.lifecycle_status === "archived" && <p className="pf-message">This conference is archived. Its settings and tracks are read-only.</p>}
    {error && <div role="alert" className="pf-message pf-message--error">{error} <Button disabled={busy} onClick={() => { setError(""); reload().catch((err) => setError(errorMessage(err))); }}>Reload settings</Button></div>}
    {message && <p role="status" className="pf-inline-status">{message}</p>}</div>
    {!readOnly && data.can_configure && data.settings.lifecycle_status !== "archived" && <details className="pf-settings-disclosure" open={expanded || undefined}>
      <summary className="cursor-pointer font-medium">Configure conference</summary>
      <form className="pf-settings-editor" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setError(""); setMessage("");
        try {
          const settings = { ...form, website: form.website || null, ...Object.fromEntries(dateKeys.map((key) => [key, form[key] ? new Date(form[key]).toISOString() : null])) };
          onChanged(await saveConferenceSettings(confId, { expected_version: data.version, settings })); setMessage("Conference settings saved.");
        } catch (err) { setError(errorMessage(err)); }
        finally { setBusy(false); }
      }}>
        <fieldset className="pf-settings-section"><legend>Event details</legend><p className="pf-section-description">Give your conference a recognizable identity and define its current stage.</p><div className="pf-form-grid"><Field label="Abbreviation"><input maxLength={40} value={form.abbreviation} disabled={busy} onChange={(e) => change("abbreviation", e.target.value)} /></Field><Field label="Conference lifecycle"><select value={form.lifecycle_status} disabled={busy} onChange={(e) => change("lifecycle_status", e.target.value)}>{["setup", "open", "reviewing", "closed", "archived"].map((state) => <option key={state} value={state}>{state}</option>)}</select></Field></div><Field label="Website"><input type="url" value={form.website || ""} disabled={busy} placeholder="https://your-conference.org" onChange={(e) => change("website", e.target.value)} /></Field><Field label="Research scope"><textarea rows={3} maxLength={10000} value={form.research_scope} disabled={busy} onChange={(e) => change("research_scope", e.target.value)} /></Field></fieldset>
        <fieldset className="pf-settings-section"><legend>Submission schedule</legend><p className="pf-section-description">Choose when authors can upload papers and requested revisions.</p><div className="pf-form-grid">{dateKeys.map((key, index) => <Field label={["Submission opening time", "Submission closing time", "Requested revision deadline"][index]} key={key}><input type="datetime-local" value={form[key]} disabled={busy} onChange={(e) => change(key, e.target.value)} /></Field>)}</div><p className="pf-fine-print">Times use your local timezone and are saved as UTC. A blank time has no date limit; lifecycle rules still apply. Closing time is exclusive.</p></fieldset>
        <fieldset className="pf-settings-section"><legend>Submission requirements</legend><p className="pf-section-description">Choose the metadata authors must provide before a paper enters review.</p><div className="pf-requirements-grid">{[["require_title", "Require title", "Identify the research paper."], ["require_abstract", "Require abstract", "Include a summary of the work."], ["require_authors", "Require author list", "Record the paper's author metadata."], ["require_track", "Require track", "Route the paper to a conference track."]].map(([key, label, hint]) => <label className="pf-check-option" key={key}><input type="checkbox" checked={form[key]} disabled={busy} onChange={(e) => change(key, e.target.checked)} /><span>{label}<small>{hint}</small></span></label>)}</div></fieldset>
        <div className="pf-form-footer"><Button type="submit" variant="primary" busy={busy}>{busy ? "Saving…" : "Save conference settings"}</Button></div>
      </form>
    </details>}
    <div className="pf-card-heading pf-tracks-heading"><div><h3>Tracks</h3><p>Organize papers by topic or submission category.</p></div><span className="pf-count">{data.tracks.length}</span></div><div className="pf-card-body pf-stack">
    {!data.tracks.length && <p className="pf-track-empty">No tracks configured.</p>}
    {data.tracks.map((item) => !readOnly && data.can_configure && data.settings.lifecycle_status !== "archived" ? <TrackEditor key={`${item.track_id}:${item.version}`} confId={confId} track={item} onSaved={reload} onError={setError} disabled={busy} /> : <div className="pf-track-editor" key={item.track_id}><h3>{item.name}{!item.active && " (archived)"}</h3><p>{item.description}</p></div>)}
    {!readOnly && data.can_configure && data.settings.lifecycle_status !== "archived" && <form className="pf-stack pf-section-divider" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true); setError("");
      try { await createConferenceTrack(confId, track); setTrack({ name: "", description: "", active: true }); await reload(); }
      catch (err) { setError(errorMessage(err)); }
      finally { setBusy(false); }
    }}>
      <h3>Add a track</h3><Field label="New track name" required><input maxLength={120} value={track.name} disabled={busy} onChange={(e) => setTrack({ ...track, name: e.target.value })} /></Field>
      <Field label="New track description"><textarea rows={2} maxLength={4000} value={track.description} disabled={busy} onChange={(e) => setTrack({ ...track, description: e.target.value })} /></Field>
      <div><Button type="submit" disabled={busy || !track.name.trim()}>Create track</Button></div>
    </form>}</div>
  </section>;
}
