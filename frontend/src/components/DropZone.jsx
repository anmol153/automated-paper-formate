import { useRef, useState } from "react";
import FileIcon from "./FileIcon.jsx";

const MAX_SIZE = 30 * 1024 * 1024;
const ACCEPT_EXTENSIONS = ["pdf", "tex", "latex", "docx"];

export default function DropZone({ label, hint, file, error, onSelect, onClear, disabled }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  function accept(file) {
    if (!file) return;
    const extension = String(file.name.split(".").pop() || "").toLowerCase();
    const isSupported = ACCEPT_EXTENSIONS.includes(extension);
    if (!isSupported) {
      onSelect(null, "Only PDF, TEX and DOCX files are accepted.");
      return;
    }
    if (file.size > MAX_SIZE) {
      onSelect(null, "File is larger than 30 MB.");
      return;
    }
    onSelect(file, null);
  }

  const getZoneClass = () => {
    if (dragOver) return "dropzone-active";
    if (error) return "dropzone-error";
    if (file) return "dropzone-file";
    return "";
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label htmlFor={`dropzone-${label.toLowerCase()}`} className="field-label">
          {label}
        </label>
        {file && (
          <button
            type="button"
            onClick={onClear}
            disabled={disabled}
            className="btn-ghost text-xs px-2 py-1"
            aria-label={`Remove ${file.name}`}
          >
            Remove
          </button>
        )}
      </div>

      <div
        id={`dropzone-${label.toLowerCase()}`}
        onClick={() => !file && !disabled && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (!disabled) accept(e.dataTransfer.files?.[0]);
        }}
        className={`relative flex min-h-[120px] cursor-pointer items-center gap-4 rounded-2xl border-2 border-dashed px-4 py-4 transition-all duration-200 ${getZoneClass()} ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !file && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        aria-label={file ? `${label}: ${file.name}, ${(file.size / 1024 / 1024).toFixed(2)} MB` : `Drop ${label} file here or click to browse`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.tex,.latex,.docx,application/pdf"
          className="hidden"
          onChange={(e) => {
            accept(e.target.files?.[0]);
            e.target.value = "";
          }}
          disabled={disabled}
          aria-label={`Choose ${label} file`}
        />

        {file ? (
          <>
            <FileIcon name={file.name} className="h-10 w-10 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-surface-800 dark:text-surface-100">{file.name}</p>
              <p className="text-xs text-surface-500 dark:text-surface-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
            <div className="flex items-center gap-2">
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 text-success-500" aria-hidden="true">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
              </svg>
              <button
                type="button"
                onClick={onClear}
                disabled={disabled}
                className="btn-ghost p-1.5 text-surface-400 hover:text-danger-600 dark:hover:text-danger-400"
                aria-label={`Remove ${file.name}`}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="flex flex-col items-center gap-3 text-center">
              <UploadGlyph />
              <div>
                <p className="text-sm font-medium text-surface-600 dark:text-surface-400">
                  Drop PDF, TEX or DOCX here or <span className="text-primary-600 dark:text-primary-400 font-semibold">browse</span>
                </p>
                <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">{hint}</p>
              </div>
            </div>
          </>
        )}
      </div>

      {error && (
        <div className="mt-2 flex items-center gap-2 rounded-lg bg-danger-50 px-3 py-2 text-xs text-danger-700 dark:bg-danger-500/10 dark:text-danger-300 animate-slide-down">
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 shrink-0" aria-hidden="true">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-6a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 4zm0 10a.75.75 0 01.75-.75h.008v.008H10.75V10a.75.75 0 011.5 0v.008H11.5V14a.75.75 0 01-1.5 0v-.008H10V11a.75.75 0 01.75-.75z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}

function UploadGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-8 w-8 shrink-0 text-surface-400 dark:text-surface-500" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0L8 8m4-4l4 4m4 8v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2" />
    </svg>
  );
}