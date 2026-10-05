import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { CATEGORY_LABELS, CATEGORY_ORDER, CHECK_STATUS_META, VERDICT_META } from "../lib/ruleOptions.js";
import FileIcon from "../components/FileIcon.jsx";

export default function Results() {
  const location = useLocation();
  const report = location.state?.report;
  const isDemo = Boolean(location.state?.demo);

  const isBatch = Boolean(report?.papers);

  const papers = useMemo(() => {
    if (!report) return [];
    if (isBatch) return report.papers;
    return [
      {
        filename: report.filename ?? report.paper_filename ?? "Paper",
        format: report.paper_format ?? "",
        verdict: report.score === 100 ? "accepted" : "needs_review",
        score: report.score,
        passed: report.passed,
        failed: report.failed,
        missing: report.missing,
        results: report.results ?? [],
        metadata: report.metadata,
        summary_line: "",
        action_required: null,
      },
    ];
  }, [report, isBatch]);

  if (!report) {
    return (
      <div className="animate-fade-in max-w-md mx-auto text-center">
        <div className="panel p-8">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-16 w-16 mx-auto text-surface-300 dark:text-surface-600 mb-4" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h1 className="text-xl font-bold text-surface-900 dark:text-surface-50 mb-2">No report yet</h1>
          <p className="text-sm text-surface-600 dark:text-surface-400 mb-6">Submit a paper or run a comparison to see results here.</p>
          <Link to="/submit" className="btn-primary inline-flex">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 mr-2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Submit a paper
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      {isBatch ? <BatchHeader report={report} /> : <SingleHeader report={report} demo={isDemo} />}

      <div className="mt-8 space-y-4">
        {papers.map((paper, index) => (
          <PaperCard key={`${paper.filename}-${index}`} paper={paper} defaultOpen={index === 0} />
        ))}
      </div>

      <div className="mt-12 text-center animate-fade-in">
        <Link to="/submit" className="text-sm font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 inline-flex items-center gap-1">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Check more papers
        </Link>
      </div>
    </div>
  );
}

function BatchHeader({ report }) {
  const total = report.papers?.length ?? 0;
  const accepted = report.accepted ?? 0;
  const needsReview = report.needs_review ?? 0;
  const rejected = report.rejected ?? 0;

  return (
    <section className="panel animate-slide-up" aria-labelledby="batch-heading">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 id="batch-heading" className="text-xl font-bold tracking-tight text-surface-900 dark:text-surface-50">
            {report.template_name || "Submission"} checked
          </h1>
          <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
            {total} paper{total === 1 ? "" : "s"}
            {report.source === "drive" ? " from a Google Drive folder" : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <VerdictChip verdict="accepted" count={accepted} />
          <VerdictChip verdict="needs_review" count={needsReview} />
          <VerdictChip verdict="rejected" count={rejected} />
        </div>
      </div>
      {report.publisher?.notes_for_authors && (
        <div className="mt-4 pt-4 border-t border-surface-200 dark:border-surface-800">
          <p className="text-xs leading-relaxed text-surface-500 dark:text-surface-400">
            {report.publisher.notes_for_authors}
            {report.publisher.contact_email && (
              <>
                {" "}
                Questions?{" "}
                <a
                  href={`mailto:${report.publisher.contact_email}`}
                  className="font-medium text-primary-600 hover:underline dark:text-primary-400"
                >
                  {report.publisher.contact_email}
                </a>
              </>
            )}
          </p>
        </div>
      )}
    </section>
  );
}

function VerdictChip({ verdict, count }) {
  const meta = VERDICT_META[verdict];
  return (
    <span className={`badge ${meta.chip} gap-1.5`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} aria-hidden="true" />
      <span className="font-semibold">{count}</span>
      <span className="font-medium capitalize">{meta.label.toLowerCase()}</span>
    </span>
  );
}

function SingleHeader({ report, demo }) {
  const total = (report.passed ?? 0) + (report.failed ?? 0) + (report.missing ?? 0);
  const passed = report.passed ?? 0;
  const failed = report.failed ?? 0;
  const missing = report.missing ?? 0;
  const metadata = report.metadata ?? {};

  return (
    <section className="panel animate-slide-up" aria-labelledby="single-heading">
      <div className="flex flex-row items-center gap-6">
        <div className="rotate-90"><ScoreRing score={report.score ?? 0} /></div>
        <div className="flex-1 min-w-0 text-left">
          {metadata.title && (
            <div className="mb-2">
              <FileIcon name={report.filename ?? "paper"} className="h-5 w-5 inline-block text-surface-400" />
              <span className="ml-2 text-sm font-medium text-surface-900 dark:text-surface-50">
                {metadata.title}
              </span>
            </div>
          )}
          {metadata.authors?.length && (
            <p className="mb-2 text-sm text-primary-600 dark:text-primary-400">
              {metadata.authors.join(", ")}
            </p>
          )}
          <h1 id="single-heading" className="text-xl font-bold tracking-tight text-surface-900 dark:text-surface-50">
            Overall compliance: <span className="text-primary-600 dark:text-primary-400">{report.score}%</span>
          </h1>
          <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
            {total} requirements evaluated{demo && " &middot; demo data"}
          </p>
          <div className="mt-4 flex gap-2">
            <StatChip label="Passed" value={passed} color="success" />
            <StatChip label="Failed" value={failed} color="danger" />
            <StatChip label="Missing" value={missing} color="warning" />
          </div>
        </div>
      </div>
    </section>
  );
}

function StatChip({ label, value, color }) {
  const colors = {
    success: "bg-success-50 text-success-700 border-success-200 dark:bg-success-500/10 dark:text-success-300 dark:border-success-500/30",
    danger: "bg-danger-50 text-danger-700 border-danger-200 dark:bg-danger-500/10 dark:text-danger-300 dark:border-danger-500/30",
    warning: "bg-warning-50 text-warning-700 border-warning-200 dark:bg-warning-500/10 dark:text-warning-300 dark:border-warning-500/30",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold ${colors[color]}`}>
      <span className="font-bold text-sm">{value}</span>
      <span>{label.toLowerCase()}</span>
    </span>
  );
}

function ScoreRing({ score }) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);
  const stroke = score >= 80 ? "#059669" : score >= 50 ? "#d97706" : "#dc2626";
  const strokeClass = score >= 80 ? "text-success-500" : score >= 50 ? "text-warning-500" : "text-danger-500";

  return (
    <div className="shrink-0 flex items-center justify-center" aria-label={`Compliance score: ${score}%`}>
      <svg width="108" height="108" viewBox="0 0 108 108" className="progress-ring">
        <circle cx="54" cy="54" r={radius} stroke="var(--score-track)" strokeWidth="10" fill="none" />
        <circle
          className="progress-ring-circle"
          cx="54"
          cy="54"
          r={radius}
          stroke={stroke}
          strokeWidth="10"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transform: `rotate(-90deg)`, transformOrigin: "center" }}
        />
        <text
          x="54"
          y="54"
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-surface-900 text-2xl font-bold dark:fill-surface-50"
        >
          {score}
        </text>
      </svg>
    </div>
  );
}

function PaperCard({ paper, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = VERDICT_META[paper.verdict] ?? VERDICT_META.needs_review;
  const issues = (paper.results ?? []).filter((r) => r.status === "failed" || r.status === "missing");
  const blocking = issues.filter((r) => r.severity === "blocking");
  const metadata = paper.metadata ?? {};

  return (
    <section className="panel animate-slide-up" aria-labelledby={`paper-${paper.filename}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={`paper-content-${paper.filename}`}
        id={`paper-${paper.filename}`}
        className="accordion-trigger"
      >
        <span className={`h-3 w-3 shrink-0 rounded-full ${meta.dot}`} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <FileIcon name={paper.filename} className="h-5 w-5 flex-shrink-0 text-surface-400" />
            <p className="truncate text-sm font-semibold text-surface-800 dark:text-surface-100">
              {paper.filename}
            </p>
          </div>
          {metadata.title && (
            <p className="mt-1.5 text-sm font-medium text-surface-900 dark:text-surface-50 truncate">
              {metadata.title}
            </p>
          )}
          {metadata.authors?.length && (
            <p className="mt-0.5 text-xs text-primary-600 dark:text-primary-400 truncate">
              {metadata.authors.join(", ")}
            </p>
          )}
          <p className="mt-0.5 text-xs text-surface-500 dark:text-surface-400">
            {[
              paper.format ? paper.format.toUpperCase() : null,
              meta.label,
              issues.length ? `${issues.length} issue${issues.length === 1 ? "" : "s"}` : "no issues",
              paper.score !== undefined ? `${paper.score}%` : null,
            ]
              .filter(Boolean)
              .join(" &middot; ")}
          </p>
        </div>
        <span className={`shrink-0 text-surface-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </span>
      </button>

      {paper.action_required && (
        <div className="border-t border-surface-200 px-5 py-3 bg-primary-50 dark:bg-primary-500/10 dark:border-surface-800">
          <p className="text-sm text-surface-700 dark:text-surface-300">
            <span className="font-semibold text-primary-700 dark:text-primary-300">What to do: </span>
            {paper.action_required}
          </p>
        </div>
      )}

      <div id={`paper-content-${paper.filename}`} className="accordion-content animate-slide-down" hidden={!open}>
        {blocking.length > 0 && (
          <div className="border-b border-surface-200 dark:border-surface-800">
            <h3 className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-danger-600 dark:text-danger-400">
              Blocking issues ({blocking.length})
            </h3>
            <ul className="divide-y divide-surface-200 dark:divide-surface-800/60">
              {blocking.map((item) => (
                <BlockingRow key={item.id || item.name} item={item} />
              ))}
            </ul>
          </div>
        )}
        <Details results={paper.results ?? []} />
      </div>
    </section>
  );
}

function BlockingRow({ item }) {
  return (
    <li className="bg-danger-50/40 px-5 py-4 dark:bg-danger-500/5">
      <div className="flex gap-3">
        <span className="mt-0.5 w-5 shrink-0 text-center font-bold text-danger-500">✗</span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-surface-800 dark:text-surface-100">{item.name}</p>
          <p className="mt-1 text-xs text-surface-600 dark:text-surface-400">
            <span className="font-medium text-surface-400">Expected: </span>
            {display(item.expected)}
            <span className="mx-1.5 text-surface-300 dark:text-surface-600">|</span>
            <span className="font-medium text-surface-400">Found: </span>
            {display(item.actual)}
          </p>
          {item.advice && (
            <p className="mt-2 text-xs leading-relaxed text-surface-700 dark:text-surface-300">
              <span className="font-medium text-primary-700 dark:text-primary-300">Advice: </span>
              {item.advice}
            </p>
          )}
          {item.evidence && (
            <p className="mt-1 text-[11px] leading-relaxed text-surface-400 font-mono">
              {item.evidence}
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

function Details({ results }) {
  const grouped = useMemo(() => {
    const map = new Map();
    for (const item of results) {
      const category = item.category ?? "other";
      if (!map.has(category)) map.set(category, []);
      map.get(category).push(item);
    }
    return CATEGORY_ORDER.filter((c) => map.has(c)).map((c) => [c, map.get(c)]);
  }, [results]);

  if (grouped.length === 0) return null;

  return (
    <details className="px-5 py-3">
      <summary className="cursor-pointer list-none flex items-center gap-2 text-xs font-semibold text-surface-500 hover:text-primary-600 dark:text-surface-400 dark:hover:text-primary-400">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Show all {results.length} checks
      </summary>
      <div className="mt-4 space-y-5 animate-slide-down">
        {grouped.map(([category, items]) => (
          <div key={category}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-surface-400">
              {CATEGORY_LABELS[category] ?? category}
            </p>
            <ul className="divide-y divide-surface-100 rounded-xl border border-surface-200 dark:divide-surface-800/60 dark:border-surface-800 overflow-hidden">
              {items.map((item) => (
                <CheckRow key={item.id || item.name} item={item} />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </details>
  );
}

function CheckRow({ item }) {
  const meta = CHECK_STATUS_META[item.status] ?? CHECK_STATUS_META.not_applicable;
  const isBlocking = item.severity === "blocking" && item.status !== "passed";

  return (
    <li className={`flex gap-3 px-4 py-3 ${meta.row}`}>
      <span className={`mt-0.5 w-5 shrink-0 text-center font-bold ${meta.text}`}>{meta.icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm text-surface-800 dark:text-surface-100">{item.name}</p>
          {isBlocking && (
            <span className="badge badge-danger text-[10px]">
              Blocking
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
          <span className="font-medium text-surface-400">Expected: </span>
          {display(item.expected)}
          <span className="mx-1.5 text-surface-300 dark:text-surface-600">|</span>
          <span className="font-medium text-surface-400">Found: </span>
          {display(item.actual)}
        </p>
        {item.confidence && item.confidence !== "high" && item.status !== "passed" && (
          <p className="mt-1 text-[11px] text-surface-400">
            Confidence: {item.confidence}
            {item.confidence === "low"
              ? " &mdash; this could not be measured reliably for this file type."
              : ""}
          </p>
        )}
        {item.advice && item.status !== "passed" && (
          <p className="mt-2 text-xs leading-relaxed text-surface-700 dark:text-surface-300">
            <span className="font-medium text-primary-700 dark:text-primary-300">Advice: </span>
            {item.advice}
          </p>
        )}
      </div>
    </li>
  );
}

function display(value) {
  if (value === null || value === undefined || value === "") return "not specified";
  if (typeof value === "object") {
    return Object.entries(value)
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([k, v]) => `${k}: ${v}`)
      .join(", ");
  }
  return String(value);
}