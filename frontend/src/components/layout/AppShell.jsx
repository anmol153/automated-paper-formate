import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import Button from "../ui/Button.jsx";
import NotificationDropdown from "../NotificationDropdown.jsx";
import SessionControls from "../SessionControls.jsx";
import ThemeToggle from "../ThemeToggle.jsx";
import AppNavigation, { NavigationIcon } from "./AppNavigation.jsx";
import AccountMenu from "./AccountMenu.jsx";

function contextFor(pathname) {
  if (pathname === "/my-invitations") return [{ label: "My invitations" }];
  if (pathname === "/my-schedule") return [{ label: "My schedule" }];
  if (pathname === "/docs") return [{ label: "Docs" }];
  if (pathname === "/settings") return [{ label: "Account settings" }];
  if (pathname.startsWith("/conferences/")) {
    const section = pathname.endsWith("/new") ? "Create conference" : pathname.endsWith("/latest") ? "Templates" : pathname.endsWith("/diff") ? "Template comparison" : pathname.endsWith("/submit") ? "New submission" : pathname.endsWith("/submissions") ? "Papers" : "Conference workspace";
    return [{ label: "Conferences", to: "/conferences" }, { label: section }];
  }
  if (pathname.startsWith("/submissions/")) return [{ label: "Paper workspace" }];
  if (pathname.startsWith("/issues/")) return [{ label: "Paper workspace" }, { label: "Issues" }];
  const names = { "/": "Home", "/home": "Home", "/dashboard": "Dashboard", "/submit": "Check papers", "/compare": "Compare documents", "/reports": "Saved reports", "/results": "Formatting results", "/setup": "Template setup", "/conferences": "Conferences", "/reviewer": "Review workspace", "/notifications": "Notifications", "/account": "Account", "/login": "Sign in", "/invitations": "Conference invitation" };
  return [{ label: names[pathname] || "Workspace" }];
}

function Brand({ compact = false, onClick }) {
  return <Link to="/" className={`pf-brand${compact ? " is-compact" : ""}`} aria-label="Paper-Format home" onClick={onClick}>
    <span className="pf-brand-mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" d="M7 3h9l4 4v11H7zM16 3v5h4M4 7v14h12M10 12h7m-7 3h5" /></svg></span>
    <span className="pf-brand-name">Paper-Format</span>
  </Link>;
}

export default function AppShell({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  const sessionKey = user?.user_id || "anonymous";
  const [collapsed, setCollapsed] = useState(false);
  const [wide, setWide] = useState(() => window.matchMedia?.("(min-width: 1280px)").matches ?? false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawer = useRef(null);
  const toggle = useRef(null);
  const paper = /^\/(submissions|issues)\//.test(location.pathname);
  const compact = collapsed || paper || !wide;
  const context = contextFor(location.pathname);
  const desktopToggle = wide && !paper;

  const closeNavigation = () => { if (drawer.current?.open) drawer.current.close(); };
  useEffect(() => {
    const query = window.matchMedia?.("(min-width: 1280px)");
    if (!query) return;
    const changed = () => setWide(query.matches);
    query.addEventListener?.("change", changed);
    return () => query.removeEventListener?.("change", changed);
  }, []);
  useEffect(() => { closeNavigation(); }, [location.key, wide]);
  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [drawerOpen]);
  function toggleNavigation() {
    if (desktopToggle) setCollapsed((value) => !value);
    else if (drawer.current && !drawer.current.open) { drawer.current.showModal(); setDrawerOpen(true); }
  }
  function containDrawerFocus(event) {
    if (event.key !== "Tab") return;
    const controls = [...drawer.current.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')]
      .filter((node) => !node.disabled && node.tabIndex >= 0 && node.getClientRects().length > 0)
      .sort((left, right) => left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);
    const first = controls[0], last = controls.at(-1);
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
  if (location.pathname === "/login") return <div className="pf-auth-shell"><a href="#main-content" className="pf-skip-link">Skip to content</a><header className="pf-auth-header"><Brand /><div><Link to="/" className="pf-auth-home-link">← Back to home</Link><ThemeToggle /></div></header><main id="main-content" tabIndex={-1} className="pf-auth-main">{children}</main><footer className="pf-auth-footer">Paper-Format<span>Paper formatting & peer review</span><Link to="/docs">Help & documentation</Link></footer></div>;
  return <div className={`pf-shell${compact ? " is-compact" : ""}`}>
    <a href="#main-content" className="pf-skip-link">Skip to content</a>
    <aside className="pf-sidebar" aria-label="Workspace sidebar">
      <Brand compact={compact} />
      <AppNavigation id="workspace-sidebar-navigation" compact={compact} authenticated={!!user} currentPath={location.pathname} />
      <div className="pf-sidebar-account"><AccountMenu /></div>
    </aside>
    <div className="pf-shell-body">
      <header className="pf-topbar">
        <div className="pf-context">
          <Button ref={toggle} className="pf-icon-button" onClick={toggleNavigation} aria-label={desktopToggle ? collapsed ? "Expand navigation" : "Collapse navigation" : "Open navigation"}
            aria-expanded={desktopToggle ? !collapsed : drawerOpen} aria-controls={desktopToggle ? "workspace-sidebar-navigation" : "navigation-dialog"}>
            <NavigationIcon path="M4 4h16v16H4zM9 4v16" />
          </Button>
          <div className="pf-mobile-brand"><Brand /></div>
          <nav className="pf-breadcrumbs" aria-label="Breadcrumb"><ol>{context.map((item, index) => <li key={item.label}>
            {index > 0 && <span aria-hidden="true" className="pf-breadcrumb-divider">/</span>}{item.to ? <Link to={item.to}>{item.label}</Link> : <span aria-current="page">{item.label}</span>}
          </li>)}</ol></nav>
        </div>
        <div className="pf-shell-tools">
          <NotificationDropdown key={sessionKey} />
          {user ? <div className="pf-header-account"><AccountMenu placement="header" /></div> : <div className="pf-shell-session"><SessionControls /></div>}
          {!user && location.pathname !== "/login" && <Link className="pf-mobile-account pf-button" to="/login">Sign in</Link>}
          <ThemeToggle />
        </div>
      </header>
      <main id="main-content" key={sessionKey} tabIndex={-1} className="pf-main"><div className="pf-legacy-content">{children}</div></main>
      <footer className="pf-footer">Paper-Format<span aria-hidden="true"> · </span><span>Paper formatting & peer review</span></footer>
    </div>
    <dialog id="navigation-dialog" className="pf-navigation-dialog" ref={drawer} aria-label="Workspace navigation"
      onKeyDown={containDrawerFocus}
      onClose={() => { setDrawerOpen(false); toggle.current?.focus(); }}
      onClick={(event) => { if (event.target === event.currentTarget) closeNavigation(); }}>
      <div className="pf-drawer-header"><Brand onClick={closeNavigation} /><Button className="pf-icon-button" aria-label="Close navigation" onClick={closeNavigation}><NavigationIcon path="M6 6l12 12M18 6L6 18" /></Button></div>
      <AppNavigation authenticated={!!user} onNavigate={closeNavigation} currentPath={location.pathname} />
      <div className="pf-drawer-account"><AccountMenu placement="drawer" onNavigate={closeNavigation} /></div>
    </dialog>
  </div>;
}
