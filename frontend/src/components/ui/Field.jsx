import { Children, cloneElement, useId } from "react";

export default function Field({ id, label, hint, error, required = false, children }) {
  const generated = useId();
  const fieldId = id || generated;
  const control = Children.only(children);
  const describedBy = [control.props["aria-describedby"], hint && `${fieldId}-hint`, error && `${fieldId}-error`].filter(Boolean).join(" ");
  return <div className="pf-field">
    <label htmlFor={fieldId}>{label}{required && <span aria-hidden="true"> *</span>}</label>
    {cloneElement(control, { id: fieldId, required: required || control.props.required, "aria-invalid": error ? true : control.props["aria-invalid"], "aria-describedby": describedBy || undefined,
      className: `pf-input ${control.props.className || ""}` })}
    {hint && <p id={`${fieldId}-hint`} className="pf-field-hint">{hint}</p>}
    {error && <p id={`${fieldId}-error`} className="pf-field-error">{error}</p>}
  </div>;
}
