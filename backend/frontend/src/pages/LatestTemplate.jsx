import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { getLatestTemplateVersion, errorMessage } from "../lib/api.js";

export default function LatestTemplate() {
  const { confId } = useParams();
  const location = useLocation();

  const query = new URLSearchParams(location.search);
  const confIdFromQuery = query.get("confId");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rules, setRules] = useState(null);

  useEffect(() => {
    const targetConfId = confId || confIdFromQuery;
    if (!targetConfId) {
      setError("Missing conference ID. Use /conferences/:confId/latest?confId=ID or navigate from a conference page.");
      setLoading(false);
      return;
    }
    async function load() {
      try {
        const data = await getLatestTemplateVersion(targetConfId);
        setRules(data);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [confId, confIdFromQuery]);

  if (loading) return <div className="text-center py-8">Loading latest template…</div>;
  if (error) return <div className="alert alert-danger">{error}</div>;

  return (
    <div className="animate-fade-in">
      <header className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Latest Template</h1>
        <button className="btn-outline" onClick={() => navigate(-1)}>
          ← Back
        </button>
      </header>
      {rules && (
        <pre className="bg-surface-100 p-4 rounded overflow-auto max-h-70">
          {JSON.stringify(rules, null, 2)}
        </pre>
      )}
      {!rules && <p className="text-surface-500">No template found for this conference.</p>}
    </div>
  );
}