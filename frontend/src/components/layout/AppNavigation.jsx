import { NavLink } from "react-router-dom";

const groups = [
  { label: "Workspace", items: [
    { to: "/", label: "Home", icon: "M3 11l9-8 9 8M5 9v12h5v-7h4v7h5V9" },
    { to: "/dashboard", label: "Dashboard", icon: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" },
    { to: "/conferences", label: "Conferences", icon: "M4 5h16v15H4zM8 3v4m8-4v4M4 10h16" },
    { to: "/reviewer", label: "Review workspace", icon: "M9 4H5v17h14V4h-4M9 3h6v4H9zM8 14l3 3 5-6" },
  ] },
  { label: "Formatting tools", items: [
    { to: "/submit", label: "Check papers", icon: "M5 3h9l5 5v13H5zM14 3v6h5M8 14h8m-8 3h5" },
    { to: "/compare", label: "Compare documents", icon: "M4 4h6v16H4zM14 4h6v16h-6zM8 8h0m10 8h0" },
    { to: "/setup", label: "Template setup", icon: "M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6" },
    { to: "/reports", label: "Saved reports", icon: "M5 3h10l4 4v14H5zM9 11h6m-6 4h6m-6 3h4" },
  ] },
];

export function NavigationIcon({ path }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" d={path} /></svg>;
}

export default function AppNavigation({ id, authenticated = false, onNavigate, compact = false, currentPath = "" }) {
  const render = (item) => <NavLink key={item.to} to={item.to === "/account" && currentPath === "/settings" ? "/settings" : item.to} end={item.to === "/"} title={compact ? item.label : undefined}
    className={({ isActive }) => `pf-nav-link${isActive ? " is-active" : ""}`} aria-label={item.label} onClick={onNavigate}>
    <NavigationIcon path={item.icon} /><span className="pf-nav-label">{item.label}</span>
  </NavLink>;
  return <nav id={id} className="pf-navigation" aria-label="Main navigation">
    {groups.map((group) => <div className="pf-nav-group" key={group.label}><p className="pf-nav-group-label">{group.label}</p>{group.items.map(render)}</div>)}
    {authenticated && <div className="pf-nav-group"><p className="pf-nav-group-label">Personal</p>{render({ to: "/notifications", label: "Notifications", icon: "M18 8a6 6 0 00-12 0c0 6-2 6-2 9h16c0-3-2-3-2-9M10 21h4" })}{render({ to: "/account", label: "Settings", icon: "M12 8a4 4 0 110 8 4 4 0 010-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z" })}</div>}
  </nav>;
}
