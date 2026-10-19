import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { errorMessage } from "../lib/api.js";

export default function SessionControls() {
  const { user, loading, signOut } = useAuth();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (loading) return null;
  if (!user) return <Link className="btn-secondary" to="/login">Sign in</Link>;
  return <div className="flex items-center gap-2">
    <Link className="btn-secondary" to="/account">Account</Link>
    <span className="hidden sm:inline text-sm">{user.full_name}</span>
    <button className="btn-secondary" disabled={busy} onClick={async () => {
      setBusy(true);
      try { await signOut(); } catch (err) { setError(errorMessage(err)); }
      finally { setBusy(false); }
    }}>Sign out</button>
    {error && <span role="alert" className="text-sm text-danger">{error}</span>}
  </div>;
}
