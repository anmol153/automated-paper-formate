import { Link, useLocation } from "react-router-dom";
import { useMemo } from "react";

const CATEGORIES = [
  { key: "document", label: "Document" },
  { key: "typography", label: "Typography" },
  { key: "paragraph", label: "Paragraph Formatting" },
  { key: "structure", label: "Structure & Sections" },
];

export default function Results() {
  const location = useLocation();
  const report = location.state?.report;
  const isDemo = Boolean(location.state?.demo);

  const grouped = useMemo(() => {
    if (!report) return null;
    return Object.fromEntries(
      CATEGORIES.map((c) => [c.key, report.results.filter((r) => r.category === c.key)])
    );
  }, [report]);

  if (!report) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-slate-600 dark:text-slate-400">No report yet.</p>
        <Link to="/" className="mt-3 inline-block text-sm font-semibold text-indigo-600 hover:text-indigo-700">
          Run a comparison first
        </Link>
      </div>
    );
  }

  return (
    <div>
      <ScoreCard report={report} demo={isDemo} />

      <div className="mt-10 space-y-8">
        {CATEGORIES.map(({ key, label }) => {
          const items = grouped[key];
          if (!items.length) return null;
          return <CategorySection key={key} label={label} items={items} />;
        })}
      </div>

      <div className="mt-10 text-center">
        <Link to="/" className="text-sm font-semibold text-indigo-600 hover:text-indigo-700">
          Compare another pair
        </Link>
      </div>
    </div>
  );
}

function ScoreCard({ report, demo }) {
  const { score, passed, failed, missing } = report;
  const total = passed + failed + missing;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-col items-center gap-6 px-6 py-8 sm:flex-row sm:px-10">
        <ScoreRing score={score} />
        <div className="flex-1 text-center sm:text-left">
          <h1 className="text-xl font-bold tracking-tight">Overall Compliance: {score}%</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {total} requirements evaluated
            {demo && " · demo data"}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2 sm:justify-start">
            <Chip tone="green" label={`✓ ${passed} matched`} title="Passed checks" />
            <Chip tone="red" label={`✗ ${failed} issues`} title="Failed checks" />
            <Chip tone="amber" label={`⚠ ${missing} missing`} title="Missing required elements" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x divide-slate-100 border-t border-slate-100 text-center dark:divide-slate-800 dark:border-slate-800">
        <Stat label="Passed" value={passed} className="bg-emerald-50/50 dark:bg-emerald-500/5" />
        <Stat label="Failed" value={failed} className="bg-red-50/40 dark:bg-red-500/5" />
        <Stat label="Missing" value={missing} className="bg-amber-50/60 dark:bg-amber-500/5" />
      </div>
    </section>
  );
}

function ScoreRing({ score }) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);
  const stroke = score >= 80 ? "#059669" : score >= 50 ? "#d97706" : "#dc2626";

  return (
    <svg width="132" height="132" viewBox="0 0 132 132" className="shrink-0">
      <circle cx="66" cy="66" r={radius} stroke="var(--score-track)" strokeWidth="12" fill="none" />
      <circle
        cx="66"
        cy="66"
        r={radius}
        stroke={stroke}
        strokeWidth="12"
        fill="none"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${66} ${66})`}
        className="transition-all duration-700"
      />
      <text
        x="66"
        y="66"
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-slate-900 text-2xl font-bold dark:fill-slate-100"
      >
        {score}
      </text>
    </svg>
  );
}

function Stat({ label, value, className = "" }) {
  return (
    <div className={`px-4 py-4 ${className}`}>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

const TONES = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300",
  red: "border-red-200 bg-red-50 text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300",
  amber: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300",
};

function Chip({ tone, label, title }) {
  return (
    <span title={title} className={`rounded-full border px-3 py-1 text-xs font-semibold ${TONES[tone]}`}>
      {label}
    </span>
  );
}

const CATEGORY_ICONS = {
  document: "📄",
  typography: "🅰",
  paragraph: "¶",
  structure: "🧱",
};

function CategorySection({ label, items }) {
  const passedCount = items.filter((i) => i.status === "passed").length;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5 dark:border-slate-800">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          <span aria-hidden>{CATEGORY_ICONS[label.split(" ")[0].toLowerCase()] ?? ""}</span> {label}
        </h2>
        <span className="text-xs font-medium text-slate-400 dark:text-slate-500">
          {passedCount}/{items.length} passed
        </span>
      </header>
      <ul className="divide-y divide-slate-50 dark:divide-slate-800/60">
        {items.map((item) => (
          <CheckRow key={item.name + item.expected} item={item} />
        ))}
      </ul>
    </section>
  );
}

const STATUS_META = {
  passed: { icon: "✓", cls: "text-emerald-500 dark:text-emerald-400", rowCls: "" },
  failed: { icon: "✗", cls: "text-red-500 dark:text-red-400", rowCls: "bg-red-50/30 dark:bg-red-500/5" },
  missing: { icon: "⚠", cls: "text-amber-500 dark:text-amber-400", rowCls: "bg-amber-50/40 dark:bg-amber-500/5" },
};

function CheckRow({ item }) {
  const meta = STATUS_META[item.status];
  return (
    <li className={`flex gap-3 px-5 py-3.5 ${meta.rowCls}`}>
      <span className={`mt-0.5 w-4 shrink-0 text-center font-bold ${meta.cls}`}>{meta.icon}</span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">{item.name}</div>
        <div className="mt-0.5 flex flex-wrap gap-x-6 gap-y-0.5 text-xs text-slate-500 dark:text-slate-400">
          <ValueLine prefix="Expected" value={item.expected} />
          <ValueLine prefix="Found" value={item.actual} />
        </div>
      </div>
    </li>
  );
}

function ValueLine({ prefix, value }) {
  const display =
    value === null || value === undefined || value === ""
      ? "Not specified"
      : typeof value === "object"
        ? Object.entries(value)
            .map(([k, v]) => `${k}: ${v}`)
            .join(", ")
        : String(value);
  const isMissing = display === "Not specified" || display === "Missing";
  return (
    <span>
      <span className="font-medium text-slate-400">{prefix}: </span>
      <span className={isMissing ? "italic text-slate-400 dark:text-slate-500" : "font-medium text-slate-700 dark:text-slate-200"}>{display}</span>
    </span>
  );
}
