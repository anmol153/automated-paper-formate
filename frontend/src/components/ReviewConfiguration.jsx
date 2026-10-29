import { useEffect, useState } from "react";
import { errorMessage, getReviewConfiguration, saveReviewConfiguration } from "../lib/api.js";

function localTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export default function ReviewConfiguration({ confId, readOnly = false }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [deadline, setDeadline] = useState("");
  const [recommendations, setRecommendations] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    getReviewConfiguration(confId).then((value) => {
      if (active) { setData(value); setForm(value.form); setPolicy(value.policy); setDeadline(localTime(value.policy.deadline)); setRecommendations(value.form.recommendations.join("\n")); }
    }).catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [confId, refresh]);
  function criterion(index, key, value) {
    setForm((current) => ({ ...current, criteria: current.criteria.map((c, i) => i === index ? { ...c, [key]: value } : c) }));
  }
  async function save(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const saved = await saveReviewConfiguration(confId, { expected_version: data.version,
        form: { ...form, recommendations: recommendations.split("\n").map((r) => r.trim()).filter(Boolean) },
        policy: { ...policy, deadline: deadline ? new Date(deadline).toISOString() : null } });
      setData(saved); setForm(saved.form); setPolicy(saved.policy);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <section className="panel p-5 space-y-4">
    <h2 className="text-lg font-semibold">Formal review configuration</h2>
    {error && <p role="alert" className="text-danger-600">{error} <button className="btn-secondary ml-2" disabled={busy} onClick={() => { setError(""); setRefresh((n) => n + 1); }}>Reload configuration</button></p>}
    {!data ? !error && <p role="status">Loading review configuration…</p> : <>
      <p className="text-sm">Form version {data.form_number || "not published"} · Minimum current-revision reviews for a decision: {data.policy.minimum_reviews}</p>
      {readOnly || !data.can_configure ? <p className="text-sm">Review deadline: {data.policy.deadline ? new Date(data.policy.deadline).toLocaleString() : "No deadline configured"}</p> : <details>
        <summary className="cursor-pointer font-medium">Configure criteria, visibility and deadlines</summary>
        <form className="space-y-4 mt-4" onSubmit={save}>
          <p className="text-sm text-surface-500">Existing reviews keep their form version. Identity and recommendation visibility changes apply to future releases.</p>
          <label className="block">Review form name<input className="input-base mt-2" required maxLength={150} value={form.name} disabled={busy} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <div className="space-y-4">{form.criteria.map((c, i) => <fieldset key={i} className="border rounded-lg p-4 grid sm:grid-cols-2 gap-3">
            <legend className="px-2">Criterion {i + 1}</legend>
            <label>Stable criterion ID<input className="input-base mt-1" required pattern="[a-z][a-z0-9_]{0,39}" value={c.id} disabled={busy} onChange={(e) => criterion(i, "id", e.target.value)} /></label>
            <label>Label<input className="input-base mt-1" required maxLength={120} value={c.label} disabled={busy} onChange={(e) => criterion(i, "label", e.target.value)} /></label>
            <label>Answer type<select className="input-base mt-1" value={c.kind} disabled={busy} onChange={(e) => criterion(i, "kind", e.target.value)}><option value="score">Numerical score</option><option value="text">Text</option></select></label>
            <label>Released visibility<select className="input-base mt-1" value={c.visibility} disabled={busy} onChange={(e) => criterion(i, "visibility", e.target.value)}><option value="authors">Authors and chairs</option><option value="chairs">Chairs only</option></select></label>
            {c.kind === "score" && <><label>Minimum<input className="input-base mt-1" type="number" step="any" required value={c.minimum} disabled={busy} onChange={(e) => criterion(i, "minimum", Number(e.target.value))} /></label><label>Maximum<input className="input-base mt-1" type="number" step="any" required value={c.maximum} disabled={busy} onChange={(e) => criterion(i, "maximum", Number(e.target.value))} /></label></>}
            <label className="flex gap-2 items-center"><input type="checkbox" checked={c.required} disabled={busy} onChange={(e) => criterion(i, "required", e.target.checked)} /> Required on submission</label>
            <button className="btn-secondary" type="button" disabled={busy || form.criteria.length === 1} onClick={() => setForm({ ...form, criteria: form.criteria.filter((_, n) => n !== i) })}>Remove criterion</button>
          </fieldset>)}</div>
          <button className="btn-secondary" type="button" disabled={busy || form.criteria.length >= 20} onClick={() => {
            let n = form.criteria.length + 1;
            while (form.criteria.some((c) => c.id === `criterion_${n}`)) n += 1;
            setForm({ ...form, criteria: [...form.criteria, { id: `criterion_${n}`, label: "New criterion", kind: "text", required: true, visibility: "authors", minimum: 1, maximum: 5 }] });
          }}>Add criterion</button>
          <label className="block">Allowed recommendations (one per line)<textarea className="input-base mt-2" rows={7} required value={recommendations} disabled={busy} onChange={(e) => setRecommendations(e.target.value)} /></label>
          <label className="block">Review deadline (your local time)<input className="input-base mt-2" type="datetime-local" value={deadline} disabled={busy} onChange={(e) => setDeadline(e.target.value)} /></label>
          <label className="block">Minimum reviews for a decision<input className="input-base mt-2" type="number" min="0" max="20" required value={policy.minimum_reviews} disabled={busy} onChange={(e) => setPolicy({ ...policy, minimum_reviews: Number(e.target.value) })} /></label>
          <label className="block">Reviewer identities in future author releases<select className="input-base mt-2" value={policy.reviewer_identities} disabled={busy} onChange={(e) => setPolicy({ ...policy, reviewer_identities: e.target.value })}><option value="hidden">Hidden</option><option value="visible">Visible</option></select></label>
          {[["allow_edit_submitted", "Allow submitted reviews to be edited before the deadline"], ["reviewers_see_others", "Reviewers may see others’ submitted reviews after submitting their own"], ["publish_recommendation", "Include recommendations in author releases"]].map(([key, label]) => <label key={key} className="flex gap-2"><input type="checkbox" checked={policy[key]} disabled={busy} onChange={(e) => setPolicy({ ...policy, [key]: e.target.checked })} />{label}</label>)}
          <button className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Save review configuration"}</button>
        </form>
      </details>}
    </>}
  </section>;
}
