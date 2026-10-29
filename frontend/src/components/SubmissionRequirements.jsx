import { Link } from "react-router-dom";

export default function SubmissionRequirements({ confId, templateStatus, settings, onReloadTemplates }) {
  const submissionWindow = settings?.submission_window;
  const rules = settings?.enabled ? settings.settings : {};
  if (templateStatus === "ready" && submissionWindow?.allowed !== false) return null;
  let windowAdvice = "Ask a conference chair to check the submission schedule.";
  if (rules.lifecycle_status && rules.lifecycle_status !== "open") {
    windowAdvice = `The conference is ${rules.lifecycle_status}. ${rules.lifecycle_status === "archived" ? "Contact a chair about available submission options." : "A chair must open it for initial submissions."}`;
  } else if (rules.submissions_open_at && new Date(rules.submissions_open_at) > new Date()) {
    windowAdvice = `Submissions open ${new Date(rules.submissions_open_at).toLocaleString()}. Please return then.`;
  } else if (rules.submissions_close_at && new Date(rules.submissions_close_at) <= new Date()) {
    windowAdvice = `The submission deadline was ${new Date(rules.submissions_close_at).toLocaleString()}. Contact a chair if you need an extension.`;
  }
  return <div className="pf-message pf-message--error" role="alert" tabIndex={-1} data-submission-blocker>
    {templateStatus !== "ready" && <>
      <p id="paper-template-status">{templateStatus === "loading" ? "The conference template is still loading. Please try again in a moment."
        : templateStatus === "error" ? "The conference template could not be loaded. Please reload the templates before submitting, or open the template page."
          : "No template has been published. Before submitting, ask a chair to publish a template."}</p>
      {templateStatus === "error" && <button type="button" className="btn-secondary" onClick={onReloadTemplates}>Reload templates</button>}
      {templateStatus !== "loading" && <Link className="text-primary-600" to={`/conferences/${confId}/latest`}>View conference template</Link>}
    </>}
    {submissionWindow?.allowed === false && <p id="paper-submission-window">{submissionWindow.reason || "Initial submissions are closed."} {windowAdvice}</p>}
  </div>;
}
