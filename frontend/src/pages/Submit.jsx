import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import MultiDropZone from "../components/MultiDropZone.jsx";
import {
  errorMessage,
  getDriveStatus,
  listTemplates,
  previewDriveFolder,
  submitFromDrive,
  submitPapers,
} from "../lib/api.js";

export default function Submit() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [files, setFiles] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [mode, setMode] = useState("files");
  const [folderUrl, setFolderUrl] = useState("");
  const [recursive, setRecursive] = useState(true);
  const [preview, setPreview] = useState(null);
  const [drive, setDrive] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    listTemplates()
      .then((list) => {
        setTemplates(list);
        if (list.length === 1) setTemplateId(list[0].template_id);
      })
      .catch((err) => setError(errorMessage(err)));
    getDriveStatus()
      .then(setDrive)
      .catch(() => setDrive({ configured: false, mode: "unknown" }));
  }, []);

  const selectedTemplate = templates.find((t) => t.template_id === templateId);

  const ready =
    Boolean(templateId) &&
    (mode === "files" ? files.length > 0 : folderUrl.trim().length > 0);

  const addFiles = useCallback((accepted, refused = []) => {
    if (accepted.length) {
      setFiles((prev) => {
        const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
        return [...prev, ...accepted.filter((f) => !seen.has(`${f.name}:${f.size}`))];
      });
    }
    if (refused.length) {
      setRejected((prev) => [...prev, ...refused]);
    }
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    setProgress(0);
    try {
      const report =
        mode === "files"
          ? await submitPapers(files, { templateId, onProgress: setProgress })
          : await submitFromDrive(folderUrl, { templateId, recursive });
      navigate("/results", { state: { report } });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePreview() {
    if (!folderUrl.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(await previewDriveFolder(folderUrl, recursive));
    } catch (err) {
      setPreview(null);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="animate-fade-in">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-surface-900 dark:text-surface-50">Submit papers</h1>
        <p className="mt-2 max-w-2xl text-sm text-surface-600 dark:text-surface-400">
          Check one paper or a whole batch against the venue's rules. Every paper is reported
          separately, and a problem with one file never blocks the rest of the batch.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="panel animate-slide-up" aria-labelledby="template-heading">
          <h2 id="template-heading" className="panel-title">Venue template</h2>
          {templates.length === 0 ? (
            <div className="alert alert-warning">
              <div className="flex items-start gap-3">
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-6a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 4zm0 10a.75.75 0 01.75-.75h.008v.008H10.75V10a.75.75 0 011.5 0v.008H11.5V14a.75.75 0 01-1.5 0v-.008H10V11a.75.75 0 01.75-.75z" clipRule="evenodd" />
                </svg>
                <div>
                  <p className="font-medium">No template configured</p>
                  <p className="mt-1 text-sm">A conference manager needs to save a template in <strong>Setup</strong> before authors can submit.</p>
                </div>
              </div>
            </div>
          ) : (
            <>
              <Field label="Select template" hint="Choose the venue template to check against.">
                <select
                  className="input-base"
                  value={templateId}
                  disabled={busy}
                  onChange={(e) => setTemplateId(e.target.value)}
                  aria-required="true"
                >
                  <option value="">Select a template&hellip;</option>
                  {templates.map((template) => (
                    <option key={template.template_id} value={template.template_id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </Field>
              {selectedTemplate?.publisher?.notes_for_authors && (
                <div className="alert alert-info">
                  <div className="flex items-start gap-3">
                    <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0111 6zm-1 8a.75.75 0 101.5 0H11.5a.75.75 0 000 1.5H10a.75.75 0 00-.75-.75z" clipRule="evenodd" />
                    </svg>
                    <p className="text-sm">{selectedTemplate.publisher.notes_for_authors}</p>
                  </div>
                </div>
              )}
            </>
          )}
        </section>

        <section className="panel animate-slide-up" aria-labelledby="mode-heading">
          <h2 id="mode-heading" className="panel-title">Submission method</h2>
          <div className="flex gap-2 rounded-lg bg-surface-100 p-1 dark:bg-surface-800" role="radiogroup" aria-label="Choose submission method">
            {[
              ["files", "Upload files", "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"],
              ["drive", "Google Drive folder", "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"],
            ].map(([key, label, icon]) => (
              <button
                key={key}
                type="button"
                onClick={() => setMode(key)}
                disabled={busy || templates.length === 0}
                role="radio"
                aria-checked={mode === key}
                className={`flex-1 flex items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all duration-150 disabled:opacity-50 ${
                  mode === key
                    ? "bg-white text-surface-900 shadow-sm dark:bg-surface-900 dark:text-white"
                    : "text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-100"
                }`}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 shrink-0" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
                </svg>
                {label}
              </button>
            ))}
          </div>
        </section>

        {mode === "files" ? (
          <section className="panel animate-slide-up" aria-labelledby="files-heading">
            <h2 id="files-heading" className="panel-title">Paper files</h2>
            <MultiDropZone
              files={files}
              rejected={rejected}
              onAdd={addFiles}
              onRemove={(index) => setFiles((prev) => prev.filter((_, i) => i !== index))}
              onClearRejected={() => setRejected([])}
              disabled={busy}
            />
          </section>
        ) : (
          <DrivePanel
            drive={drive}
            folderUrl={folderUrl}
            setFolderUrl={setFolderUrl}
            recursive={recursive}
            setRecursive={setRecursive}
            preview={preview}
            onPreview={handlePreview}
            busy={busy}
          />
        )}

        {error && (
          <div className="alert alert-danger animate-slide-down" role="alert">
            <div className="flex items-start gap-3">
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <p>{error}</p>
            </div>
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pt-2 animate-fade-in">
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={!ready || busy}
              className="btn-primary min-w-[180px]"
            >
              {busy
                ? "Checking&hellip;"
                : mode === "files"
                ? `Check ${files.length} paper${files.length === 1 ? "" : "s"}`
                : "Check Drive folder"}
            </button>
            {busy && mode === "files" && progress > 0 && progress < 100 && (
              <div className="flex items-center gap-3">
                <div className="h-2 w-48 overflow-hidden rounded-full bg-surface-200 dark:bg-surface-700">
                  <div
                    className="h-full rounded-full bg-primary-500 transition-all duration-300 ease-out"
                    style={{ width: `${progress}%` }}
                    role="progressbar"
                    aria-valuenow={progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Upload progress"
                  />
                </div>
                <span className="text-sm font-medium text-surface-500 tabular-nums dark:text-surface-400 w-10 text-right">
                  {progress}%
                </span>
              </div>
            )}
          </div>
        </div>
      </form>

      <div className="alert alert-warning animate-fade-in" role="note">
        <div className="flex items-start gap-3">
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0111 6zm-1 8a.75.75 0 101.5 0H11.5a.75.75 0 000 1.5H10a.75.75 0 00-.75-.75z" clipRule="evenodd" />
          </svg>
          <div className="text-xs leading-relaxed text-warning-800 dark:text-warning-200">
            <p className="font-medium">Supported formats</p>
            <p className="mt-1">PDF, TEX and DOCX files are analyzed. Scanned PDFs without extractable text are not supported. Page counts for LaTeX and Word submissions are estimated, because those formats are not paginated until they are rendered; PDF page counts are exact.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function DrivePanel({
  drive,
  folderUrl,
  setFolderUrl,
  recursive,
  setRecursive,
  preview,
  onPreview,
  busy,
}) {
  if (drive && drive.configured === false) {
    return (
      <section className="panel animate-slide-up" aria-labelledby="drive-warning-heading">
        <h2 id="drive-warning-heading" className="panel-title">Google Drive</h2>
        <div className="alert alert-warning">
          <div className="flex items-start gap-3">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0111 6zm-1 8a.75.75 0 101.5 0H11.5a.75.75 0 000 1.5H10a.75.75 0 00-.75-.75z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="font-medium">Google Drive is not connected</p>
              <p className="mt-1 text-sm">{drive.instructions ?? "The backend has no Drive credentials, so folders cannot be listed."} Upload the files directly instead &mdash; it works without any setup.</p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel animate-slide-up" aria-labelledby="drive-heading">
      <h2 id="drive-heading" className="panel-title">Google Drive folder</h2>
      <Field label="Folder link" hint="Paste a Google Drive folder URL.">
        <input
          className="input-base"
          placeholder="https://drive.google.com/drive/folders/&hellip;"
          value={folderUrl}
          disabled={busy}
          onChange={(e) => setFolderUrl(e.target.value)}
        />
      </Field>
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400 cursor-pointer">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-400 dark:border-surface-600 dark:bg-surface-800"
            checked={recursive}
            disabled={busy}
            onChange={(e) => setRecursive(e.target.checked)}
          />
          Include subfolders
        </label>
        <button
          type="button"
          onClick={onPreview}
          disabled={!folderUrl.trim() || busy}
          className="btn-secondary"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          Preview files
        </button>
      </div>
      {preview && (
        <div className="mt-4 rounded-xl border border-surface-200 bg-surface-50 p-4 dark:border-surface-800 dark:bg-surface-900/50 animate-slide-down">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-surface-700 dark:text-surface-300">
              {preview.usable_papers} paper{preview.usable_papers === 1 ? "" : "s"} found
              {preview.skipped?.length ? ` &middot; ${preview.skipped.length} skipped` : ""}
            </p>
          </div>
          {preview.files?.length > 0 && (
            <ul className="mt-3 max-h-48 space-y-1.5 overflow-y-auto scrollbar-thin">
              {preview.files.map((file) => (
                <li key={file.id} className="flex items-center gap-2 truncate text-xs text-surface-500 dark:text-surface-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-surface-300 dark:bg-surface-600 shrink-0" aria-hidden="true" />
                  {file.name}
                </li>
              ))}
            </ul>
          )}
          {preview.skipped?.length > 0 && (
            <p className="mt-3 text-xs text-warning-700 dark:text-warning-300">
              <span className="font-medium">Skipped: </span>
              {preview.skipped.map((f) => f.name).join(", ")}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}