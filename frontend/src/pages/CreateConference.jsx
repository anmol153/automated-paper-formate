import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { createConference, errorMessage } from "../lib/api.js";
import Button, { ButtonLink } from "../components/ui/Button.jsx";

export default function CreateConference() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", description: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault(); if (!user || busy || !form.name.trim()) return;
    setBusy(true); setError("");
    try { const conference = await createConference({ name: form.name.trim(), description: form.description.trim() }); navigate(`/conferences/${conference.conference_id}?created=1`); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <div className="pf-management"><Link className="pf-back-link" to="/conferences">← Conferences</Link><header className="pf-management-header"><div><p className="pf-eyebrow">CONFERENCE SETUP</p><h1>Create a conference</h1><p>Start with the essentials. Add your dates, tracks and submission rules next.</p></div></header>
    <div className="pf-form-layout"><form className="pf-card pf-form-card" onSubmit={submit}><div className="pf-card-heading"><div><h2>Conference details</h2><p>Help authors and reviewers recognize your event.</p></div><span className="pf-step-label">STEP 1 OF 2</span></div><div className="pf-card-body pf-stack">
      {loading ? <p role="status">Loading account…</p> : !user && <div className="pf-message">You need an account to create a conference. <Link to="/login">Sign in to continue</Link>.</div>}
      {error && <div role="alert" className="pf-message pf-message--error">{error}</div>}
      <div className="pf-form-field"><label htmlFor="conference-name">Conference name <span aria-hidden="true">*</span></label><input id="conference-name" aria-describedby="conference-name-hint" name="name" required maxLength={200} autoComplete="organization" placeholder="e.g. International Conference on Machine Learning" value={form.name} disabled={busy || !user} onChange={(e) => setForm({ ...form, name: e.target.value })} /><small id="conference-name-hint">Use the full name of your conference. You can add an abbreviation in settings.</small></div>
      <div className="pf-form-field"><label htmlFor="conference-description">Description</label><textarea id="conference-description" aria-describedby="conference-description-hint" name="description" rows={6} maxLength={20000} placeholder="Tell participants about the conference and its research focus…" value={form.description} disabled={busy || !user} onChange={(e) => setForm({ ...form, description: e.target.value })} /><small id="conference-description-hint">This description appears in the conference directory. Keep confidential information out of it.</small></div>
    </div><div className="pf-form-footer"><ButtonLink to="/conferences">Cancel</ButtonLink><Button type="submit" variant="primary" busy={busy} disabled={!user || !form.name.trim()}>{busy ? "Creating…" : "Create conference"}</Button></div></form>
    <aside className="pf-form-help"><span className="pf-eyebrow">A GOOD START</span><h2>Your conference, your workflow.</h2><p>You'll become the conference chair when you create it.</p><ol><li><strong>Set the essentials</strong><span>Name your event and introduce its scope.</span></li><li><strong>Make it submission-ready</strong><span>Configure dates, publish a template and set review requirements.</span></li><li><strong>Bring your team together</strong><span>Invite chairs, authors and reviewers from the People tab.</span></li></ol><p className="pf-help-note">Creating a conference does not publish a formatting template or open submissions automatically.</p></aside></div></div>;
}
