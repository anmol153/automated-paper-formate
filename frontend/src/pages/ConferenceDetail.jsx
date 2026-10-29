import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { errorMessage, getConference, getConferenceSettings, updateConference } from "../lib/api.js";
import Button, { ButtonLink } from "../components/ui/Button.jsx";
import ConferenceSettings from "../components/ConferenceSettings.jsx";
import ConferenceTemplates from "../components/ConferenceTemplates.jsx";
import ConferencePeople from "../components/ConferencePeople.jsx";
import ConferenceInvitations from "../components/ConferenceInvitations.jsx";
import ConferenceWorkflowPolicy from "../components/ConferenceWorkflowPolicy.jsx";
import ReviewConfiguration from "../components/ReviewConfiguration.jsx";
import ConferenceReviewProgress from "../components/ConferenceReviewProgress.jsx";
import { AccessRequestForm } from "../components/ConferenceAccess.jsx";

export default function ConferenceDetail() {
  const { confId } = useParams();
  return <ConferenceWorkspace key={confId} confId={confId} />;
}
function ConferenceWorkspace({ confId }) {
  const { user, loading: authLoading } = useAuth();
  const [params, setParams] = useSearchParams();
  const tabs = ["overview", "settings", "templates", "people", "invitations", "reviews"];
  const tab = tabs.includes(params.get("tab")) ? params.get("tab") : "overview";
  const [conference, setConference] = useState(null);
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState("");
  const [membershipRequired, setMembershipRequired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [form, setForm] = useState({ name: "", description: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (!user) return;
    let active = true; setLoading(true); setError("");
    Promise.all([getConference(confId), getConferenceSettings(confId)]).then(([conf, config]) => { if (active) { setConference(conf); setForm({ name: conf.name, description: conf.description || "" }); setSettings(config); setMembershipRequired(false); } }).catch((err) => { if (active) { setError(errorMessage(err)); setMembershipRequired(err?.response?.status === 404); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [confId, user, attempt]);
  const chair = conference?.members?.some((member) => member.user_id === user?.user_id && member.role === "owner") || false;
  function selectTab(value) { setParams((prev) => { const next = new URLSearchParams(prev); next.set("tab", value); next.delete("created"); return next; }); }
  if (authLoading) return <p role="status">Loading account…</p>;
  if (!user) return <div className="pf-management pf-empty"><h1>Conference workspace</h1><p>Sign in with a conference member account to continue.</p><ButtonLink variant="primary" to="/login">Sign in</ButtonLink></div>;
  return <div className="pf-management"><Link className="pf-back-link" to="/conferences">← Conferences</Link>
    {loading ? <div className="pf-empty" role="status">Loading conference…</div> : !conference ? <div className="pf-stack"><div className="pf-card pf-empty"><h1>{membershipRequired ? "Conference access required" : "Conference unavailable"}</h1><p role={membershipRequired ? "status" : "alert"}>{membershipRequired ? "You need conference membership to open this workspace." : error}</p>{!membershipRequired && <Button onClick={() => setAttempt((n) => n + 1)}>Retry conference</Button>}</div>{membershipRequired && <AccessRequestForm confId={confId} />}</div> : <>
      <header className="pf-management-header"><div><p className="pf-eyebrow">CONFERENCE WORKSPACE {chair && "· CHAIR"}</p><h1>{conference.name}</h1><p>{conference.description || "Your conference workspace for papers, people and peer review."}</p></div><ButtonLink variant="primary" to={`/conferences/${confId}/submissions`}>View papers →</ButtonLink></header>
      {params.get("created") === "1" && <div role="status" className="pf-message pf-created"><strong>Your conference is created.</strong> Next, configure your dates and publish a formatting template.<Button onClick={() => selectTab("settings")}>Continue setup →</Button></div>}
      <nav className="pf-workspace-tabs" aria-label="Conference sections">{tabs.filter((value) => value !== "invitations" || chair).map((value) => <Link key={value} to={`?tab=${value}`} aria-current={tab === value ? "page" : undefined}>{value[0].toUpperCase() + value.slice(1)}</Link>)}</nav>
      <div className="pf-conference-content" key={tab}>
      {tab === "overview" && <div className="pf-dashboard-columns"><section className="pf-card"><div className="pf-card-heading"><div><h2>Conference overview</h2><p>Your event at a glance.</p></div><span className="pf-count">{settings?.settings.lifecycle_status || "Not configured"}</span></div><div className="pf-card-body pf-stack"><p className="pf-preserve-text">{conference.description || "No description added yet."}</p>{settings?.settings.research_scope && <><h3>Research scope</h3><p className="pf-preserve-text">{settings.settings.research_scope}</p></>}<dl className="pf-detail-list"><div><dt>Abbreviation</dt><dd>{settings?.settings.abbreviation || "Not set"}</dd></div><div><dt>Submission window</dt><dd>{settings?.enabled ? settings.submission_window.allowed ? "Open" : "Closed" : "Not configured"}</dd></div><div><dt>Submission deadline</dt><dd>{settings?.settings.submissions_close_at ? new Date(settings.settings.submissions_close_at).toLocaleString() : "No date configured"}</dd></div><div><dt>Tracks</dt><dd>{settings?.tracks.length || 0}</dd></div></dl><ButtonLink to={`/conferences/${confId}/submit`}>Submit a paper →</ButtonLink></div></section><aside className="pf-card"><div className="pf-card-heading"><div><h2>{chair ? "Set up your conference" : "Conference resources"}</h2><p>{chair ? "Build the workflow in a few focused steps." : "Requirements and participant information."}</p></div></div><div className="pf-setup-links">{[["01", "Dates & requirements", "Define the submission window and tracks", "settings"], ["02", "Formatting template", "Publish the rules used to check papers", "templates"], ["03", "People & invitations", "Bring your conference community together", "people"], ["04", "Review workflow", "Criteria, formatting gates and progress", "reviews"]].map(([number, title, hint, target]) => <Link to={`?tab=${target}`} key={target}><span>{number}</span><div><strong>{title}</strong><small>{hint}</small></div><span aria-hidden="true">→</span></Link>)}</div></aside></div>}
      {tab === "settings" && <div className="pf-form-layout"><div className="pf-stack">{chair && <form className="pf-card" onSubmit={async (event) => { event.preventDefault(); setBusy(true); setError(""); setMessage(""); try { const conf = await updateConference(confId, { name: form.name.trim(), description: form.description }); setConference(conf); setMessage("Conference details saved."); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); } }}><div className="pf-card-heading"><h2>Conference identity</h2></div><div className="pf-card-body pf-stack">{error && <p role="alert" className="pf-message pf-message--error">{error}</p>}{message && <p role="status" className="pf-message">{message}</p>}<label className="pf-form-field">Conference name<input required maxLength={200} value={form.name} disabled={busy} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label className="pf-form-field">Description<textarea rows={4} maxLength={20000} value={form.description} disabled={busy} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label></div><div className="pf-form-footer"><Button type="submit" variant="primary" busy={busy} disabled={!form.name.trim()}>Save Changes</Button></div></form>}<ConferenceSettings confId={confId} data={settings} onChanged={setSettings} expanded /></div><aside className="pf-form-help"><span className="pf-eyebrow">SUBMISSION READINESS</span><h2>Make the requirements clear.</h2><p>Configure the submission window and required paper metadata. Publish the formatting template in its own tab.</p><p>Times are entered in your local timezone and stored as UTC. Archived conferences cannot be reconfigured.</p><Link to="?tab=templates">Open formatting templates →</Link></aside></div>}
      {tab === "templates" && <ConferenceTemplates confId={confId} canPublish={chair} />}
      {tab === "people" && <ConferencePeople conference={conference} onChanged={setConference} canManage={chair} showInvitations={false} />}
      {tab === "invitations" && (chair ? <ConferenceInvitations confId={confId} /> : <div className="pf-card pf-empty"><h2>Chair access required</h2><p>Conference invitations are managed by the conference chairs.</p></div>)}
      {tab === "reviews" && <div className="pf-stack"><ConferenceWorkflowPolicy confId={confId} /><ReviewConfiguration confId={confId} /><ConferenceReviewProgress confId={confId} /></div>}
      </div>
    </>}
  </div>;
}
