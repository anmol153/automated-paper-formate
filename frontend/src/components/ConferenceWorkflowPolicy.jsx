import { useEffect, useState } from "react";
import { errorMessage, getConferenceWorkflow, setConferenceWorkflow } from "../lib/api.js";

export default function ConferenceWorkflowPolicy({ confId }) {
  const [policy, setPolicy] = useState(null);
  const [gate, setGate] = useState("allow_issues");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    getConferenceWorkflow(confId).then((data) => { if (active) { setPolicy(data); setGate(data.formatting_gate); } })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [confId]);
  return <section className="panel p-5 space-y-3">
    <h2 className="font-semibold">Submission formatting policy</h2>
    {error && <p role="alert" className="text-danger-600">{error}</p>}
    {!policy ? !error && <p role="status">Loading policy…</p> : <>
      <p className="text-sm">{policy.formatting_gate === "block_errors" ? "Papers with blocking formatting errors stay in draft until corrected. Warnings may proceed." : "Papers may proceed to review with formatting findings. A completed check is required."}</p>
      {policy.can_configure && <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setError("");
        try { setPolicy(await setConferenceWorkflow(confId, gate)); }
        catch (err) { setError(errorMessage(err)); }
        finally { setBusy(false); }
      }}>
        <label className="block">Formatting gate
          <select className="input-base mt-2" value={gate} disabled={busy} onChange={(e) => setGate(e.target.value)}>
            <option value="allow_issues">Allow formatting findings</option>
            <option value="block_errors">Require blocking errors to be corrected</option>
          </select>
        </label>
        <button className="btn-secondary" disabled={busy}>{busy ? "Saving…" : "Save policy"}</button>
      </form>}
    </>}
  </section>;
}
