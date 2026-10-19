import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { diffTemplateVersions } from "../lib/api.js";
import { errorMessage } from "../lib/api.js";

export default function TemplateDiff() {
  const { confId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [oh, setOH] = useState(null);
  const [nw, setNW] = useState(null);
  const [diff, setDiff] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Expect query params ?old=&new=
  const query = new URLSearchParams(location.search);
  const oldId = query.get("old");
  const newId = query.get("new");

  useEffect(() => {
    if (!oldId || !newId) {
      setError("Missing template IDs. Use ?old=ID1&new=ID2 in URL");
      setLoading(false);
      return;
    }
    async function load() {
      try {
        const data = await diffTemplateVersions(confId, oldId, newId);
        setOH(oldId);
        setNW(newId);
        setDiff(data.diff);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [confId, oldId, newId]);

  if (loading) return <div className="text-center py-8">Loading diff…</div>;
  if (error) return <div className="alert alert-danger">{error}</div>;

  return (
    <div className="animate-fade-in">
      <header className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Template Diff</h1>
        <button className="btn-outline" onClick={() => navigate(-1)}>
          ← Back
        </button>
      </header>
      <p className="mb-4">
        Comparing template <strong>{oh}</strong> vs <strong>{nw}</strong>
      </p>
      <pre className="bg-surface-100 p-4 rounded overflow-auto">
        {JSON.stringify(diff, null, 2)}
      </pre>
    </div>
  );
}
