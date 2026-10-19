import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { completeGoogleSignIn, createGoogleChallenge, errorMessage, getGoogleSignInConfig } from "../lib/api.js";
import { loadGoogleIdentity } from "../lib/googleIdentity.js";
import { useAuth } from "../context/AuthContext.jsx";

export default function GoogleSignIn({ mode = "login", onConnected, onSignedIn }) {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [password, setPassword] = useState("");
  const container = useRef(null);
  const active = useRef(false);
  const attempt = useRef(0);
  const connected = useRef(onConnected);
  connected.current = onConnected;
  const signedIn = useRef(onSignedIn);
  signedIn.current = onSignedIn;

  useEffect(() => {
    active.current = true;
    getGoogleSignInConfig().then((data) => { if (active.current) setConfig(data); })
      .catch((err) => { if (active.current) setError(errorMessage(err)); });
    return () => { active.current = false; attempt.current += 1; };
  }, []);

  async function prepare(confirmationPassword) {
    const currentAttempt = ++attempt.current;
    setBusy(true); setReady(false); setError("");
    container.current?.replaceChildren();
    try {
      const [identity, challenge] = await Promise.all([loadGoogleIdentity(), createGoogleChallenge(confirmationPassword)]);
      if (!active.current || currentAttempt !== attempt.current) return;
      setPassword("");
      identity.initialize({
        client_id: challenge.client_id, nonce: challenge.nonce, ux_mode: "popup", auto_select: false, button_auto_select: false,
        callback: async ({ credential }) => {
          if (!active.current || currentAttempt !== attempt.current) return;
          // One callback per local attempt, even if the browser delivers twice.
          attempt.current += 1;
          setBusy(true); setReady(false); container.current?.replaceChildren();
          try {
            if (!credential) throw new Error("Google did not return a sign-in credential. Try again.");
            await completeGoogleSignIn(challenge.challenge_id, credential);
            if (!active.current) return;
            const user = await refresh();
            if (!user) throw new Error("Your browser could not establish a session. Please enable cookies and try again.");
            if (mode === "link") connected.current?.(); else if (signedIn.current) signedIn.current(user); else navigate("/dashboard");
          } catch (err) {
            if (active.current) {
              setError(errorMessage(err));
              // An invalid Google token is not proof that the app session expired.
              if (mode === "link") await refresh().catch(() => {});
            }
          } finally { if (active.current) setBusy(false); }
        },
      });
      const buttonWidth = Math.max(200, Math.min(300, container.current?.parentElement?.clientWidth || 300));
      identity.renderButton(container.current, { type: "standard", theme: "outline", size: "large", text: "continue_with", shape: "rectangular", width: buttonWidth });
      setReady(true);
    } catch (err) { if (active.current && currentAttempt === attempt.current) setError(errorMessage(err)); }
    finally { if (active.current && currentAttempt === attempt.current) setBusy(false); }
  }

  // One active Google button on a page. A retry uses a fresh nonce/configuration.
  useEffect(() => { if (config?.enabled && mode === "login") prepare(); }, [config?.enabled, mode]);

  return <div className="space-y-3" aria-label={mode === "link" ? "Connect Google account" : "Google sign-in"}>
    <h2 className="font-semibold">{mode === "link" ? "Connect your Google account" : "Continue with Google"}</h2>
    {!config && !error && <p role="status">Loading Google sign-in…</p>}
    {config && !config.enabled && <><button className="btn-secondary" type="button" disabled>Continue with Google</button><p className="text-sm text-surface-500">Google sign-in is currently unavailable. You can use email and password.</p></>}
    {mode === "link" && config?.enabled && !ready && <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); prepare(password); }}>
      <p className="text-sm">Confirm your Paper-Format password, then choose the Google account you want to connect.</p>
      <label className="block">Current password<input className="input-base mt-1" type="password" autoComplete="current-password" required maxLength={72} value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} /></label>
      <button className="btn-secondary" disabled={busy || !password}>Confirm password and continue</button>
    </form>}
    {busy && <p role="status">Loading Google sign-in…</p>}
    {ready && mode === "link" && <p className="text-sm">Choose and confirm your Google account below.</p>}
    <div ref={container} className="min-h-0" aria-label="Google account chooser" />
    {error && <p role="alert" className="text-danger-600">{error}</p>}
    {error && (mode === "login" || !config) && <button className="btn-secondary" type="button" disabled={busy} onClick={() => { setError(""); if (config?.enabled) prepare(); else getGoogleSignInConfig().then(setConfig).catch((err) => setError(errorMessage(err))); }}>Retry Google sign-in</button>}
    {ready && <button type="button" className="text-sm text-primary-600" disabled={busy} onClick={() => { attempt.current += 1; setReady(false); container.current?.replaceChildren(); if (mode === "login") prepare(); }}>Restart Google sign-in</button>}
    {mode === "login" && config?.enabled && <p className="text-xs text-surface-500">If you already use a password here, sign in with it first and connect Google in Account settings.</p>}
  </div>;
}
