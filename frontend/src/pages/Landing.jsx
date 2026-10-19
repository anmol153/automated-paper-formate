import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { ButtonLink } from "../components/ui/Button.jsx";

export default function Landing() {
  const { user } = useAuth();
  return <div className="pf-management pf-home">
    <div className="pf-home-top"><span className="pf-eyebrow">THE RESEARCH WORKSPACE</span><Link to="/conferences">Explore conferences →</Link></div>
    <section className="pf-home-hero">
      <div><span className="pf-kicker">From first draft to final decision</span><h1>A better home for<br />your next conference.</h1><p>Bring papers, people and peer review together. Set up your conference, check submissions and keep every revision in one workspace.</p><div className="pf-actions"><ButtonLink variant="primary" to={user ? "/dashboard" : "/login"}>{user ? "Open dashboard" : "Get started"} →</ButtonLink><ButtonLink to="/conferences">Find a conference</ButtonLink></div><span className="pf-home-note">Already have a manuscript? <Link to="/submit">Check its formatting</Link></span></div>
      <div className="pf-home-diagram" aria-label="Paper workflow: configure, submit, review"><div className="pf-diagram-heading"><span className="pf-sidebar-dot" />One connected paper workflow</div>{[["01", "Configure your conference", "Templates, tracks and submission requirements"], ["02", "Welcome better submissions", "Check formatting and preserve every revision"], ["03", "Make review a conversation", "Discuss, request changes and record decisions"]].map(([number, title, text]) => <div className="pf-diagram-step" key={number}><span>{number}</span><div><h3>{title}</h3><p>{text}</p></div></div>)}<div className="pf-diagram-footer">PDF · Word · LaTeX <span>Built for research teams</span></div></div>
    </section>
    <section className="pf-home-features" aria-label="Explore Paper-Format">{[["For conference chairs", "A workspace for your entire event", "Create a conference, publish formatting rules, invite participants and configure how reviews work.", "/conferences/new", "Create a conference"], ["For authors", "Give your paper a clear path forward", "Find your conference, upload a manuscript and follow its checks, revisions and review discussion.", "/conferences", "Browse conferences"], ["For reviewers", "Focus on the work that matters", "Open your assignments, read the current revision and submit a structured review.", "/reviewer", "Open review workspace"]].map(([label, title, text, to, action]) => <article key={label}><span className="pf-eyebrow">{label}</span><h2>{title}</h2><p>{text}</p><Link to={to}>{action} →</Link></article>)}</section>
    <div className="pf-home-bottom"><div><h2>Formatting checks are still right here.</h2><p>Use the standalone checker or compare a paper with your own template.</p></div><ButtonLink to="/compare">Compare documents →</ButtonLink></div>
  </div>;
}
