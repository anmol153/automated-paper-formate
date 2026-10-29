import SubmissionField, { ValidationIcon } from "./SubmissionField.jsx";

export const emptyMetadata = () => ({ title: "", abstract: "", authors: [], track_id: null });
export const metadataFields = (data) => ({ title: data.title, abstract: data.abstract, authors: data.authors.map((a) => ({ name: a.name, affiliation: a.affiliation || "" })), track_id: data.track_id });

export function validatePaperMetadata(value, requirements = {}, forReview = true, tracks = []) {
  const errors = {};
  if (forReview) {
    if (requirements.require_title && !value.title.trim()) errors.title = "Enter the paper title.";
    if (requirements.require_abstract && !value.abstract.trim()) errors.abstract = "Enter an abstract.";
    if (requirements.require_authors && !value.authors.length) errors.authors = "Add at least one author.";
    if (requirements.require_track && !value.track_id) errors.track_id = tracks.some((track) => track.active)
      ? "Choose a track for your paper." : "A track is required. Ask a chair to add or enable a track in conference settings.";
  }
  value.authors.forEach((author, index) => {
    if (!author.name.trim()) errors[`author_${index}`] = "Enter the author's name.";
  });
  return errors;
}

export default function PaperMetadataFields({ value, onChange, tracks = [], requirements = {}, forReview = true, errors = {}, disabled = false }) {
  const change = (key, next) => onChange({ ...value, [key]: next });
  const changeAuthor = (index, key, next) => change("authors", value.authors.map((author, i) => i === index ? { ...author, [key]: next } : author));
  return <div className="pf-paper-metadata">
    <SubmissionField label="Paper title" required={forReview && requirements.require_title} error={errors.title}>
      <input placeholder="Enter your paper title" value={value.title} maxLength={500} disabled={disabled} onChange={(e) => change("title", e.target.value)} />
    </SubmissionField>
    <SubmissionField label="Abstract" required={forReview && requirements.require_abstract} error={errors.abstract}>
      <textarea placeholder="A short summary of your research" rows={5} value={value.abstract} maxLength={12000} disabled={disabled} onChange={(e) => change("abstract", e.target.value)} />
    </SubmissionField>
    <SubmissionField label="Track" required={forReview && requirements.require_track} error={errors.track_id} hint="Choose the topic that best fits your paper.">
      <select value={value.track_id || ""} disabled={disabled} onChange={(e) => change("track_id", e.target.value || null)}>
        <option value="">No track selected</option>
        {tracks.filter((track) => track.active || track.track_id === value.track_id).map((track) => <option key={track.track_id} value={track.track_id}>{track.name}{!track.active ? " (archived)" : ""}</option>)}
      </select>
    </SubmissionField>
    <fieldset className="space-y-3 pf-paper-authors" disabled={disabled} aria-describedby={errors.authors ? "paper-authors-error" : undefined}>
      <legend className="font-medium">Author list{forReview && requirements.require_authors && " *"}</legend>
      <p className="text-sm text-surface-500">List authors in the order they appear on the paper.</p>
      {value.authors.map((author, index) => <div key={index} className="border rounded p-3 pf-author-entry">
        <SubmissionField label={`Author ${index + 1} name`} required error={errors[`author_${index}`]}>
          <input maxLength={200} value={author.name} onChange={(e) => changeAuthor(index, "name", e.target.value)} />
        </SubmissionField>
        <SubmissionField label={`Author ${index + 1} affiliation`}>
          <input maxLength={500} value={author.affiliation} onChange={(e) => changeAuthor(index, "affiliation", e.target.value)} />
        </SubmissionField>
        <button type="button" className="btn-secondary" aria-label={`Remove author ${index + 1}`} onClick={() => change("authors", value.authors.filter((_, i) => i !== index))}>Remove</button>
      </div>)}
      <span className="pf-author-add"><button type="button" className="btn-secondary" disabled={value.authors.length >= 50} aria-invalid={errors.authors ? true : undefined} aria-describedby={errors.authors ? "paper-authors-error" : undefined} onClick={() => change("authors", [...value.authors, { name: "", affiliation: "" }])}>Add author</button>{errors.authors && <ValidationIcon message={errors.authors} />}</span>
      {errors.authors && <p id="paper-authors-error" className="sr-only" role="alert">{errors.authors}</p>}
    </fieldset>
  </div>;
}
