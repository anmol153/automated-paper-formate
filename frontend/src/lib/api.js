import axios from "axios";

// Relative by default: the Vite dev server proxies /api to the backend, which
// keeps the browser same-origin. VITE_API_BASE points a deployed build at a
// separate API host, and the component test at a known port.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api/v1",
  timeout: 120_000,
});

/* ------------------------------------------------------------------ */
/* legacy: template-vs-paper comparison                                */
/* ------------------------------------------------------------------ */

export async function compareDocuments(templateFile, paperFile, onProgress) {
  const formData = new FormData();
  formData.append("template", templateFile);
  formData.append("paper", paperFile);
  const { data } = await api.post("/compare", formData, {
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return data;
}

export async function compareDemo() {
  const formData = new FormData();
  formData.append("demo", "true");
  const { data } = await api.post("/compare", formData);
  return data;
}

export async function parsePdf(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/parse", formData);
  return data;
}

/* ------------------------------------------------------------------ */
/* publisher templates (conference manager setup)                      */
/* ------------------------------------------------------------------ */

export async function getRuleSchema() {
  const { data } = await api.get("/rule-schema");
  return data;
}

export async function listTemplates() {
  const { data } = await api.get("/templates");
  return data.templates ?? [];
}

/**
 * Infer a rule set from an uploaded template. This is a preview only: the
 * returned rules are not saved until the manager accepts them via createTemplate.
 */
export async function importTemplate(file, name = "") {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  const { data } = await api.post("/templates/import", formData);
  return data;
}

export async function createTemplate(rules) {
  const { data } = await api.post("/templates", rules);
  return data;
}

export async function getTemplate(templateId) {
  const { data } = await api.get(`/templates/${templateId}`);
  return data;
}

export async function updateTemplate(templateId, rules) {
  const { data } = await api.put(`/templates/${templateId}`, rules);
  return data;
}

export async function deleteTemplate(templateId) {
  const { data } = await api.delete(`/templates/${templateId}`);
  return data;
}

/* ------------------------------------------------------------------ */
/* submissions                                                         */
/* ------------------------------------------------------------------ */

/**
 * Submit one or many papers. FormData.append must be called once per file:
 * that produces one multipart part each, which is what the backend binds to
 * `files: list[UploadFile]`.
 */
export async function submitPapers(files, { templateId, rules, onProgress } = {}) {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);
  if (templateId) formData.append("template_id", templateId);
  else if (rules) formData.append("rules", JSON.stringify(rules));
  const { data } = await api.post("/submissions", formData, {
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return data;
}

export async function getDriveStatus() {
  const { data } = await api.get("/drive/status");
  return data;
}

export async function previewDriveFolder(folderUrl, recursive = true) {
  const { data } = await api.post("/drive/preview", { folder_url: folderUrl, recursive });
  return data;
}

export async function submitFromDrive(folderUrl, { templateId, rules, recursive = true } = {}) {
  const { data } = await api.post("/submissions/drive", {
    folder_url: folderUrl,
    template_id: templateId ?? null,
    rules: rules ?? null,
    recursive,
  });
  return data;
}

/* ------------------------------------------------------------------ */
/* errors                                                              */
/* ------------------------------------------------------------------ */

export function errorMessage(error) {
  if (error?.response?.data?.detail) {
    const detail = error.response.data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const where = Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "";
          return where ? `${where}: ${d.msg}` : d.msg;
        })
        .join("; ");
    }
    return JSON.stringify(detail);
  }
  if (error?.code === "ECONNABORTED") return "Request timed out.";
  if (error?.message === "Network Error")
    return "Cannot reach the backend. Is it running on http://localhost:8000?";
  return error?.message || "Unexpected error.";
}

/* ------------------------------------------------------------------ */
/* report history                                                      */
/* ------------------------------------------------------------------ */

export async function listReports() {
  const { data } = await api.get("/reports");
  return data.reports ?? [];
}

export async function getReport(filename) {
  const encoded = encodeURIComponent(filename);
  const { data } = await api.get(`/reports/${encoded}`);
  return data;
}

export async function deleteReport(filename) {
  const encoded = encodeURIComponent(filename);
  const { data } = await api.delete(`/reports/${encoded}`);
  return data;
}
