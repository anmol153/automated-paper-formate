import { useEffect, useRef, useState } from "react";
import { createConferenceInvitation, errorMessage, listConferenceInvitations, revokeConferenceInvitation } from "../lib/api.js";
import Button from "./ui/Button.jsx";
import Field from "./ui/Field.jsx";

const date = (value) => new Date(value * 1000).toLocaleString();
const roleLabel = (role) => role === "owner" ? "Chair" : role === "reviewer" ? "Reviewer" : "Author";

export default function ConferenceInvitations({ confId }) {
  return <InvitationManager key={confId} confId={confId} />;
}

function InvitationManager({ confId }) {
  const [data, setData] = useState(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("author");
  const [days, setDays] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null);
  const [copied, setCopied] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [search, setSearch] = useState("");
  const active = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => {
    let current = true; setError("");
    listConferenceInvitations(confId).then((value) => { if (current) setData(value); })
      .catch((err) => { if (current) setError(errorMessage(err)); });
    return () => { current = false; };
  }, [confId, refresh]);
  async function create(event) {
    event.preventDefault(); setBusy(true); setError(""); setCopied("");
    try {
      const result = await createConferenceInvitation(confId, { email: email.trim(), role, expires_in_days: days });
      if (!active.current) return;
      const link = new URL("/invitations", window.location.origin);
      link.hash = new URLSearchParams({ token: result.token }).toString();
      setCreated({ id: result.invitation.invitation_id, link: link.href, email: result.invitation.recipient_email, expires: result.invitation.expires_at });
      setEmail(""); setRefresh((value) => value + 1);
    } catch (err) { if (active.current) setError(errorMessage(err)); }
    finally { if (active.current) setBusy(false); }
  }
  async function revoke(id) {
    setBusy(true); setError("");
    try {
      await revokeConferenceInvitation(confId, id);
      if (active.current) { if (created?.id === id) setCreated(null); setRefresh((value) => value + 1); }
    } catch (err) { if (active.current) setError(errorMessage(err)); }
    finally { if (active.current) setBusy(false); }
  }
  const visible = data?.invitations.filter((item) => `${item.recipient_email} ${item.role} ${item.status}`.toLowerCase().includes(search.toLowerCase())) || [];
  return <section className="pf-management pf-invitations pf-stack" aria-label="Conference invitations">
    <div className="pf-section-intro"><div><span className="pf-eyebrow">BUILD YOUR CONFERENCE TEAM</span><h2>Invitations</h2><p>Give authors and reviewers a direct path into your conference.</p></div><span className="pf-status-chip">Private invitation links</span></div>
    {error && <div role="alert" className="pf-message pf-message--error">{error} <Button disabled={busy} onClick={() => setRefresh((value) => value + 1)}>Reload invitations</Button></div>}
    {!data ? !error && <div className="pf-card pf-empty" role="status">Loading invitations…</div> : !data.enabled ? <div className="pf-card pf-empty"><h3>Invitations are unavailable</h3><p>Conference invitations are not enabled yet. Ask the administrator to enable them; existing member management is available in People.</p></div> : <>
      <div className="pf-form-layout"><form className="pf-card" onSubmit={create}><div className="pf-card-heading"><div><h3>Invite participants</h3><p>Create a link for one participant and one conference role.</p></div></div><div className="pf-card-body pf-stack">
        <Field label="Recipient email" hint="The recipient must sign in using this email address." required><input type="email" autoComplete="off" maxLength={320} disabled={busy} value={email} onChange={(event) => setEmail(event.target.value)} /></Field>
        <div className="pf-form-grid"><Field label="Invitation role"><select disabled={busy} value={role} onChange={(event) => setRole(event.target.value)}><option value="author">Author</option><option value="reviewer">Reviewer</option></select></Field><Field label="Link expires after"><select disabled={busy} value={days} onChange={(event) => setDays(Number(event.target.value))}>{[1, 3, 7, 14, 30].map((number) => <option key={number} value={number}>{number} {number === 1 ? "day" : "days"}</option>)}</select></Field></div>
        <div className="pf-role-explainer"><strong>{roleLabel(role)} access</strong><p>{role === "reviewer" ? "Join as a reviewer. A chair must separately assign the papers to review." : "Join as an author. Paper submission remains subject to the conference's requirements and deadlines."}</p></div>
      </div><div className="pf-form-footer"><Button type="submit" variant="primary" busy={busy} disabled={!email.trim()}>{busy ? "Working…" : "Create invitation link"}</Button></div></form>
      <aside className="pf-form-help"><span className="pf-eyebrow">HOW INVITATIONS WORK</span><h2>Invite. Share. Collaborate.</h2><div className="pf-invite-steps"><div><span>01</span><p>Create a private link for the intended participant.</p></div><div><span>02</span><p>Copy the link and share it with them directly. No email is sent automatically.</p></div><div><span>03</span><p>They sign in with the invited email and explicitly accept.</p></div></div><p className="pf-help-note">Membership does not assign a paper or bypass conference deadlines. Expired or revoked links cannot be accepted.</p></aside></div>
      {created && <section className="pf-card pf-created-invitation"><div className="pf-card-heading"><div><h3>Your invitation link is ready</h3><p role="status">Invitation created for {created.email}. No email was sent automatically.</p></div><span className="pf-status-chip pf-status-chip--success">Created</span></div><div className="pf-card-body pf-stack"><Field label="Private invitation link" hint="Copy and share privately now. This link is shown only during this visit; it cannot be retrieved later. If lost, revoke it and create another."><input readOnly value={created.link} onFocus={(event) => event.target.select()} /></Field><div className="pf-preference-row"><p>Expires {date(created.expires)}</p><Button onClick={async () => { try { await navigator.clipboard.writeText(created.link); setCopied("Invitation link copied."); } catch { setCopied("Select the link above and copy it manually."); } }}>Copy invitation link</Button></div>{copied && <p role="status" className="pf-inline-status">{copied}</p>}</div></section>}
      <section className="pf-card"><div className="pf-list-toolbar"><div><h3>Invitation history <span className="pf-count">{data.invitations.length} loaded</span></h3><p>Track the status of links you've created. Raw links are never retrieved here.</p></div><label className="pf-search"><span className="sr-only">Search loaded invitations</span><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search email, role or status…" /></label></div>
        {!visible.length ? <div className="pf-empty"><span className="pf-empty-symbol" aria-hidden="true">↗</span><h3>{search ? "No matching invitations" : "No invitations yet."}</h3><p>{search ? "Search applies to loaded invitations. Clear the search or load older invitations below." : "Create your first invitation above to bring your conference team together."}</p>{search && <Button onClick={() => setSearch("")}>Clear invitation search</Button>}</div> : <><div className="pf-invitation-columns" aria-hidden="true"><span>Participant</span><span>Status</span><span>Expires</span><span>Action</span></div><ul className="pf-invitation-history">{visible.map((item) => <li className="pf-invitation-row" key={item.invitation_id}><div><strong>{item.recipient_email}</strong><p>{roleLabel(item.role)} · Created {date(item.created_at)}</p>{item.accepted_at && <p>Accepted {date(item.accepted_at)}</p>}</div><span className={`pf-status-chip${item.status === "accepted" ? " pf-status-chip--success" : item.status === "pending" ? " pf-status-chip--attention" : ""}`}>{item.status}</span><time dateTime={new Date(item.expires_at * 1000).toISOString()}>{date(item.expires_at)}</time><div>{["pending", "invalidated"].includes(item.status) ? <Button variant="quiet" disabled={busy} onClick={() => revoke(item.invitation_id)}>Revoke invitation<span className="sr-only"> for {item.recipient_email}</span></Button> : <span className="pf-muted">—</span>}</div></li>)}</ul></>}
        {data.next_cursor && <div className="pf-form-footer"><Button disabled={busy} onClick={async () => {
          setBusy(true); setError("");
          try { const older = await listConferenceInvitations(confId, data.next_cursor); if (active.current) setData((current) => ({ ...older, invitations: [...current.invitations, ...older.invitations] })); }
          catch (err) { if (active.current) setError(errorMessage(err)); }
          finally { if (active.current) setBusy(false); }
        }}>Load older invitations</Button></div>}
      </section>
    </>}
  </section>;
}
