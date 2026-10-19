export default function PageHeader({ title, description, eyebrow, actions, children }) {
  return <header className="pf-page-header">
    <div className="pf-page-heading">{eyebrow && <p className="pf-eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>{description && <p className="pf-description">{description}</p>}{children}
    </div>{actions && <div className="pf-page-actions">{actions}</div>}
  </header>;
}
