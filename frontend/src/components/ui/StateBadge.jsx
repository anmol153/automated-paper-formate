const states = {
  draft: ["neutral", "Draft"], submitted: ["info", "Submitted"], under_review: ["info", "Under review"],
  changes_requested: ["attention", "Changes requested"], accepted: ["success", "Accepted"],
  rejected: ["danger", "Rejected"], withdrawn: ["neutral", "Withdrawn"],
  passed: ["success", "Passed"], passed_with_warnings: ["attention", "Passed with warnings"],
  failed: ["danger", "Failed"], processing: ["info", "Processing"], unable_to_validate: ["neutral", "Unable to validate"],
};
const marks = { success: "M5 12l4 4L19 6", danger: "M6 6l12 12M18 6L6 18", attention: "M12 7v6m0 4h.01", info: "M12 7v5l3 2", neutral: "M8 12h8" };

export default function StateBadge({ status, label }) {
  const [tone, name] = states[status] || ["neutral", String(status || "Unknown").replaceAll("_", " ")];
  return <span className={`pf-state pf-state--${tone}`}>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path strokeLinecap="round" strokeLinejoin="round" d={marks[tone]} /></svg>
    {label || name}
  </span>;
}
