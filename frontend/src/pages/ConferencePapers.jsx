import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { createConferenceSubmission, errorMessage, getConference, getConferenceSettings, listConferenceSubmissions } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import ConferenceWorkflowPolicy from "../components/ConferenceWorkflowPolicy.jsx";
import ReviewConfiguration from "../components/ReviewConfiguration.jsx";
import ConferenceReviewProgress from "../components/ConferenceReviewProgress.jsx";
import ConferenceSettings from "../components/ConferenceSettings.jsx";
import PaperMetadataFields, { emptyMetadata } from "../components/PaperMetadataFields.jsx";
import ConferenceTemplates from "../components/ConferenceTemplates.jsx";
import StateBadge from "../components/ui/StateBadge.jsx";
import { ButtonLink } from "../components/ui/Button.jsx";

export default function ConferencePapers() {
  const { confId } = useParams();
  const { pathname } = useLocation();
  const creating = pathname.endsWith("/submit");
  return <ConferencePaperList key={`${confId}:${creating}`} confId={confId} creating={creating} />;
}

function ConferencePaperList({ confId, creating }) {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const [conference, setConference] = useState(null);
  const [papers, setPapers] = useState([]);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [submitForReview, setSubmitForReview] = useState(true);
  const [settings, setSettings] = useState(null);
  const [metadata, setMetadata] = useState(emptyMetadata);
  const [search, setSearch] = useState("");
  const [trackFilter, setTrackFilter] = useState("");
  const [templateStatus, setTemplateStatus] = useState("loading");
  useEffect(() => {
    if (!user) return;
    let active = true;
    Promise.all([getConference(confId), listConferenceSubmissions(confId), getConferenceSettings(confId)])
      .then(([conf, rows, config]) => { if (active) { setConference(conf); setPapers(rows); setSettings(config); } })
      .catch((err) => { if (active) setError(errorMessage(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [confId, user]);
  async function submit(event) {
    event.preventDefault();
    if (!file || templateStatus !== "ready") return;
    setBusy(true); setError("");
    try {
      const suppliedMetadata = settings?.enabled && (metadata.title || metadata.abstract || metadata.authors.length || metadata.track_id) ? metadata : undefined;
      const paper = await createConferenceSubmission(confId, file, { submitForReview, metadata: suppliedMetadata });
      navigate(`/submissions/${paper.submission_id}`);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  const visiblePapers = papers.filter((paper) => (!trackFilter || paper.track_id === trackFilter) && `${paper.title} ${paper.filename} #${paper.paper_number || ""}`.toLowerCase().includes(search.toLowerCase()));
  if (authLoading) return <p role="status">Loading account…</p>;
  if (!user) return <p><Link to="/login" className="text-primary-600">Sign in</Link> to access conference papers.</p>;
  return <div className="pf-management pf-conference-content space-y-6">
    <Link to="/conferences" className="text-primary-600">← Conferences</Link>
    <header className="pf-management-header"><div><p className="pf-eyebrow">CONFERENCE SUBMISSIONS</p><h1>{conference?.name || "Conference"} · {creating ? "New submission" : "Papers"}</h1><p>{creating ? "Upload your manuscript using this conference’s formatting requirements." : "Follow submissions from the first upload through formatting checks and review."}</p></div><ButtonLink to={creating ? `/conferences/${confId}/submissions` : `/conferences/${confId}`}>{creating ? "View papers →" : "Conference workspace →"}</ButtonLink></header>
    {error && <p role="alert" className="text-danger-600">{error}</p>}
    {loading ? <p role="status">Loading papers…</p> : conference && <>
      <details className="pf-card pf-inline-configuration"><summary>Conference requirements and configuration</summary><div className="pf-stack">
      <ConferenceSettings confId={confId} data={settings} onChanged={setSettings} />
      <ConferenceTemplates confId={confId} canPublish={conference.members?.some((member) => member.user_id === user.user_id && member.role === "owner")} onAvailabilityChange={setTemplateStatus} />
      <ConferenceWorkflowPolicy confId={confId} />
      <ReviewConfiguration confId={confId} />
      <ConferenceReviewProgress confId={confId} />
      </div></details>
      {creating && <form id="new-submission" className="panel p-5 space-y-4 pf-conference-submission-form" onSubmit={submit}>
        <div className="pf-submission-form-heading"><span className="pf-eyebrow">NEW MANUSCRIPT</span><h2>Submit a paper</h2>
        <p>Your first upload becomes revision 1 and is checked against this conference’s current template.</p></div>
        {templateStatus !== "ready" && <p>Paper uploads are available once the conference template has loaded. If none is published, ask a chair to configure one above.</p>}
        {settings?.enabled && <PaperMetadataFields value={metadata} onChange={setMetadata} tracks={settings.tracks} disabled={busy || settings.submission_window.allowed === false} />}
        <label className="block">Paper file (PDF, DOCX or LaTeX)
          <input className="block mt-2" type="file" accept=".pdf,.docx,.tex,.latex" required disabled={busy || templateStatus !== "ready" || settings?.submission_window.allowed === false}
            onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
        <label className="flex gap-2"><input type="checkbox" checked={submitForReview} disabled={busy} onChange={(e) => setSubmitForReview(e.target.checked)} /> Submit for review after formatting checks</label>
        <p className="text-sm text-surface-500">If the conference’s formatting gate is not met, the paper stays in draft so you can correct it.</p>
        {settings?.submission_window.reason && <p>{settings.submission_window.reason}</p>}
        <div className="pf-submission-form-footer"><button className="btn-primary" disabled={busy || !file || templateStatus !== "ready" || settings?.submission_window.allowed === false}>{busy ? "Uploading and checking…" : "Create submission"}</button>
        <Link to={`/conferences/${confId}/latest`}>View conference template →</Link></div>
      </form>}
      {!creating && <section className="panel p-5 pf-paper-list pf-conference-paper-list">
        <div className="pf-submission-list-heading"><div><h2>Papers you can access</h2><p>Open a paper to follow its discussion, revisions and review progress.</p></div><span className="pf-count">{visiblePapers.length} of {papers.length}</span></div>
        <div className="pf-submission-filters"><label className="block">Search papers<input className="input-base mt-1" type="search" placeholder="Title, filename or paper number" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
        {settings?.tracks.length > 0 && <label className="block">Track<select className="input-base mt-1" value={trackFilter} onChange={(e) => setTrackFilter(e.target.value)}><option value="">All tracks</option>{settings.tracks.map((track) => <option key={track.track_id} value={track.track_id}>{track.name}</option>)}</select></label>}</div>
        {visiblePapers.length === 0 ? <div className="pf-submission-empty"><h3>{papers.length ? "No papers match these filters" : "No submissions yet"}</h3><p>{papers.length ? "Try another title or track." : "New conference submissions will appear here."}</p></div> : <ul className="pf-conference-paper-rows">
          {visiblePapers.map((paper) => <li className="pf-conference-paper-row" key={paper.submission_id}>
            <div className="pf-conference-paper-info"><span className="pf-eyebrow">{paper.paper_number ? `PAPER #${paper.paper_number}` : "CONFERENCE PAPER"}</span><Link to={`/submissions/${paper.submission_id}`}>{paper.title || paper.filename}</Link>{paper.title && <span className="pf-paper-muted">{paper.filename}</span>}</div>
            <div className="pf-paper-state"><StateBadge status={paper.status} /><small>Formatting score: {paper.compliance_score ?? "—"}</small></div>
          </li>)}
        </ul>}
      </section>}
    </>}
  </div>;
}
