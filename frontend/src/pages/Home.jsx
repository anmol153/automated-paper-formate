import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DropZone from "../components/DropZone.jsx";
import { compareDemo, compareDocuments, errorMessage } from "../lib/api.js";

export default function Home() {
  const navigate = useNavigate();
  const [templateFile, setTemplateFile] = useState(null);
  const [paperFile, setPaperFile] = useState(null);
  const [errors, setErrors] = useState({ template: null, paper: null });
  const [globalError, setGlobalError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);

  function selectTemplate(file, error) {
    setTemplateFile(file);
    setErrors((prev) => ({ ...prev, template: error }));
  }

  function selectPaper(file, error) {
    setPaperFile(file);
    setErrors((prev) => ({ ...prev, paper: error }));
  }

  const ready = templateFile && paperFile && !loading;

  async function handleCompare(event) {
    event.preventDefault();
    if (!ready) return;
    setGlobalError(null);
    setLoading(true);
    setProgress(0);
    try {
      const report = await compareDocuments(templateFile, paperFile, setProgress);
      navigate("/results", { state: { report } });
    } catch (err) {
      setGlobalError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleDemo() {
    setGlobalError(null);
    setLoading(true);
    try {
      const report = await compareDemo();
      navigate("/results", { state: { report, demo: true } });
    } catch (err) {
      setGlobalError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Check a paper against a template</h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
        Upload two PDFs. The template's formatting rules are extracted and compared against the
        research paper — page setup, typography, paragraph formatting and required sections.
      </p>

      <form
        onSubmit={handleCompare}
        className="mt-8 space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <DropZone
          label="Template PDF"
          hint="Journal/conference formatting guidelines or sample"
          file={templateFile}
          error={errors.template}
          onSelect={selectTemplate}
          onClear={() => selectTemplate(null, null)}
          disabled={loading}
        />

        <DropZone
          label="Research paper PDF"
          hint="The manuscript you want to check"
          file={paperFile}
          error={errors.paper}
          onSelect={selectPaper}
          onClear={() => selectPaper(null, null)}
          disabled={loading}
        />

        {globalError && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
            {globalError}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            type="submit"
            disabled={!ready}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Compare
          </button>
          <button
            type="button"
            onClick={handleDemo}
            disabled={loading}
            className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            Try demo data
          </button>

          {loading && progress > 0 && progress < 100 && (
            <div className="flex items-center gap-3">
              <ProgressBar value={progress} />
              <span className="text-xs font-medium text-slate-500 tabular-nums dark:text-slate-400">{progress}%</span>
            </div>
          )}
          {loading && (progress >= 100 || progress === 0) && (
            <span className="text-sm text-slate-500 dark:text-slate-400">Analyzing documents…</span>
          )}
        </div>
      </form>

      <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200/90">
        Text-based PDFs only — scanned documents without extractable text are not supported yet.
        Files never leave your machine except to the backend performing the analysis.
      </div>
    </div>
  );
}

function ProgressBar({ value }) {
  return (
    <div className="h-1.5 w-40 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
      <div
        className="h-full rounded-full bg-indigo-500 transition-all duration-200"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}
