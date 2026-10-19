import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import { acceptInvitation, errorMessage, inspectInvitation } from '../lib/api.js';
import Login from './Login.jsx';
import Button, { ButtonLink } from '../components/ui/Button.jsx';

function InvitationFrame({ children }) {
  return <div className="pf-management pf-invitation-page"><header className="pf-invitation-preamble"><span className="pf-eyebrow">PAPER-FORMAT · CONFERENCE ACCESS</span><p>A new place for your research community.</p></header><div className="pf-invitation-layout"><div>{children}</div><aside className="pf-form-help"><span className="pf-eyebrow">JOIN THE CONVERSATION</span><h2>Your next collaboration starts here.</h2><p>An invitation gives your account a role in one conference. Your existing papers and memberships stay with you.</p><div className="pf-invite-steps"><div><span>01</span><p>Use the email address the chair invited.</p></div><div><span>02</span><p>Check the conference and the role before accepting.</p></div><div><span>03</span><p>Open the conference to see its submission and review requirements.</p></div></div><p className="pf-help-note">Reviewer assignments and conference deadlines are managed separately.</p></aside></div></div>;
}

export default function Invitation() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get('token');
  const accepted = location.state?.invitationAccepted;
  if (loading) return <p role="status">Loading account…</p>;
  if (accepted?.user_id === user?.user_id && user) return <InvitationFrame><section className="pf-card pf-invitation-state pf-stack">
    <span className="pf-invitation-seal is-success" aria-hidden="true">✓</span><h1>Invitation accepted</h1>
    <p>You have {accepted.membership_role} access to {accepted.conference_name}.</p>
    <ButtonLink variant="primary" to={`/conferences/${accepted.conference_id}/submissions`}>Open conference papers</ButtonLink>
    <p>Reviewer assignments and submission deadlines are managed separately by the conference.</p>
  </section></InvitationFrame>;
  if (!token || !/^[A-Za-z0-9_-]{43}$/.test(token)) return <InvitationFrame><section className="pf-card pf-invitation-state pf-stack"><span className="pf-invitation-seal" aria-hidden="true">↗</span><h1>Conference invitation</h1><p role="alert">This page needs a complete invitation link. Ask a chair to share a current link.</p><ButtonLink to="/conferences">Browse conferences</ButtonLink></section></InvitationFrame>;
  if (!user) return <InvitationFrame><div className="pf-stack"><div className="pf-card pf-card-body"><h1>Join a conference</h1><p className="pf-section-description">Sign in or create an account below using the invited email address. Signing in does not accept the invitation.</p></div><Login onSignedIn={() => {}} /></div></InvitationFrame>;
  return <Acceptance key={`${token}:${user.user_id}`} token={token} user={user} />;
}

function Acceptance({ token, user }) {
  const navigate = useNavigate();
  const [invitation, setInvitation] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setError(''); setInvitation(null);
    inspectInvitation(token).then((value) => { if (active) setInvitation(value); })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [token, refresh]);
  return <InvitationFrame><section className="pf-card" aria-label="Accept conference invitation">
    <div className="pf-card-heading"><div><span className="pf-eyebrow">YOU'RE INVITED</span><h1>Conference invitation</h1></div></div><div className="pf-card-body pf-stack">
    <div className="pf-signed-in-note"><span className="pf-avatar pf-avatar--small" aria-hidden="true">{user.email.slice(0, 2).toUpperCase()}</span><div><strong>Signed in as {user.email}</strong><p>If this is not the invited address, sign out above and open the invitation link again.</p></div></div>
    {error && <div role="alert" className="pf-message pf-message--error">{error} <Button disabled={busy} onClick={() => setRefresh((value) => value + 1)}>Check invitation again</Button></div>}
    {!invitation ? !error && <p role="status">Loading invitation…</p> : <>
      <div className="pf-invited-conference"><span className="pf-invitation-seal" aria-hidden="true">↗</span><h2>{invitation.conference_name}</h2><span className="pf-status-chip">Invited role: {invitation.role}</span></div>
      <p className="pf-fine-print">Expires {new Date(invitation.expires_at * 1000).toLocaleString()}</p>
      <p>Accepting adds this account to the conference. It does not assign you a paper, publish a review, or change any existing role.</p>
      <div className="pf-invitation-accept"><Button variant="primary" busy={busy} onClick={async () => {
        setBusy(true); setError('');
        try {
          const result = await acceptInvitation(token);
          navigate('/invitations', { replace: true, state: { invitationAccepted: { ...result, user_id: user.user_id } } });
        } catch (err) { setError(errorMessage(err)); }
        finally { setBusy(false); }
      }}>{busy ? 'Accepting…' : invitation.status === 'accepted' ? 'Open accepted invitation' : 'Accept invitation'}</Button></div>
    </>}
  </div></section></InvitationFrame>;
}
