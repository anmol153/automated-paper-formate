import { useRef, useState } from "react";
import PdfIcon from "../components/PdfIcon.jsx";

const MAX_SIZE = 30 * 1024 * 1024;

export default function DropZone({ label, hint, file, error, onSelect, onClear, disabled }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  function accept(file) {
    if (!file) return;
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      onSelect(null, "Only PDF files are accepted.");
      return;
    }
    if (file.size > MAX_SIZE) {
      onSelect(null, "File is larger than 30 MB.");
      return;
    }
    onSelect(file, null);
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
        {file && (
          <button
            type="button"
            onClick={onClear}
            disabled={disabled}
            className="text-xs font-medium text-slate-400 transition hover:text-red-500"
          >
            Remove
          </button>
        )}
      </div>

      <div
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
        className={`flex min-h-[104px] cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed px-4 py-3 transition ${
          dragOver
            ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-500/10"
            : error
              ? "border-red-300 bg-red-50/50 dark:border-red-500/40 dark:bg-red-500/5"
              : file
                ? "border-emerald-300 bg-emerald-50/40 dark:border-emerald-500/40 dark:bg-emerald-500/5"
                : "border-slate-300 bg-slate-50 hover:border-indigo-300 hover:bg-indigo-50/40 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-indigo-500 dark:hover:bg-indigo-500/10"
        } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
      >
        {file ? (
          <>
            <PdfIcon className="h-8 w-8 shrink-0 text-red-500" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">{file.name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
            <CheckBadge />
          </>
        ) : (
          <>
            <UploadGlyph />
            <div>
              <p className="text-sm font-medium text-slate-600">
                Drop PDF here or <span className="text-indigo-600 dark:text-indigo-400">browse</span>
              </p>
              <p className="mt-0.5 text-xs text-slate-400">{hint}</p>
            </div>
          </>
        )}
      </div>

      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={(e) => {
          accept(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
    </div>
  );
}

function CheckBadge() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 text-emerald-500">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function UploadGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
         className="h-7 w-7 shrink-0 text-slate-400">
      <path strokeLinecap="round" strokeLinejoin="round"
            d="M12 16V4m0 0L8 8m4-4l4 4m4 8v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2" />
    </svg>
  );
}
