export default function StateNotice({ tone = "info", title, children, action }) {
  return <div className={`pf-notice pf-notice--${tone}`} role={tone === "danger" ? "alert" : undefined}>
    <div>{title && <p className="pf-notice-title">{title}</p>}{children}</div>{action}
  </div>;
}
