import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { createConferenceSubmission, errorMessage, getConference, getConferenceSettings, listConferenceSubmissions, listConferenceTemplateVersions } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import ConferenceWorkflowPolicy from "../components/ConferenceWorkflowPolicy.jsx";
import ReviewConfiguration from "../components/ReviewConfiguration.jsx";
import ConferenceReviewProgress from "../components/ConferenceReviewProgress.jsx";
import ConferenceSettings from "../components/ConferenceSettings.jsx";
import PaperMetadataFields, { emptyMetadata, validatePaperMetadata } from "../components/PaperMetadataFields.jsx";
import SubmissionField from "../components/SubmissionField.jsx";
import SubmissionRequirements from "../components/SubmissionRequirements.jsx";
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
  const formRef = useRef(null);
  const [validationAttempt, setValidationAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState(null);
  const [reload, setReload] = useState(0);
  const [submitForReview, setSubmitForReview] = useState(true);
  const [settings, setSettings] = useState(null);
  const [metadata, setMetadata] = useState(emptyMetadata);
  const [search, setSearch] = useState("");
  const [trackFilter, setTrackFilter] = useState("");
  const [templateStatus, setTemplateStatus] = useState("loading");
  const [templateReload, setTemplateReload] = useState(0);
  useEffect(() => {
    if (!user) return;
    let active = true;
    setTemplateStatus("loading");
    listConferenceTemplateVersions(confId)
      .then((versions) => { if (active) setTemplateStatus(versions.length ? "ready" : "missing"); })
      .catch(() => { if (active) setTemplateStatus("error"); });
    return () => { active = false; };
  }, [confId, user, templateReload]);
  useEffect(() => {
    if (!user) return;
    let active = true;
    setLoading(true); setLoadError(null);
    Promise.all([getConference(confId), listConferenceSubmissions(confId), getConferenceSettings(confId)])
      .then(([conf, rows, config]) => { if (active) { setConference(conf); setPapers(rows); setSettings(config); } })
      .catch((err) => { if (active) setLoadError({ message: errorMessage(err), accessDenied: [403, 404].includes(err?.response?.status) }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [confId, user, reload]);
  const uploadBlocked = templateStatus !== "ready" || settings?.submission_window.allowed === false;
  const fieldErrors = validationAttempt ? {
    ...(settings?.enabled ? validatePaperMetadata(metadata, settings.settings, submitForReview, settings.tracks) : {}),
    ...(!file ? { file: "Choose a PDF, Word (.docx), or LaTeX paper." } : {}),
  } : {};
  useEffect(() => {
    if (!validationAttempt) return;
    const invalidField = formRef.current?.querySelector('input[aria-invalid="true"], textarea[aria-invalid="true"], select[aria-invalid="true"], button[aria-invalid="true"]');
    (invalidField || formRef.current?.querySelector("[data-submission-blocker]"))?.focus();
  }, [validationAttempt]);
  const canConfigure = settings?.can_configure || conference?.members?.some((member) => member.user_id === user?.user_id && member.role === "owner");
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setValidationAttempt((value) => value + 1);
    const metadataErrors = settings?.enabled ? validatePaperMetadata(metadata, settings.settings, submitForReview, settings.tracks) : {};
    if (!file || Object.keys(metadataErrors).length || uploadBlocked) return;
    setBusy(true); setError("");
    try {
      const suppliedMetadata = settings?.enabled && (metadata.title || metadata.abstract || metadata.authors.length || metadata.track_id) ? metadata : undefined;
      const paper = await createConferenceSubmission(confId, file, { submitForReview, metadata: suppliedMetadata });
      navigate(`/submissions/${paper.submission_id}`);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  const conferenceRequirements = (<details className="pf-card pf-inline-configuration"><summary>{creating ? "Conference requirements" : "Conference requirements and configuration"}</summary><div className="pf-stack">
      <ConferenceSettings confId={confId} data={settings} onChanged={setSettings} readOnly={creating} />
      <p><Link className="text-primary-600" to={`/conferences/${confId}/latest`}>Open conference templates →</Link></p>
      <ConferenceWorkflowPolicy confId={confId} readOnly={creating} />
      <ReviewConfiguration confId={confId} readOnly={creating} />
      {!creating && <ConferenceReviewProgress confId={confId} />}
      {creating && canConfigure && <p><Link className="text-primary-600" to={`/conferences/${confId}?tab=settings`}>Manage conference settings →</Link></p>}
      </div></details>);
  const visiblePapers = papers.filter((paper) => (!trackFilter || paper.track_id === trackFilter) && `${paper.title} ${paper.filename} #${paper.paper_number || ""}`.toLowerCase().includes(search.toLowerCase()));
  if (authLoading) return <p role="status">Loading account…</p>;
  if (!user) return <p><Link to="/login" className="text-primary-600">Sign in</Link> to access conference papers.</p>;
  return <div className={`pf-management pf-conference-content space-y-6${creating ? " pf-submission-page" : ""}`}>
    <Link to={creating ? `/conferences/${confId}/submissions` : "/conferences"} className="pf-back-link">{creating ? "← Conference papers" : "← Conferences"}</Link>
    <header className="pf-management-header"><div><p className="pf-eyebrow">{creating ? conference?.name || "CONFERENCE SUBMISSION" : "CONFERENCE SUBMISSIONS"}</p><h1>{creating ? "Submit a paper" : `${conference?.name || "Conference"} · Papers`}</h1><p>{creating ? "Add your paper details and manuscript." : "Follow submissions from the first upload through formatting checks and review."}</p></div>{!creating && <ButtonLink to={`/conferences/${confId}`}>Conference workspace →</ButtonLink>}</header>
    {loading ? <p role="status">{creating ? "Loading submission requirements…" : "Loading papers…"}</p> : loadError ? <section className="pf-message pf-message--error" role="alert">
      <h2>{creating ? "Submission requirements could not be loaded" : "Conference papers could not be loaded"}</h2><p>{loadError.message}</p>
      <p>{loadError.accessDenied ? "Check that you opened the correct conference and signed in with an invited account. Accept your conference invitation or ask a chair to add you as a participant." : "Check your connection and retry. If this continues, ask a chair to check that the conference is available."}</p>
      <button type="button" className="btn-secondary" onClick={() => setReload((value) => value + 1)}>Retry loading requirements</button>
    </section> : conference && <>
      {!creating && conferenceRequirements}
      {creating && <div className="pf-submission-layout">
      <form id="new-submission" ref={formRef} noValidate className="panel pf-conference-submission-form" onSubmit={submit}>
        <div className="pf-submission-form-heading"><h2>Paper details</h2><p>* Required</p></div>
        {validationAttempt > 0 && <SubmissionRequirements confId={confId} templateStatus={templateStatus} settings={settings} onReloadTemplates={() => setTemplateReload((value) => value + 1)} />}
        {settings?.enabled && <PaperMetadataFields value={metadata} onChange={setMetadata} tracks={settings.tracks} requirements={settings.settings} forReview={submitForReview} errors={fieldErrors} disabled={busy} />}
        <section className="pf-manuscript-section" aria-labelledby="manuscript-heading">
          <h2 id="manuscript-heading">Manuscript</h2>
          <SubmissionField id="paper-file" label="Paper file (PDF, DOCX or LaTeX)" required error={fieldErrors.file}>
            <input type="file" accept=".pdf,.docx,.tex,.latex" disabled={busy} onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </SubmissionField>
        </section>
        <label className="pf-review-option"><input type="checkbox" checked={submitForReview} disabled={busy} onChange={(e) => setSubmitForReview(e.target.checked)} /><span><strong>Submit for review after formatting checks</strong><small>If changes are needed, your paper stays in draft.</small></span></label>
        {error && <div role="alert" className="pf-message pf-message--error"><h3>Paper could not be submitted</h3><p>{error}</p><p>Your selected file and paper details are kept. Review the message and try again. If the error continues, share this message with a conference chair.</p></div>}
        <div className="pf-submission-form-footer"><Link to={`/conferences/${confId}/submissions`}>Cancel</Link><button className="btn-primary" disabled={busy}>{busy ? "Uploading and checking…" : "Create submission"}</button></div>
      </form>
      <aside id="submission-resources" className="pf-submission-resources" aria-label="Conference resources">
        <div className="pf-resources-intro"><h2>Conference resources</h2><p>Formatting rules and requirements for your paper.</p></div>
        <Link className="pf-template-resource" to={`/conferences/${confId}/latest`}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/></svg><span>View conference template →</span></Link>
        {conferenceRequirements}
      </aside>
      </div>}
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
