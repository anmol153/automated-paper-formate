import { Link } from "react-router-dom";

export default function Button({ variant = "secondary", size = "standard", busy = false, disabled = false, className = "", children, type = "button", ...props }) {
  return <button {...props} type={type} disabled={disabled || busy} aria-busy={busy || undefined}
    className={`pf-button pf-button--${variant} pf-button--${size} ${className}`}>
    {busy && <span className="pf-spinner" aria-hidden="true" />}{children}
  </button>;
}

export function ButtonLink({ to, variant = "secondary", className = "", children, ...props }) {
  return <Link {...props} to={to} className={`pf-button pf-button--${variant} ${className}`}>{children}</Link>;
}
