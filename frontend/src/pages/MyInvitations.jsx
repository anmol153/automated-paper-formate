import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Button, { ButtonLink } from "../components/ui/Button.jsx";
import Field from "../components/ui/Field.jsx";

export function invitationDestination(value, origin) {
  let url;
  try { url = new URL(value.trim(), origin); } catch { throw new Error("Paste a complete Paper-Format invitation link."); }
  const token = new URLSearchParams(url.hash.slice(1)).get("token");
  if (url.origin !== origin || url.pathname !== "/invitations" || !/^[A-Za-z0-9_-]{43}$/.test(token || "")) {
    throw new Error("Use a complete invitation link from this Paper-Format site. Ask the conference chair for a current link if needed.");
  }
  return `/invitations#${new URLSearchParams({ token })}`;
}

export default function MyInvitations() {
  const navigate = useNavigate();
  const [link, setLink] = useState("");
  const [error, setError] = useState("");
  return <div className="pf-management"><header className="pf-management-header"><div><p className="pf-eyebrow">YOUR CONFERENCE COMMUNITY</p><h1>My invitations</h1><p>Open a private invitation shared by a conference chair.</p></div><ButtonLink to="/conferences">Browse conferences →</ButtonLink></header>
    <div className="pf-form-layout"><form className="pf-card" onSubmit={(event) => {
      event.preventDefault(); setError("");
      try { navigate(invitationDestination(link, window.location.origin)); }
      catch (err) { setError(err.message); }
    }}><div className="pf-card-heading"><div><h2>Join a conference</h2><p>Check the conference and your invited role before accepting.</p></div></div><div className="pf-card-body pf-stack"><Field label="Invitation link" required hint="Paste the complete invitation link shared by the conference chair." error={error}><input type="text" autoComplete="off" spellCheck={false} value={link} onChange={(event) => { setLink(event.target.value); setError(""); }} placeholder={`${window.location.origin}/invitations#token=…`} /></Field><p className="pf-fine-print">Invitations are shared as private links. This page does not list pending invitations automatically.</p></div><div className="pf-form-footer"><Button type="submit" variant="primary" disabled={!link.trim()}>Open invitation →</Button></div></form>
    <aside className="pf-form-help"><span className="pf-eyebrow">BEFORE YOU JOIN</span><h2>A place for your next collaboration.</h2><p>Sign in with the email address that was invited. Opening the link lets you inspect the invitation; accepting is a separate step.</p><p className="pf-help-note">Don't have a link? Ask your conference chair to create one. Membership does not automatically assign papers for review.</p></aside></div>
  </div>;
}
