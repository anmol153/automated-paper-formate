import { useRef, useState } from "react";
import FileIcon from "./FileIcon.jsx";

const MAX_SIZE_MB = 50;
const ACCEPT_EXTENSIONS = ["pdf", "tex", "latex", "ltx", "docx"];

export default function MultiDropZone({
  files,
  rejected,
  onAdd,
  onRemove,
  onClearRejected,
  disabled,
  maxCount = 40,
}) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  function collect(list) {
    if (!list?.length) return;
    const accepted = [];
    const refused = [];
    for (const file of Array.from(list)) {
      const extension = String(file.name.split(".").pop() || "").toLowerCase();
      if (!ACCEPT_EXTENSIONS.includes(extension)) {
        refused.push({ name: file.name, reason: "not a PDF, TEX or DOCX file" });
      } else if (file.size === 0) {
        refused.push({ name: file.name, reason: "file is empty" });
      } else if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        refused.push({ name: file.name, reason: `larger than ${MAX_SIZE_MB} MB` });
      } else {
        accepted.push(file);
      }
    }
    if (accepted.length) onAdd(accepted);
    if (refused.length) onAdd([], refused);
  }

  const full = files.length >= maxCount;

  return (
    <div>
      <div
        onClick={() => !disabled && !full && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !full) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (!disabled && !full) collect(e.dataTransfer.files);
        }}
        onPaste={(e) => {
          if (disabled || full) return;
          const pasted = Array.from(e.clipboardData?.files ?? []);
          if (pasted.length) {
            e.preventDefault();
            collect(pasted);
          }
        }}
        tabIndex={0}
        role="button"
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled && !full) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={`flex min-h-[120px] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-5 text-center transition-all duration-200 ${
          dragOver
            ? "dropzone-active"
            : full
            ? "border-surface-300 bg-surface-100 opacity-60 dark:border-surface-700 dark:bg-surface-900"
            : "border-surface-300 bg-surface-50 hover:border-primary-300 hover:bg-primary-50/40 dark:border-surface-700 dark:bg-surface-900 dark:hover:border-primary-500 dark:hover:bg-primary-500/10"
        } ${disabled ? "pointer-events-none opacity-60" : ""}`}
        aria-label={full ? "Maximum file limit reached" : "Drop papers here, click to browse, or paste files"}
      >
        <UploadGlyph />
        <p className="text-sm font-medium text-surface-600 dark:text-surface-400">
          Drop papers here, <span className="text-primary-600 dark:text-primary-400">browse</span>, or paste files
        </p>
        <p className="text-xs text-surface-400">
          PDF, TEX and DOCX &middot; up to {maxCount} at a time &middot; {MAX_SIZE_MB} MB max each
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.tex,.latex,.ltx,.docx,application/pdf"
        className="hidden"
        onChange={(e) => {
          collect(e.target.files);
          e.target.value = "";
        }}
        disabled={disabled}
        aria-label="Choose paper files"
      />

      {files.length > 0 && (
        <div className="mt-3 animate-fade-in">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-medium text-surface-700 dark:text-surface-300">
              {files.length} file{files.length === 1 ? "" : "s"} selected
            </p>
          </div>
          <ul className="divide-y divide-surface-200 overflow-hidden rounded-xl border border-surface-200 dark:divide-surface-800 dark:border-surface-800">
            {files.map((file, index) => (
              <li
                key={`${file.name}-${index}`}
                className="flex items-center gap-3 bg-white px-4 py-3 dark:bg-surface-900 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors"
              >
                <FileIcon name={file.name} className="h-7 w-7 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-surface-800 dark:text-surface-100">
                    {file.name}
                  </p>
                  <p className="text-xs text-surface-500 dark:text-surface-400">{(file.size / 1024).toFixed(0)} KB</p>
                </div>
                <button
                  type="button"
                  onClick={() => onRemove(index)}
                  disabled={disabled}
                  aria-label={`Remove ${file.name}`}
                  className="btn-ghost p-1.5 text-surface-400 hover:text-danger-600 dark:hover:text-danger-400"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {rejected.length > 0 && (
        <div className="mt-3 rounded-xl border border-warning-200 bg-warning-50 px-4 py-3 dark:border-warning-500/30 dark:bg-warning-500/10 animate-slide-down">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-semibold text-warning-800 dark:text-warning-200">
              {rejected.length} file{rejected.length > 1 ? "s" : ""} not added
            </p>
            <button
              type="button"
              onClick={onClearRejected}
              className="btn-ghost text-xs text-warning-600 hover:text-danger-600 dark:text-warning-400 dark:hover:text-danger-400"
            >
              Dismiss
            </button>
          </div>
          <ul className="mt-2 space-y-1">
            {rejected.map((item) => (
              <li key={item.name} className="text-xs text-warning-800/90 dark:text-warning-200/90">
                <span className="font-medium">{item.name}</span> &mdash; {item.reason}
              </li>
            ))}
          </ul>
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