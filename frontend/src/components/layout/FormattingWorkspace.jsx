import { NavLink, useLocation } from "react-router-dom";

export const formattingVerdictLabel = (verdict) => ({ accepted: "Passed", needs_review: "Needs review", rejected: "Blocking issues" }[verdict] || "Needs review");

export default function FormattingWorkspace({ title, description, actions, children, className = "" }) {
  const { pathname } = useLocation();
  const pages = [["/submit", "Check papers"], ["/compare", "Compare documents"], ["/setup", "Template setup"], ["/reports", "Saved reports"]];
  if (pathname === "/results") pages.push(["/results", "Results"]);
  return <div className={`pf-management pf-formatting ${className}`}><header className="pf-management-header"><div><p className="pf-eyebrow">FORMATTING WORKSPACE</p><h1>{title}</h1><p>{description}</p></div>{actions && <div className="pf-actions">{actions}</div>}</header><nav className="pf-workspace-tabs" aria-label="Formatting tools">{pages.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}</nav>{children}</div>;
}
