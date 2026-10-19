import { useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { errorMessage } from "../../lib/api.js";
import { NavigationIcon } from "./AppNavigation.jsx";

const entries = [
  { label: "Settings", to: "/account", icon: "M12 8a4 4 0 110 8 4 4 0 010-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z" },
  { label: "My Invitations", to: "/my-invitations", icon: "M3 5h18v14H3zM3 6l9 7 9-7" },
  { label: "My Schedule", to: "/my-schedule", icon: "M4 5h16v16H4zM8 3v4m8-4v4M4 11h16M8 15h2m4 0h2" },
  { label: "Docs", to: "/docs", icon: "M5 3h10l4 4v14H5zM14 3v5h5M9 12h6m-6 4h6" },
];

export default function AccountMenu({ placement = "sidebar", onNavigate }) {
  const { user, loading, signOut } = useAuth();
  const location = useLocation();
  const id = useId();
  const root = useRef(null), trigger = useRef(null), popup = useRef(null), focusLast = useRef(false);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setOpen(false); }, [location.key, user?.user_id]);
  useEffect(() => {
    if (!open) return;
    const outside = (event) => { if (!root.current?.contains(event.target)) setOpen(false); };
    const resize = () => setOpen(false);
    document.addEventListener("pointerdown", outside, true);
    window.addEventListener("resize", resize);
    const controls = popup.current?.querySelectorAll('[role="menuitem"]');
    (focusLast.current ? controls?.[controls.length - 1] : controls?.[0])?.focus();
    return () => { document.removeEventListener("pointerdown", outside, true); window.removeEventListener("resize", resize); };
  }, [open]);
  if (loading) return null;
  if (!user) return <Link to="/login" className="pf-account-sign-in" onClick={onNavigate}><NavigationIcon path="M10 17l5-5-5-5M15 12H3M14 3h7v18h-7" /><span>Sign in</span></Link>;
  const name = user.full_name || user.email;
  const initials = name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  function close(restore = false) { setOpen(false); if (restore) trigger.current?.focus(); }
  function keyboard(event) {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(true); return; }
    const controls = [...popup.current.querySelectorAll('[role="menuitem"]')].filter((node) => !node.disabled);
    const index = controls.indexOf(document.activeElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const target = event.key === "Home" ? 0 : event.key === "End" ? controls.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + controls.length) % controls.length;
      controls[target]?.focus();
    }
    if (event.key === "Tab") {
      event.preventDefault(); event.stopPropagation();
      const scope = root.current.closest("dialog[open]") || document;
      const focusable = [...scope.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')]
        .filter((node) => node.tabIndex >= 0 && !node.disabled && !popup.current.contains(node) && node.getClientRects().length);
      const position = focusable.indexOf(trigger.current);
      const next = (position + (event.shiftKey ? -1 : 1) + focusable.length) % focusable.length;
      close(); focusable[next]?.focus();
    }
  }
  return <div className={`pf-account-menu pf-account-menu--${placement}`} ref={root}
    onBlur={(event) => { if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) close(); }}>
    <button ref={trigger} className="pf-account-trigger" type="button" aria-label="Account menu" title={name}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => { focusLast.current = false; setOpen((value) => !value); }}
      onKeyDown={(event) => { if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); focusLast.current = event.key === "ArrowUp"; setOpen(true); } }}>
      <span className="pf-account-avatar" aria-hidden="true">{initials}</span><span className="pf-account-identity"><strong>{name}</strong><small>{user.email}</small></span><NavigationIcon path="M12 5h.01M12 12h.01M12 19h.01" />
    </button>
    {open && <div className="pf-account-popup" role="menu" aria-label="Account options" id={id} ref={popup} onKeyDown={keyboard}>
      <div className="pf-account-popup-heading" role="presentation"><span className="pf-account-avatar" aria-hidden="true">{initials}</span><div><strong>{name}</strong><small>{user.email}</small></div></div>
      <div role="group" className="pf-account-menu-links">{entries.map((entry) => <Link role="menuitem" tabIndex={-1} key={entry.to} to={entry.to} onClick={() => { close(); onNavigate?.(); }}><NavigationIcon path={entry.icon} />{entry.label}</Link>)}</div>
      <div className="pf-account-sign-out"><button type="button" role="menuitem" tabIndex={-1} disabled={busy} onClick={async () => {
        setBusy(true); setError("");
        try { await signOut(); onNavigate?.(); }
        catch (err) { setError(errorMessage(err)); }
        finally { setBusy(false); }
      }}><NavigationIcon path="M10 17l5-5-5-5M15 12H3M14 3h7v18h-7" />{busy ? "Signing out…" : "Sign out"}</button></div>
      {error && <p className="pf-account-error" role="alert">{error}</p>}
    </div>}
  </div>;
}
