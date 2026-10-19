import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage, listConferences } from "../lib/api.js";

export default function ConferenceChooser() {
  const [conferences, setConferences] = useState([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    listConferences().then((rows) => { if (active) setConferences(rows); })
      .catch((err) => { if (active) setError(errorMessage(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);
  return <section className="panel mb-6 space-y-3" aria-label="Choose a conference">
    <h2 className="font-semibold">Submit to a conference for review</h2>
    <p className="text-sm text-surface-500">Choose your conference to upload a paper with revision history and peer review. Sign in with an account the chair has added to that conference.</p>
    {loading ? <p role="status">Loading conferences…</p> : error ? <p role="alert">{error} <button className="btn-secondary" type="button" onClick={() => setReload((value) => value + 1)}>Retry conferences</button></p> : conferences.length ? <>
      <label className="block">Choose conference<select className="input-base mt-1" value={selected} onChange={(event) => setSelected(event.target.value)}>
        <option value="">Select a conference</option>{conferences.map((conf) => <option key={conf.conference_id} value={conf.conference_id}>{conf.name}</option>)}
      </select></label>
      {selected && <Link className="btn-primary inline-flex" to={`/conferences/${selected}/submit`}>Open conference submissions</Link>}
    </> : <p>No conferences yet. <Link className="text-primary-600" to="/conferences">Create a conference</Link> to get started.</p>}
    <p className="text-sm">The standalone check below produces a formatting report. Use conference submissions when you want peer review.</p>
  </section>;
}
