import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { errorMessage, getGoogleConnection } from "../lib/api.js";
import GoogleSignIn from "../components/GoogleSignIn.jsx";
import Button, { ButtonLink } from "../components/ui/Button.jsx";
import Field from "../components/ui/Field.jsx";
import ThemeToggle from "../components/ThemeToggle.jsx";

export default function Account() {
  const { user, loading } = useAuth();
  const [connection, setConnection] = useState(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [copyStatus, setCopyStatus] = useState("");
  useEffect(() => {
    if (!user) return;
    let active = true;
    getGoogleConnection().then((data) => { if (active) setConnection(data); })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [user, refresh]);
  if (loading) return <p role="status">Loading account…</p>;
  if (!user) return <div className="pf-management pf-card pf-empty"><h1>Account settings</h1><p>Sign in to manage your account.</p><ButtonLink variant="primary" to="/login">Sign in</ButtonLink></div>;
  return <div className="pf-management pf-settings-page">
    <header className="pf-management-header"><div><p className="pf-eyebrow">PERSONAL WORKSPACE</p><h1>Account settings</h1><p>Your identity, conference access and connected accounts.</p></div><ButtonLink to="/dashboard">Back to dashboard →</ButtonLink></header>
    <div className="pf-settings-layout"><aside className="pf-settings-index"><div className="pf-account-summary"><span className="pf-avatar" aria-hidden="true">{(user.full_name || user.email).slice(0, 2).toUpperCase()}</span><strong>{user.full_name || "Your account"}</strong><span>{user.email}</span></div><nav aria-label="Account settings sections"><a href="#profile">Profile</a><a href="#conference-access">Conference access</a><a href="#connected-accounts">Connected accounts</a><a href="#appearance">Appearance</a></nav><p>One account. A separate role in every conference.</p></aside>
    <div className="pf-stack"><section id="profile" className="pf-card"><div className="pf-card-heading"><div><h2>Profile</h2><p>The identity attached to your papers and memberships.</p></div><span className="pf-count">Account details</span></div><div className="pf-card-body"><dl className="pf-profile-details"><div><dt>Full name</dt><dd>{user.full_name || "Not provided"}</dd></div><div><dt>Email address</dt><dd>{user.email}</dd></div></dl></div></section>
    <section id="conference-access" className="pf-card"><div className="pf-card-heading"><div><h2>Conference access</h2><p>Help a conference chair find your account.</p></div></div><div className="pf-card-body pf-stack">
      <Field label="Your account ID" hint="Share this ID with a conference chair to be added as an author or reviewer. Your role is assigned separately for each conference."><input readOnly value={user.user_id} onFocus={(event) => event.target.select()} /></Field>
      <div><Button onClick={async () => {
        try { await navigator.clipboard.writeText(user.user_id); setCopyStatus("Account ID copied."); }
        catch { setCopyStatus("Select the account ID above and copy it manually."); }
      }}>Copy account ID</Button></div>{copyStatus && <p role="status" className="pf-inline-status">{copyStatus}</p>}
    </div></section>
    <section id="connected-accounts" className="pf-card"><div className="pf-card-heading"><div><h2>Connected accounts</h2><p>Another way to sign in to the same research workspace.</p></div></div><div className="pf-card-body pf-stack">
      {error && <div role="alert" className="pf-message pf-message--error">{error} <Button onClick={() => { setError(""); setConnection(null); setRefresh((n) => n + 1); }}>Reload</Button></div>}
      {!connection ? !error && <p role="status">Loading connected accounts…</p> : connection.connected ? <div className="pf-connection-row"><span className="pf-provider-mark" aria-hidden="true">G</span><div><h3>Google account connected</h3><p>{connection.email_at_link}</p><small>Connected {new Date(connection.linked_at).toLocaleString()}. This address was recorded when you connected Google.</small></div><span className="pf-status-chip pf-status-chip--success">Connected</span></div> : <GoogleSignIn mode="link" onConnected={() => { setConnection(null); setRefresh((n) => n + 1); }} />}
      <p className="pf-fine-print">Your papers and conference memberships stay with this Paper-Format account. Google sign-in does not grant conference membership or access to Google Drive files.</p>
    </div></section>
    <section id="appearance" className="pf-card"><div className="pf-card-heading"><div><h2>Appearance</h2><p>Choose a comfortable workspace for this browser.</p></div></div><div className="pf-card-body pf-preference-row"><div><h3>Light and dark theme</h3><p>Your preference is saved on this device.</p></div><ThemeToggle /></div></section>
    </div></div>
  </div>;
}
