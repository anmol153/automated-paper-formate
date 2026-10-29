const titles = { publisher: "Publisher", file_type: "Accepted files", pages: "Page setup", sections: "Sections and references", anonymisation: "Anonymisation", typography: "Typography", paragraph: "Paragraph formatting", decision: "Decision rules" };
const label = (key) => key.replace(/_/g, " ").replace(/\bpt\b/g, "(pt)").replace(/\bmb\b/g, "(MB)").replace(/^./, (letter) => letter.toUpperCase());

function Value({ value }) {
  if (value === null || value === undefined || value === "") return <span className="pf-rule-unset">Not specified</span>;
  if (typeof value === "boolean") return <span className="pf-published-boolean" data-enabled={value}>{value ? "Yes" : "No"}</span>;
  if (Array.isArray(value)) return value.length ? value.map((entry) => typeof entry === "object" ? JSON.stringify(entry) : String(entry)).join(", ") : <span className="pf-rule-unset">None specified</span>;
  if (typeof value === "object") return <Rows values={value} />;
  return String(value);
}

function Rows({ values }) {
  return <dl className="pf-published-rule-rows">{Object.entries(values).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd><Value value={value} /></dd></div>)}</dl>;
}

export default function PublishedRules({ rules }) {
  return <article className="pf-published-rules" aria-label="Published template rules">
    <header><h3>{rules.name}</h3>{rules.description && <p>{rules.description}</p>}<p>Published snapshot · Read only. Unspecified values do not impose a requirement.</p></header>
    {rules.source_template_filename && <p>Source: {rules.source_template_filename}</p>}
    {Object.entries(rules).filter(([key, value]) => value && typeof value === "object" && !Array.isArray(value)).map(([key, value]) => <section key={key}><h4>{titles[key] || label(key)}</h4><Rows values={value} /></section>)}
  </article>;
}
