import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { comparePaperRevisions, errorMessage, getRevisionChecks } from "../lib/api.js";

const states = { resolved: "Resolved", newly_reported: "Newly reported", remaining: "Remaining", not_evaluated: "No longer evaluated" };
const value = (item) => item == null ? "Unavailable" : typeof item === "object" ? JSON.stringify(item) : String(item);

export default function RevisionComparison({ submissionId, revisions, selectedId }) {
  const [params, setParams] = useSearchParams();
  const selected = revisions.find((r) => r.revision_id === selectedId) || revisions[0];
  const validRevision = (id) => revisions.some((r) => r.revision_id === id);
  const [baseId, setBaseId] = useState(() => validRevision(params.get("compare_base")) ? params.get("compare_base") : selected?.parent_revision_id || revisions.find((r) => r !== selected)?.revision_id || selected?.revision_id);
  const [targetId, setTargetId] = useState(() => validRevision(params.get("compare_target")) ? params.get("compare_target") : selected?.revision_id);
  const [baseRun, setBaseRun] = useState(params.get("base_run") || "");
  const [targetRun, setTargetRun] = useState(params.get("target_run") || "");
  const [includeText, setIncludeText] = useState(params.get("compare_text") === "1");
  const [runs, setRuns] = useState({ base: [], target: [] });
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  const generation = useRef(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; generation.current += 1; }; }, []);

  useEffect(() => {
    if (!baseId || !targetId) return;
    let active = true;
    setLoadingRuns(true); setError("");
    Promise.all([getRevisionChecks(submissionId, baseId), getRevisionChecks(submissionId, targetId)])
      .then(([base, target]) => { if (active) setRuns({ base, target }); })
      .catch((err) => { if (active) setError(errorMessage(err)); })
      .finally(() => { if (active) setLoadingRuns(false); });
    return () => { active = false; };
  }, [submissionId, baseId, targetId]);

  async function compare(event) {
    event?.preventDefault();
    const request = ++generation.current;
    setBusy(true); setError(""); setData(null);
    try {
      const next = await comparePaperRevisions(submissionId, {
        base_revision_id: baseId, target_revision_id: targetId,
        base_run_id: baseRun || undefined, target_run_id: targetRun || undefined, include_text: includeText,
      });
      if (!mounted.current || request !== generation.current) return;
      setData(next);
      // Pin the exact successful run selections; a later recheck never silently
      // replaces the reports in this view or its shareable URL.
      setBaseRun(next.base.check?.run_id || ""); setTargetRun(next.target.check?.run_id || "");
      setParams((current) => {
        const nextParams = new URLSearchParams(current);
        nextParams.set("tab", "compare"); nextParams.set("compare_base", baseId); nextParams.set("compare_target", targetId);
        for (const [key, item] of [["base_run", next.base.check?.run_id], ["target_run", next.target.check?.run_id], ["compare_text", includeText ? "1" : null]]) {
          if (item) nextParams.set(key, item); else nextParams.delete(key);
        }
        return nextParams;
      }, { replace: true });
    } catch (err) {
      if (mounted.current && request === generation.current) setError(errorMessage(err));
    } finally { if (mounted.current && request === generation.current) setBusy(false); }
  }

  const revisionSelect = (side, id, update) => <label className="block">{side === "base" ? "Base revision" : "Target revision"}
    <select className="input-base mt-2" value={id || ""} disabled={busy} onChange={(e) => { update(e.target.value); setData(null); if (side === "base") setBaseRun(""); else setTargetRun(""); }}>
      {revisions.map((r) => <option key={r.revision_id} value={r.revision_id}>Revision {r.number} · {r.filename}</option>)}
    </select>
  </label>;
  const reportSelect = (side, id, update) => <label className="block">{side === "base" ? "Base report" : "Target report"}
    <select className="input-base mt-2" value={id} disabled={busy || loadingRuns} onChange={(e) => { update(e.target.value); setData(null); }}>
      <option value="">Latest saved report</option>
      {id && !runs[side].some((r) => r.run_id === id) && <option value={id}>Selected report · {id}</option>}
      {runs[side].map((run) => <option key={run.run_id} value={run.run_id}>Run {run.sequence} · {new Date(run.created_at).toLocaleString()} · {run.status.replaceAll("_", " ")}</option>)}
    </select>
  </label>;
  if (!revisions.length) return <p>No immutable revisions are available to compare.</p>;
  return <section className="space-y-5" aria-label="Revision comparison">
    <form className="panel p-5 space-y-4" onSubmit={compare}>
      <h2 className="text-lg font-semibold">Compare paper revisions</h2>
      <p className="text-sm">Compare retained reports and extracted document properties. Text comparison reads the saved files when requested.</p>
      <div className="grid md:grid-cols-2 gap-4">{revisionSelect("base", baseId, setBaseId)}{revisionSelect("target", targetId, setTargetId)}{reportSelect("base", baseRun, setBaseRun)}{reportSelect("target", targetRun, setTargetRun)}</div>
      <label className="flex gap-2 items-center"><input type="checkbox" checked={includeText} disabled={busy} onChange={(e) => { setIncludeText(e.target.checked); setData(null); }} />Include extracted text changes</label>
      <button className="btn-primary" disabled={busy || loadingRuns || !baseId || !targetId}>{busy ? "Comparing…" : "Compare revisions"}</button>
      {(busy || loadingRuns) && <p role="status">{busy ? "Loading comparison…" : "Loading saved reports…"}</p>}
      {error && <p role="alert" className="text-danger-600">{error}</p>}
    </form>
    {data && <>
      <section className="panel p-5 space-y-2" aria-label="Comparison snapshots">
        <h3 className="font-semibold">Revision {data.base.number} → Revision {data.target.number}</h3>
        {[["Base", data.base], ["Target", data.target]].map(([label, snapshot]) => <p className="text-sm break-all" key={label}>{label}: <Link className="text-primary-600" to={`/submissions/${submissionId}?revision=${snapshot.revision_id}&tab=checks${snapshot.check ? `&run=${snapshot.check.run_id}` : ""}`}>{snapshot.filename} · {snapshot.check ? `Run ${snapshot.check.sequence}` : "No report"}</Link>{snapshot.check && <> · {snapshot.check.run_id} · {snapshot.check.engine_version}</>}</p>)}
        {data.base.number > data.target.number && <p>Comparing a newer revision to an earlier revision. All changes follow the selected base → target direction.</p>}
        {data.same_file && <p>The retained file hashes are identical.</p>}
      </section>
      <section className="panel p-5 space-y-4">
        <h3 className="font-semibold">Formatting finding changes</h3>
        {data.formatting.warnings.map((warning) => <p key={warning} className="text-sm">{warning}</p>)}
        {data.formatting.status !== "available" ? <p>{data.formatting.reason}</p> : <>
          <p>Formatting: {data.formatting.base_status.replaceAll("_", " ")} → {data.formatting.target_status.replaceAll("_", " ")}</p>
          <p>Compliance score: {data.formatting.base_score ?? "unavailable"} → {data.formatting.target_score ?? "unavailable"}</p>
          <p>{Object.entries(data.formatting.summary).map(([state, count]) => `${states[state]}: ${count}`).join(" · ")}</p>
          <p className="text-sm">A finding is resolved only when the target report explicitly passes that rule. Newly reported findings may reflect newly measurable properties. Issue resolution remains a separate action.</p>
          {data.formatting.findings.map((finding) => <details key={finding.rule_id} className="border-t pt-3">
            <summary className="cursor-pointer">{states[finding.state]} · {(finding.after || finding.before).name} · {finding.rule_id}</summary>
            <div className="grid md:grid-cols-2 gap-4 mt-3">
              {[["Base", finding.before, finding.base_issue_ids], ["Target", finding.after, finding.target_issue_ids]].map(([label, result, issues]) => <div key={label} className="space-y-1 text-sm break-words"><h4 className="font-semibold">{label}</h4>{result ? <><p>{result.status} · {result.severity} · Confidence: {result.confidence || "unknown"}</p><p>Expected: {value(result.expected)}</p><p>Actual: {value(result.actual)}</p>{result.advice && <p>{result.advice}</p>}</> : <p>Rule absent from this report.</p>}{issues.length > 0 && <Link className="text-primary-600" to={`/issues/${submissionId}`}>View {issues.length} linked issue(s)</Link>}</div>)}
            </div>
            {finding.changed_fields.length > 0 && <p className="text-sm mt-2">Changed: {finding.changed_fields.join(", ")}</p>}
          </details>)}
        </>}
      </section>
      <section className="panel p-5 space-y-3">
        <h3 className="font-semibold">Extracted property changes</h3>
        <p className="text-sm">These are saved parser observations. Estimated counts and low-confidence detections need manual verification.</p>
        {data.properties.status !== "available" ? <p>{data.properties.reason}</p> : <>
          <p className="text-sm">Parsers: {data.properties.base_parser || "unknown"} → {data.properties.target_parser || "unknown"}</p>
          {[...new Set([...data.properties.base_warnings, ...data.properties.target_warnings])].map((warning) => <p className="text-sm" key={warning}>{warning}</p>)}
          <div className="overflow-x-auto"><table className="w-full text-sm text-left"><caption className="sr-only">Saved document properties by selected report</caption><thead><tr><th scope="col" className="p-2">Property</th><th scope="col" className="p-2">Base</th><th scope="col" className="p-2">Target</th><th scope="col" className="p-2">Comparison</th></tr></thead><tbody>{data.properties.fields.map((field) => <tr key={field.key} className="border-t align-top"><th scope="row" className="p-2 font-medium">{field.label}</th><td className="p-2 max-w-sm whitespace-pre-wrap break-words">{value(field.before)}</td><td className="p-2 max-w-sm whitespace-pre-wrap break-words">{value(field.after)}</td><td className="p-2">{field.state}</td></tr>)}</tbody></table></div>
        </>}
      </section>
      <section className="panel p-5 space-y-3">
        <h3 className="font-semibold">Extracted text changes</h3>
        <p className="text-sm">Text follows the current parser’s reading order and may omit source commands, images, equations or layout. Line numbers refer to extracted text, not pages. Text changes do not establish semantic or visual changes. PDF extraction has no OCR.</p>
        {data.text.status === "not_requested" ? <p>Select “Include extracted text changes” and compare again.</p> : data.text.status !== "available" ? <p>{data.text.reason}</p> : <>
          <p>{data.text.identical ? "No changes in extracted text." : `${data.text.added_lines} added lines · ${data.text.removed_lines} removed lines`}</p>
          <p className="text-xs text-surface-500">Extractor: {data.text.extractor_version}</p>
          {data.text.hunks.map((hunk, index) => <div className="border rounded overflow-x-auto" key={index}>
            <p className="text-xs p-2">Base line {hunk.base_start} · Target line {hunk.target_start}</p>
            <ol className="font-mono text-xs min-w-0" aria-label={`Text change ${index + 1}`}>
              {hunk.lines.map((line, n) => <li key={n} className={`flex gap-2 p-1 ${line.kind === "added" ? "bg-green-500/10" : line.kind === "removed" ? "bg-red-500/10" : ""}`}><span className="w-10 shrink-0 text-right" aria-label="Base line">{line.base_line ?? ""}</span><span className="w-10 shrink-0 text-right" aria-label="Target line">{line.target_line ?? ""}</span><span className="w-4 shrink-0" aria-label={line.kind}>{line.kind === "added" ? "+" : line.kind === "removed" ? "−" : " "}</span><span className="whitespace-pre-wrap break-all">{line.text}</span></li>)}
            </ol>
          </div>)}
        </>}
      </section>
    </>}
  </section>;
}
