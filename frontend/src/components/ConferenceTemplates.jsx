import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import RuleEditor from "./RuleEditor.jsx";
import { emptyRuleSet } from "../lib/ruleOptions.js";
import {
  errorMessage, getConferenceTemplateVersion, getTemplate, importTemplate,
  listConferenceTemplateVersions, listTemplates, publishConferenceTemplate,
} from "../lib/api.js";

export default function ConferenceTemplates({ confId, canPublish, onAvailabilityChange }) {
  const [versions, setVersions] = useState([]);
  const [selected, setSelected] = useState("");
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [library, setLibrary] = useState([]);
  const [libraryId, setLibraryId] = useState("");
  const [libraryError, setLibraryError] = useState("");
  const [file, setFile] = useState(null);
  const [draft, setDraft] = useState(null);
  const [reload, setReload] = useState(0);

  const reportAvailability = useCallback((status) => onAvailabilityChange?.(status), [onAvailabilityChange]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); reportAvailability("loading");
    async function load() {
      try {
        const rows = await listConferenceTemplateVersions(confId);
        const latest = rows.length ? await getConferenceTemplateVersion(confId, rows[0][0]) : null;
        if (!active) return;
        setVersions(rows); setSelected(rows[0]?.[0] || ""); setSnapshot(latest);
        reportAvailability(rows.length ? "ready" : "missing");
      } catch (err) {
        if (active) { setError(errorMessage(err)); reportAvailability("error"); }
      } finally { if (active) setLoading(false); }
    }
    load();
    return () => { active = false; };
  }, [confId, reload, reportAvailability]);

  useEffect(() => {
    if (!canPublish) return;
    let active = true;
    listTemplates().then((rows) => { if (active) { setLibrary(rows); setLibraryError(""); } })
      .catch((err) => { if (active) setLibraryError(errorMessage(err)); });
    return () => { active = false; };
  }, [canPublish, reload]);

  async function editFrom(loader) {
    setBusy(true); setError(""); setNotice("");
    try { setDraft(await loader()); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  async function viewVersion(id) {
    if (!id) return;
    setBusy(true); setError("");
    try { const rules = await getConferenceTemplateVersion(confId, id); setSelected(id); setSnapshot(rules); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  async function publish(event) {
    event.preventDefault();
    if (!draft?.name?.trim()) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await publishConferenceTemplate(confId, draft);
      setDraft(null); setFile(null); setLibraryId("");
      setSnapshot(saved); setSelected(saved.template_id);
      // Publishing succeeded even if a subsequent history refresh fails.
      setNotice(`Published “${saved.name}” as a new conference template version.`);
      setReload((value) => value + 1);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }

  return <section className="panel p-5 space-y-4" aria-label="Conference templates">
    <h2 className="text-lg font-semibold">Conference template</h2>
    <p className="text-sm text-surface-500">New papers use the latest published version. Existing papers and their revisions keep their original template and reports.</p>
    {loading && <p role="status">Loading conference template…</p>}
    {error && <p role="alert" className="text-danger-600">{error} <button type="button" className="btn-secondary" disabled={busy} onClick={() => setReload((value) => value + 1)}>Reload templates</button></p>}
    {notice && <p role="status">{notice}</p>}
    {!loading && !versions.length && !error && <p>No template has been published. {canPublish ? "Configure and publish one below before authors upload papers." : "Ask a conference chair to publish the formatting requirements before uploading."}</p>}
    {!loading && versions.length > 0 && <>
      <label className="block">Published template version
        <select className="input-base mt-1" value={selected} disabled={busy} onChange={(event) => viewVersion(event.target.value)}>
          {versions.map(([id, , created], index) => <option key={id} value={id}>{index === 0 ? "Latest · " : ""}{id} · {new Date(created).toLocaleString()}</option>)}
        </select>
      </label>
      {snapshot && <>
        <p className="font-medium">{snapshot.name}</p>
        {selected !== versions[0][0] && <p className="text-sm">Viewing a previous version. New papers use the latest published version.</p>}
        <details><summary className="cursor-pointer">View published rules</summary><div className="mt-4"><RuleEditor rules={snapshot} disabled /></div></details>
      </>}
      {versions.length > 1 && <Link className="text-primary-600" to={`/conferences/${confId}/diff?old=${encodeURIComponent(versions[1][0])}&new=${encodeURIComponent(versions[0][0])}`}>Compare the two latest template versions</Link>}
    </>}
    {canPublish && <details>
      <summary className="cursor-pointer font-medium">Configure a template</summary>
      <div className="mt-4 space-y-4">
        <p className="text-sm">Import a template file, use saved standalone rules, or start with a blank template. Review the rules before publishing.</p>
        {libraryError && <p role="alert" className="text-danger-600">Saved template library: {libraryError}</p>}
        <label className="block">Saved standalone template
          <select className="input-base mt-1" disabled={busy} value={libraryId} onChange={(event) => setLibraryId(event.target.value)}>
            <option value="">Choose saved rules</option>{library.map((item) => <option key={item.template_id} value={item.template_id}>{item.name}</option>)}
          </select>
        </label>
        <button type="button" className="btn-secondary" disabled={busy || !libraryId} onClick={() => editFrom(() => getTemplate(libraryId))}>Load saved rules</button>
        <label className="block">Conference template file (PDF, DOCX or LaTeX)
          <input type="file" className="block mt-1" accept=".pdf,.docx,.tex,.latex" disabled={busy} onChange={(event) => setFile(event.target.files?.[0] || null)} />
        </label>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-secondary" disabled={busy || !file} onClick={() => editFrom(() => importTemplate(file))}>Import template rules</button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => { setDraft({ ...emptyRuleSet(), name: "" }); setError(""); setNotice(""); }}>Start blank template</button>
          {snapshot && <button type="button" className="btn-secondary" disabled={busy} onClick={() => { setDraft(structuredClone(snapshot)); setError(""); setNotice(""); }}>Copy viewed version for editing</button>}
        </div>
        {draft && <form className="space-y-4 border-t pt-4" onSubmit={publish}>
          <h3 className="font-semibold">Review template rules</h3>
          <RuleEditor rules={draft} onChange={setDraft} disabled={busy} />
          <p className="text-sm">Publishing creates an immutable version and makes it the default for future papers in this conference. Editing saved standalone rules later will not update it.</p>
          {!draft.name?.trim() && <p>A template name is required.</p>}
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" disabled={busy || !draft.name?.trim()}>{busy ? "Working…" : "Publish template version"}</button>
            <button type="button" className="btn-secondary" disabled={busy} onClick={() => setDraft(null)}>Discard unpublished changes</button>
          </div>
        </form>}
      </div>
    </details>}
  </section>;
}
