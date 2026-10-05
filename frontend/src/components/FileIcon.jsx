const META = {
  pdf: { label: "PDF", color: "text-red-500", bg: "bg-red-50 dark:bg-red-500/10" },
  tex: { label: "TEX", color: "text-violet-500", bg: "bg-violet-50 dark:bg-violet-500/10" },
  latex: { label: "TEX", color: "text-violet-500", bg: "bg-violet-50 dark:bg-violet-500/10" },
  ltx: { label: "TEX", color: "text-violet-500", bg: "bg-violet-50 dark:bg-violet-500/10" },
  docx: { label: "DOCX", color: "text-blue-500", bg: "bg-blue-50 dark:bg-blue-500/10" },
};

export default function FileIcon({ name, className = "" }) {
  const ext = String((name || "").split(".").pop() || "").toLowerCase();
  const meta = META[ext] || { label: "DOC", color: "text-slate-500", bg: "bg-surface-100 dark:bg-surface-800" };

  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={`${className} ${meta.color}`} aria-hidden="true">
      <defs>
        <linearGradient id="docGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.1" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <path
        fill="url(#docGradient)"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.25 3.75v1.5c0 .621.504 1.125 1.125 1.125h4.125c.621 0 1.125-.504 1.125-1.125V3.75a1.125 1.125 0 00-1.125-1.125h-4.125a1.125 1.125 0 00-1.125 1.125zM19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5A3.375 3.375 0 0010.125 2.25H8.25a3.375 3.375 0 00-3.375 3.375v15.75a3.375 3.375 0 003.375 3.375h12.75a3.375 3.375 0 003.375-3.375V14.25z"
      />
      <text x="12" y="15.8" textAnchor="middle" fontSize="5.5" fontWeight="700" fill="currentColor" stroke="none" fontFamily="system-ui, sans-serif">
        {meta.label}
      </text>
    </svg>
  );
}