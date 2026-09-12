const META = {
  pdf: { label: "PDF", color: "text-red-500" },
  tex: { label: "TEX", color: "text-violet-500" },
  latex: { label: "TEX", color: "text-violet-500" },
  docx: { label: "DOCX", color: "text-blue-500" },
};

export default function FileIcon({ name, className }) {
  const ext = String((name || "").split(".").pop() || "").toLowerCase();
  const meta = META[ext] || { label: "DOC", color: "text-slate-500" };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className={`${className} ${meta.color}`}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5A3.375 3.375 0 0010.125 2.25H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
      />
      <text x="12" y="15.6" textAnchor="middle" fontSize="6.4" fontWeight="800" fill="currentColor" stroke="none">
        {meta.label}
      </text>
    </svg>
  );
}