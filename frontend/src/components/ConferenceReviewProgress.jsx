import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage, getConferenceReviewProgress } from "../lib/api.js";

export default function ConferenceReviewProgress({ confId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    getConferenceReviewProgress(confId).then((value) => { if (active) setData(value); }).catch((err) => {
      if (active && err?.response?.status !== 403) setError(errorMessage(err));
    });
    return () => { active = false; };
  }, [confId]);
  if (error) return <p role="alert" className="text-danger-600">{error}</p>;
  if (!data) return null;
  return <section className="panel p-5 space-y-4">
    <h2 className="text-lg font-semibold">Chair review dashboard</h2>
    <p className="text-sm">Minimum current-revision reviews for a decision: {data.minimum_reviews}. Papers with a chair conflict are omitted.</p>
    {data.papers.length === 0 ? <p>No papers available for you to manage.</p> : <div className="overflow-x-auto"><table className="w-full text-sm text-left">
      <thead><tr><th className="p-2">Paper</th><th className="p-2">Status</th><th className="p-2">Submitted</th><th className="p-2">Missing</th></tr></thead>
      <tbody>{data.papers.map((p) => <tr className="border-t" key={p.submission_id}><td className="p-2"><Link className="text-primary-600" to={`/submissions/${p.submission_id}`}>{p.paper_number ? `#${p.paper_number} · ` : ""}{p.title || p.filename}</Link>{p.title && <p className="text-xs text-surface-500">{p.filename}</p>}</td><td className="p-2">{p.status.replaceAll("_", " ")}</td><td className="p-2">{p.submitted}</td><td className="p-2">{p.missing}</td></tr>)}</tbody>
    </table></div>}
  </section>;
}
