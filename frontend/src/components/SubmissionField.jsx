import { Children, cloneElement, useId } from "react";

export function ValidationIcon({ select = false, message }) {
  return <svg className={`pf-validation-icon${select ? " pf-validation-icon--select" : ""}`} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
    {message && <title>{message}</title>}
    <circle cx="10" cy="10" r="8" /><circle cx="10" cy="6" r=".7" fill="currentColor" stroke="none" /><path d="M10 9v5" />
  </svg>;
}

export default function SubmissionField({ id, label, required = false, error, hint, children }) {
  const generated = useId();
  const fieldId = id || generated;
  const control = Children.only(children);
  const describedBy = [control.props["aria-describedby"], hint && `${fieldId}-hint`, error && `${fieldId}-error`].filter(Boolean).join(" ");
  return <div className="pf-field pf-submission-field">
    <label htmlFor={fieldId}>{label}{required && <span aria-hidden="true"> *</span>}</label>
    <div className="pf-submission-control">
      {cloneElement(control, { id: fieldId, required: required || control.props.required, "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy || undefined, className: `pf-input ${control.props.className || ""}` })}
      {error && <ValidationIcon select={control.type === "select"} message={error} />}
    </div>
    {hint && <p id={`${fieldId}-hint`} className="pf-field-hint">{hint}</p>}
    {error && <p id={`${fieldId}-error`} className="sr-only" role="alert">{error}</p>}
  </div>;
}
