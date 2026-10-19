import { Link, useParams, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { diffTemplateVersions, errorMessage } from "../lib/api.js";
import Button, { ButtonLink } from "../components/ui/Button.jsx";

const valueText = (value) => value === undefined ? "—" : value === null ? "Not set" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);

function changedGroups(diff) {
  const groups = Object.entries(diff || {}).filter(([name]) => name !== "_meta").map(([name, data]) => ({ name, rows: [
    ...Object.entries(data.changed || {}).map(([field, pair]) => ({ field, old: Array.isArray(pair) ? pair[0] : pair.old, next: Array.isArray(pair) ? pair[1] : pair.new, kind: "Changed" })),
    ...Object.entries(data.added || {}).map(([field, value]) => ({ field, next: value, kind: "Added" })),
    ...Object.entries(data.removed || {}).map(([field, value]) => ({ field, old: value, kind: "Removed" })),
  ] }));
  const metadata = Object.entries(diff?._meta || {}).filter(([field]) => !(field in diff)).map(([field, pair]) => ({ field, old: pair[0], next: pair[1], kind: "Changed" }));
  if (metadata.length) groups.push({ name: "Template details", rows: metadata });
  return groups.filter((group) => group.rows.length);
}

export default function TemplateDiff() {
  const { confId } = useParams();
  const [query] = useSearchParams();
  const oldId = query.get("old"), newId = query.get("new");
  const [diff, setDiff] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!oldId || !newId) { setError("Choose two published template versions from the conference template history."); setLoading(false); return; }
    let active = true; setLoading(true); setError(""); setDiff(null);
    diffTemplateVersions(confId, oldId, newId).then((data) => { if (active) setDiff(data.diff); }).catch((err) => { if (active) setError(errorMessage(err)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [confId, oldId, newId, attempt]);
  const groups = changedGroups(diff);
  return <div className="pf-management pf-formatting"><Link className="pf-back-link" to={`/conferences/${confId}/latest`}>← Conference templates</Link><header className="pf-management-header"><div><p className="pf-eyebrow">PUBLISHED FORMATTING RULES</p><h1>Template comparison</h1><p>Compare the configured rules in two immutable template versions.</p></div><ButtonLink to={`/conferences/${confId}/submissions`}>Conference papers →</ButtonLink></header>
    {oldId && newId && <div className="pf-template-version-pair"><div><span>Previous version</span><code>{oldId}</code></div><span aria-hidden="true">→</span><div><span>Compared version</span><code>{newId}</code></div></div>}
    {loading ? <div className="pf-card pf-empty" role="status">Loading template comparison…</div> : error ? <div role="alert" className="pf-message pf-message--error">{error}{oldId && newId && <Button onClick={() => setAttempt((value) => value + 1)}>Retry comparison</Button>}</div> : <div className="pf-stack">
      {!groups.length && <div className="pf-card pf-empty"><h2>No changed rules</h2><p>The compared versions contain the same formatting requirements.</p></div>}
      {groups.map((group) => <section className="pf-card" key={group.name}><div className="pf-card-heading"><h2 className="pf-capitalize">{group.name.replaceAll("_", " ")}</h2><span className="pf-count">{group.rows.length} changes</span></div>{group.rows.map((row) => <div className="pf-template-change-row" key={row.field}><div><strong>{row.field.replaceAll("_", " ")}</strong><span className="pf-count">{row.kind}</span></div><div><span>Before</span><pre>{valueText(row.old)}</pre></div><div><span>After</span><pre>{valueText(row.next)}</pre></div></div>)}</section>)}
      <details className="pf-card pf-card-body"><summary>Full structured comparison</summary><pre className="pf-template-raw-diff">{JSON.stringify(diff, null, 2)}</pre></details>
    </div>}
  </div>;
}
