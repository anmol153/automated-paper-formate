import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage, getActivity } from "../lib/api.js";

export default function PaperActivity({ submissionId }) {
  const [events, setEvents] = useState([]);
  const [before, setBefore] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    getActivity(submissionId).then((data) => { if (active) { setEvents(data.events); setBefore(data.next_before); } })
      .catch((err) => { if (active) setError(errorMessage(err)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [submissionId]);
  async function more() {
    setLoading(true); setError("");
    try { const data = await getActivity(submissionId, before); setEvents((rows) => [...rows, ...data.events]); setBefore(data.next_before); }
    catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  }
  return <section className="panel p-5 space-y-4">
    <h2 className="text-lg font-semibold">Activity</h2>
    {error && <p role="alert" className="text-danger-600">{error}</p>}
    <ol className="space-y-4">{events.map((event) => <li key={event.event_id} className="border-l-2 pl-4">
      <p>{event.action.replaceAll(".", " · ").replaceAll("_", " ")}</p>
      <p className="text-sm text-surface-500">{event.actor_id || (event.actor_role === "legacy" ? "Historical participant" : "System")} · {new Date(event.created_at).toLocaleString()}{event.visibility === "chairs" && " · Chairs only"}</p>
      {event.details.from && <p className="text-sm">{event.details.from} → {event.details.to}</p>}
      {event.details.reason && <p className="whitespace-pre-wrap text-sm">{event.details.reason}</p>}
      {event.revision_id && <Link className="text-primary-600 text-sm" to={`/submissions/${submissionId}?revision=${event.revision_id}`}>View associated revision</Link>}
    </li>)}</ol>
    {loading && <p role="status">Loading activity…</p>}
    {!loading && !error && events.length === 0 && <p>No collaboration events recorded yet.</p>}
    {before && <button className="btn-secondary" disabled={loading} onClick={more}>Load earlier events</button>}
  </section>;
}
