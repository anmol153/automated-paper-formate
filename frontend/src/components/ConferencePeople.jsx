import { useState } from "react";
import { Link } from "react-router-dom";
import ConferenceInvitations from "./ConferenceInvitations.jsx";
import { addConferenceMember, errorMessage, getConference, removeConferenceMember } from "../lib/api.js";
import Button from "./ui/Button.jsx";
import { ConferenceAccessRequests } from "./ConferenceAccess.jsx";

export default function ConferencePeople({ conference, onChanged, canManage, showInvitations = true }) {
  const [form, setForm] = useState({ userId: "", role: "author" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function change(operation, success) {
    setBusy(true); setError(""); setMessage("");
    try { await operation(); onChanged(await getConference(conference.conference_id)); setMessage(success); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <div className="pf-stack"><section className="pf-card"><div className="pf-card-heading"><div><h2>Conference people</h2><p>Membership grants conference access. Assign reviewers to individual papers separately.</p></div></div><div className="pf-card-body pf-stack">
    {error && <p role="alert" className="pf-message pf-message--error">{error}</p>}{message && <p role="status" className="pf-message">{message}</p>}
    {!canManage && <p>Conference membership is managed by its chairs.</p>}
    {conference.members?.map((member) => <div className="pf-member-row" key={member.user_id}><code>{member.user_id}</code><span className="pf-count">{member.role === "owner" ? "Chair" : member.role}</span>{canManage && <Button disabled={busy} onClick={() => { if (window.confirm(`Remove ${member.user_id} from this conference?`)) change(() => removeConferenceMember(conference.conference_id, member.user_id), "Member removed."); }}>Remove</Button>}</div>)}
    {canManage && <ConferenceAccessRequests confId={conference.conference_id} />}
    {canManage && <form className="pf-stack pf-section-divider" onSubmit={(event) => { event.preventDefault(); change(async () => { await addConferenceMember(conference.conference_id, form.userId.trim(), form.role); setForm({ userId: "", role: "author" }); }, "Member added."); }}><h3>Add an existing participant</h3><p>Ask the participant to copy their account ID from <Link to="/account">Account settings</Link>, or use an invitation below.</p><div className="pf-form-grid"><label className="pf-form-field">User ID<input required value={form.userId} disabled={busy} onChange={(e) => setForm({ ...form, userId: e.target.value })} /></label><label className="pf-form-field">Role<select value={form.role} disabled={busy} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="author">Author</option><option value="reviewer">Reviewer</option><option value="owner">Chair</option></select></label></div><div><Button type="submit" variant="primary" disabled={busy || !form.userId.trim()}>Add Member</Button></div></form>}
  </div></section>{canManage && (showInvitations ? <ConferenceInvitations confId={conference.conference_id} /> : <div className="pf-help-strip"><strong>Invite someone new</strong><span>Create a private invitation link for an author or reviewer.</span><Link to="?tab=invitations">Manage invitations →</Link></div>)}</div>;
}
