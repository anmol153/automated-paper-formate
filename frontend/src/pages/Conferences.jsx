import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listConferences, errorMessage } from "../lib/api.js";
import Button, { ButtonLink } from "../components/ui/Button.jsx";

export default function Conferences() {
  const [conferences, setConferences] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    listConferences().then((rows) => { if (active) setConferences(rows); })
      .catch((err) => { if (active) setError(errorMessage(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [attempt]);
  const visible = conferences.filter((conf) => `${conf.name} ${conf.description || ""}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="pf-management"><header className="pf-management-header"><div><p className="pf-eyebrow">RESEARCH STARTS HERE</p><h1>Conferences</h1><p>Find your event, contribute a paper or build a conference of your own.</p></div><ButtonLink variant="primary" to="/conferences/new">+ Create conference</ButtonLink></header>
    <section className="pf-card"><div className="pf-list-toolbar"><div><h2>Conference directory <span className="pf-count">{loading ? "…" : conferences.length}</span></h2><p>Public conference information. Paper access depends on your membership.</p></div><label className="pf-search"><span className="sr-only">Search conferences</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /></svg><input type="search" placeholder="Search conferences…" value={search} onChange={(e) => setSearch(e.target.value)} /></label></div>
      {loading ? <div className="pf-empty" role="status">Loading conferences…</div> : error ? <div className="pf-empty"><p role="alert">{error}</p><Button onClick={() => setAttempt((n) => n + 1)}>Retry conferences</Button></div> : !visible.length ? <div className="pf-empty"><span className="pf-empty-symbol" aria-hidden="true">▦</span><h2>{search ? "No matching conferences" : "Make room for your next big idea"}</h2><p>{search ? "Try another name or clear your search." : "Create a conference to start collecting papers and bring your research community together."}</p>{search ? <Button onClick={() => setSearch("")}>Clear search</Button> : <ButtonLink variant="primary" to="/conferences/new">Create your first conference</ButtonLink>}</div> : <div className="pf-conference-table" role="list">{visible.map((conf) => <article key={conf.conference_id} className="pf-conference-row" role="listitem"><span className="pf-conference-monogram">{conf.name.slice(0, 2).toUpperCase()}</span><div className="pf-conference-description"><h3><Link to={`/conferences/${conf.conference_id}`}>{conf.name}</Link></h3><p>{conf.description || "No description added yet."}</p></div><div className="pf-row-actions"><Link to={`/conferences/${conf.conference_id}/submissions`}>Papers</Link><ButtonLink to={`/conferences/${conf.conference_id}`}>Open workspace →</ButtonLink></div></article>)}</div>}
      {!loading && !error && <div className="pf-table-footer">{visible.length} of {conferences.length} conferences</div>}
    </section><div className="pf-help-strip"><strong>Looking to submit a paper?</strong><span>Open your conference workspace, check the requirements, then choose Submit a paper.</span><Link to="/submit">Standalone formatting check →</Link></div>
  </div>;
}
