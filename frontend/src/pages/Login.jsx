import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage, login, register } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import GoogleSignIn from "../components/GoogleSignIn.jsx";
import Button from "../components/ui/Button.jsx";
import Field from "../components/ui/Field.jsx";

export default function Login({ onSignedIn }) {
  const [createAccount, setCreateAccount] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const { refresh } = useAuth();
  const navigate = useNavigate();
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (createAccount) await register(email, password, name);
      await login(email, password);
      const current = await refresh();
      if (!current) throw new Error("Your browser could not establish a session. Please enable cookies and try again.");
      if (onSignedIn) onSignedIn(current); else navigate("/dashboard");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  const form = <section className="pf-auth-card" aria-label={createAccount ? "Create your account" : "Sign in to Paper-Format"}>
    <div className="pf-auth-card-heading"><span className="pf-eyebrow">{createAccount ? "JOIN YOUR RESEARCH COMMUNITY" : "WELCOME BACK"}</span><h1>{createAccount ? "Create an account" : "Sign in"}</h1><p>{createAccount ? "One account for your papers, reviews and conferences." : "Continue to your Paper-Format workspace."}</p></div>
    {error && <div className="pf-auth-error" role="alert">{error}</div>}
    <form onSubmit={submit} className="pf-auth-form">
      {createAccount && <Field label="Full name"><input autoComplete="name" required disabled={busy} value={name} onChange={(e) => setName(e.target.value)} placeholder="Your full name" /></Field>}
      <Field label="Email"><input type="email" autoComplete="username" required disabled={busy} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@university.edu" /></Field>
      <div className="pf-auth-password"><Field label="Password" hint={createAccount ? "Use at least 8 characters." : undefined}><input type={showPassword ? "text" : "password"} autoComplete={createAccount ? "new-password" : "current-password"} minLength={createAccount ? 8 : undefined} maxLength={72} required disabled={busy} value={password} onChange={(e) => setPassword(e.target.value)} /></Field><button type="button" className="pf-password-toggle" disabled={busy} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword((value) => !value)}>{showPassword ? "Hide" : "Show"}</button></div>
      <Button type="submit" variant="primary" busy={busy}>{busy ? "Please wait…" : createAccount ? "Create account" : "Sign in"}</Button>
    </form>
    <div className="pf-auth-separator"><span>or</span></div>
    <div className="pf-auth-google"><GoogleSignIn onSignedIn={onSignedIn} /></div>
    <div className="pf-auth-switch"><span>{createAccount ? "Already have an account?" : "New to Paper-Format?"}</span><button type="button" disabled={busy} onClick={() => { setCreateAccount(!createAccount); setShowPassword(false); setError(""); }}>{createAccount ? "Use an existing account" : "Create an account"}</button></div>
    <p className="pf-auth-role-note">Your role is assigned separately for each conference.</p>
  </section>;
  if (onSignedIn) return <div className="pf-management pf-auth-embedded">{form}</div>;
  return <div className="pf-management pf-auth-layout"><aside className="pf-auth-introduction"><span className="pf-eyebrow">THE RESEARCH WORKSPACE</span><h2>A clear path from<br />paper to peer review.</h2><p>Bring your manuscripts, collaborators and conference reviews together.</p><div className="pf-auth-benefits">{[["01", "Your papers, together", "Follow submissions, formatting checks and every revision."], ["02", "A shared review workspace", "Discuss research and respond to feedback in context."], ["03", "One account, every conference", "Join as an author, reviewer or conference chair."]].map(([number, title, text]) => <div key={number}><span aria-hidden="true">{number}</span><div><h3>{title}</h3><p>{text}</p></div></div>)}</div><p className="pf-auth-intro-footnote">Built for the work behind the research.</p></aside>{form}</div>;
}
