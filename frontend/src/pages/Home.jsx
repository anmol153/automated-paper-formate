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
    <div className="animate-fade-in max-w-3xl mx-auto">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-surface-900 dark:text-surface-50">Check a paper against a template</h1>
        <p className="mt-3 max-w-2xl mx-auto text-sm text-surface-600 dark:text-surface-400">
          Upload two documents. The template's formatting rules are extracted and compared against the
          research paper &mdash; page setup, typography, paragraph formatting and required sections.
          PDF, LaTeX (TEX) and Word (DOCX) files are supported, in any combination.
        </p>
      </header>

      <form onSubmit={handleCompare} className="space-y-6">
        <section className="panel animate-slide-up" aria-labelledby="template-heading">
          <div className="flex items-center justify-between mb-4">
            <h2 id="template-heading" className="panel-title">Template document</h2>
            {templateFile && (
              <span className="badge badge-success">
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3" aria-hidden="true">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                </svg>
                Ready
              </span>
            )}
          </div>
          <DropZone
            label="Template"
            hint="Journal/conference formatting guidelines or sample paper"
            file={templateFile}
            error={errors.template}
            onSelect={selectTemplate}
            onClear={() => selectTemplate(null, null)}
            disabled={loading}
          />
        </section>

        <section className="panel animate-slide-up" aria-labelledby="paper-heading">
          <div className="flex items-center justify-between mb-4">
            <h2 id="paper-heading" className="panel-title">Research paper</h2>
            {paperFile && (
              <span className="badge badge-success">
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3" aria-hidden="true">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                </svg>
                Ready
              </span>
            )}
          </div>
          <DropZone
            label="Research paper"
            hint="The manuscript you want to check"
            file={paperFile}
            error={errors.paper}
            onSelect={selectPaper}
            onClear={() => selectPaper(null, null)}
            disabled={loading}
          />
        </section>

        {globalError && (
          <div className="alert alert-danger animate-slide-down" role="alert">
            <div className="flex items-start gap-3">
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <p>{globalError}</p>
            </div>
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2 animate-fade-in">
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              type="submit"
              disabled={!ready}
              className="btn-primary flex-1 min-h-[48px]"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Compare documents
            </button>
            <button
              type="button"
              onClick={handleDemo}
              disabled={loading}
              className="btn-secondary flex-1 min-h-[48px]"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Try demo data
            </button>
          </div>

          {loading && (
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="h-2 w-48 overflow-hidden rounded-full bg-surface-200 dark:bg-surface-700">
                <div
                  className="h-full rounded-full bg-primary-500 transition-all duration-300 ease-out"
                  style={{ width: progress > 0 && progress < 100 ? `${progress}%` : "100%" }}
                  role="progressbar"
                  aria-valuenow={progress > 0 && progress < 100 ? progress : 100}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Analysis progress"
                />
              </div>
              <span className="text-sm font-medium text-surface-500 tabular-nums dark:text-surface-400 w-10 text-right">
                {progress > 0 && progress < 100 ? `${progress}%` : "Analyzing&hellip;"}
              </span>
            </div>
          )}
        </div>
      </form>

      <div className="mt-6 alert alert-warning animate-fade-in" role="note">
        <div className="flex items-start gap-3">
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0111 6zm-1 8a.75.75 0 101.5 0H11.5a.75.75 0 000 1.5H10a.75.75 0 00-.75-.75z" clipRule="evenodd" />
          </svg>
          <div className="text-xs leading-relaxed text-warning-800 dark:text-warning-200">
            <p className="font-medium">Supported formats & limitations</p>
            <p className="mt-1">PDF, TEX and DOCX files are analyzed &mdash; scanned PDFs without extractable text are not supported yet. Files never leave your machine except to the backend performing the analysis.</p>
          </div>
        </div>
      </div>
    </div>
  );
}