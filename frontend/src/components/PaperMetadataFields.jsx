export const emptyMetadata = () => ({ title: "", abstract: "", authors: [], track_id: null });
export const metadataFields = (data) => ({ title: data.title, abstract: data.abstract, authors: data.authors.map((a) => ({ name: a.name, affiliation: a.affiliation || "" })), track_id: data.track_id });

export default function PaperMetadataFields({ value, onChange, tracks = [], disabled = false }) {
  const change = (key, next) => onChange({ ...value, [key]: next });
  const changeAuthor = (index, key, next) => change("authors", value.authors.map((author, i) => i === index ? { ...author, [key]: next } : author));
  return <div className="space-y-4">
    <label className="block">Paper title<input className="input-base mt-2" value={value.title} maxLength={500} disabled={disabled} onChange={(e) => change("title", e.target.value)} /></label>
    <label className="block">Abstract<textarea className="input-base mt-2" rows={4} value={value.abstract} maxLength={12000} disabled={disabled} onChange={(e) => change("abstract", e.target.value)} /></label>
    <label className="block">Track<select className="input-base mt-2" value={value.track_id || ""} disabled={disabled} onChange={(e) => change("track_id", e.target.value || null)}>
      <option value="">No track selected</option>
      {tracks.filter((track) => track.active || track.track_id === value.track_id).map((track) => <option key={track.track_id} value={track.track_id}>{track.name}{!track.active ? " (archived)" : ""}</option>)}
    </select></label>
    <fieldset className="space-y-3" disabled={disabled}><legend className="font-medium">Author list</legend>
      <p className="text-sm text-surface-500">These names and affiliations describe the paper. Account access is managed separately through Paper collaborators.</p>
      {value.authors.map((author, index) => <div key={index} className="border rounded p-3 space-y-2">
        <label className="block">Author {index + 1} name<input className="input-base mt-1" required maxLength={200} value={author.name} onChange={(e) => changeAuthor(index, "name", e.target.value)} /></label>
        <label className="block">Author {index + 1} affiliation<input className="input-base mt-1" maxLength={500} value={author.affiliation} onChange={(e) => changeAuthor(index, "affiliation", e.target.value)} /></label>
        <button type="button" className="btn-secondary" aria-label={`Remove author ${index + 1}`} onClick={() => change("authors", value.authors.filter((_, i) => i !== index))}>Remove author</button>
      </div>)}
      <button type="button" className="btn-secondary" disabled={value.authors.length >= 50} onClick={() => change("authors", [...value.authors, { name: "", affiliation: "" }])}>Add author</button>
    </fieldset>
  </div>;
}
