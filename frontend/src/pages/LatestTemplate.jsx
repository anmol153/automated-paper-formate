import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { errorMessage, getConference } from "../lib/api.js";
import ConferenceTemplates from "../components/ConferenceTemplates.jsx";

export default function LatestTemplate() {
  const { confId } = useParams();
  const [query] = useSearchParams();
  const target = confId || query.get("confId");
  return <TemplatePage key={target} confId={target} />;
}

function TemplatePage({ confId }) {
  const { user, loading } = useAuth();
  const [conference, setConference] = useState(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!user || !confId) return;
    let active = true;
    setError("");
    getConference(confId).then((row) => { if (active) setConference(row); })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [confId, user, reload]);
  if (loading) return <p role="status">Loading account…</p>;
  if (!user) return <p><Link to="/login" className="text-primary-600">Sign in</Link> to view conference templates.</p>;
  if (!confId) return <p role="alert">Choose a conference from <Link to="/conferences" className="text-primary-600">Conferences</Link>.</p>;
  return <div className="pf-management pf-formatting pf-conference-content space-y-5">
    <Link className="text-primary-600" to={`/conferences/${confId}/submissions`}>← Conference papers</Link>
    <header className="pf-management-header"><div><p className="pf-eyebrow">CONFERENCE FORMATTING</p><h1>{conference?.name || "Conference"} · Templates</h1><p>Published requirements, template versions and formatting rules.</p></div></header>
    {error ? <p role="alert">{error} <button className="btn-secondary" onClick={() => setReload((value) => value + 1)}>Retry conference</button></p> : !conference ? <p role="status">Loading conference…</p> : <ConferenceTemplates confId={confId} canPublish={conference.members?.some((member) => member.user_id === user.user_id && member.role === "owner")} />}
  </div>;
}
