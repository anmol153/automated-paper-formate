import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listReports, getReport, deleteReport } from "../lib/api.js";
import { VERDICT_META } from "../lib/ruleOptions.js";
import FileIcon from "../components/FileIcon.jsx";

export default function Reports() {
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(new Set());

  useEffect(() => {
    loadReports();
  }, []);

  async function loadReports() {
    try {
      setLoading(true);
      setError(null);
      const data = await listReports();
      setReports(data);
    } catch (err) {
      setError(err.message || "Failed to load reports");
    } finally {
      setLoading(false);
    }
  }

  async function handleOpen(report) {
    try {
      const fullReport = await getReport(report.filename);
      navigate("/results", { state: { report: fullReport } });
    } catch (err) {
      setError(err.message || "Failed to open report");
    }
  }

  async function handleDelete(filename) {
    if (!window.confirm("Delete this report? This cannot be undone.")) return;
    try {
      setDeleting((prev) => new Set(prev).add(filename));
      await deleteReport(filename);
      setReports((prev) => prev.filter((r) => r.filename !== filename));
    } catch (err) {
      setError(err.message || "Failed to delete report");
    } finally {
      setDeleting((prev) => {
        const next = new Set(prev);
        next.delete(filename);
        return next;
      });
    }
  }

  function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatAuthors(authors, max = 2) {
    if (!authors?.length) return "";
    const shown = authors.slice(0, max);
    const rest = authors.length - max;
    return shown.join(", ") + (rest > 0 ? ` +${rest} more` : "");
  }

  function getVerdictClass(verdict) {
    const meta = VERDICT_META[verdict] ?? VERDICT_META.needs_review;
    return `badge ${meta.chip}`;
  }

  if (loading) {
    return (
      <div className="panel" style={{ minHeight: 300 }}>
        <div className="flex items-center justify-center h-full gap-3">
          <svg className="animate-spin h-6 w-6 text-primary-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
          </svg>
          <span className="text-surface-600 dark:text-surface-400">Loading reports…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel">
        <div className="flex items-center gap-3 p-4 text-danger-700 dark:text-danger-300 bg-danger-50 dark:bg-danger-500/10 rounded-xl">
          <svg className="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <span>{error}</span>
          <button className="ml-auto btn-ghost text-sm" onClick={loadReports}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h1 className="section-title">Report History</h1>
          <p className="section-subtitle">
            Previously generated compliance reports. Click a report to view details.
          </p>
        </div>
      </div>

      {reports.length === 0 ? (
        <div className="empty-state py-16">
          <svg className="mx-auto h-16 w-16 text-surface-300 dark:text-surface-600" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-surface-700 dark:text-surface-300">No reports yet</h3>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400 max-w-xs mx-auto">
            Submit a paper or run a comparison to generate your first compliance report.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => (
            <div
              key={report.filename}
              className="card-base card-hover flex items-center gap-4 p-4"
              onClick={() => handleOpen(report)}
              style={{ cursor: "pointer" }}
            >
              <FileIcon name={report.filename} className="h-12 w-12 flex-shrink-0" />

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-surface-900 dark:text-surface-50 truncate">
                    {report.paper_title || report.filename}
                  </span>
                  {report.authors?.length && (
                    <span className="text-sm text-surface-500 dark:text-surface-400 whitespace-nowrap">
                      {formatAuthors(report.authors)}
                    </span>
                  )}
                </div>

                <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-surface-500 dark:text-surface-400">
                  <span className="flex items-center gap-1">
                    <FileIcon name={report.filename} className="h-3.5 w-3.5" />
                    {report.format?.toUpperCase() || "—"}
                  </span>
                  {report.template_name && (
                    <span className="flex items-center gap-1 truncate max-w-[200px]">
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      {report.template_name}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {formatDate(report.updated_at)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className={getVerdictClass(report.verdict)}>
                  {report.score !== undefined && report.score !== null ? `${report.score}%` : "—"}
                </span>
                <button
                  className="btn-ghost text-danger-600 dark:text-danger-400 hover:bg-danger-50 dark:hover:bg-danger-500/10"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(report.filename);
                  }}
                  disabled={deleting.has(report.filename)}
                  aria-label="Delete report"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}