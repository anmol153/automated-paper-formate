import axios from "axios";
import { getToken, setToken, removeToken } from "../utils/auth";

// Relative by default: the Vite dev server proxies /api to the backend, which
// keeps the browser same-origin. VITE_API_BASE points a deployed build at a
// separate API host, and the component test at a known port.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api/v1",
  timeout: 120_000,
});

// Request interceptor to add the token to the Authorization header
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

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

export async function getDiscussionThread(submissionId) {
  const { data } = await api.get(`/submissions/${submissionId}/discussion`);
  return data;
}

export async function addDiscussionMessage(submissionId, authorId, text) {
  const { data } = await api.post(`/submissions/${submissionId}/discussion`, {
    author_id: authorId,
    text,
  });
  return data;
}

/* ------------------------------------------------------------------ */
/* conferences                                                         */
/* ------------------------------------------------------------------ */

export async function listConferences() {
  const { data } = await api.get("/conferences");
  return data.conferences ?? [];
}

export async function getConference(confId) {
  const { data } = await api.get(`/conferences/${confId}`);
  return data;
}

export async function createConference(payload) {
  const { data } = await api.post("/conferences", payload);
  return data;
}

export async function updateConference(confId, payload) {
  const { data } = await api.patch(`/conferences/${confId}`, payload);
  return data;
}

export async function deleteConference(confId) {
  const { data } = await api.delete(`/conferences/${confId}`);
  return data;
}

export async function addConferenceMember(confId, userId, role) {
  const { data } = await api.post(`/conferences/${confId}/members`, {
    user_id: userId,
    role,
  });
  return data;
}

export async function removeConferenceMember(confId, userId) {
  const { data } = await api.delete(`/conferences/${confId}/members/${userId}`);
  return data;
}

export async function listConferenceSubmissions(confId) {
  const { data } = await api.get(`/conferences/${confId}`);
  return data.submissions ?? [];
}

/* ------------------------------------------------------------------ */
/* issues                                                              */
/* ------------------------------------------------------------------ */

export async function listIssues(submissionId) {
  const { data } = await api.get(`/submissions/${submissionId}/issues`);
  return data;
}

export async function getIssue(issueId) {
  const { data } = await api.get(`/issues/${issueId}`);
  return data;
}

export async function updateIssue(issueId, payload) {
  const { data } = await api.patch(`/issues/${issueId}`, payload);
  return data;
}

export async function addIssueComment(issueId, text) {
  const { data } = await api.post(`/issues/${issueId}/comments`, { text });
  return data;
}

/* ------------------------------------------------------------------ */
/* auth                                                                */
/* ------------------------------------------------------------------ */

export async function login(email, password) {
  const { data } = await api.post("/auth/login", new URLSearchParams({ username: email, password }));
  setToken(data.access_token);
  return data;
}

export async function register(email, password, full_name) {
  const { data } = await api.post("/auth/register", {
    email,
    password,
    full_name,
  });
  setToken(data.access_token);
  return data;
}

export async function logout() {
  removeToken();
}

/* ------------------------------------------------------------------ */
/* notifications                                                      */
/* ------------------------------------------------------------------ */

export async function listUnreadNotifications(submissionId) {
  const { data } = await api.get(`/notifications/unread?submissionId=${submissionId}`);
  return data;
}

export async function listNotifications(unreadOnly = false) {
  const { data } = await api.get(`/notifications?unread=${unreadOnly}`);
  return data;
}

export async function countUnreadNotifications() {
  const { data } = await api.get("/notifications/count-unread");
  return data;
}

export async function markNotificationRead(notificationId) {
  const { data } = await api.patch(`/notifications/${notificationId}`);
  return data;
}

export async function markAllNotificationsRead() {
  const { data } = await api.patch(`/notifications/read-all`);
  return data;
}

/* ------------------------------------------------------------------ */
/* template diff                                                      */
/* ------------------------------------------------------------------ */

export async function diffTemplateVersions(confId, oldTemplateId, newTemplateId) {
  const { data } = await api.post(`/api/v1/conferences/diff`, {
    old_template_id: oldTemplateId,
    new_template_id: newTemplateId,
  });
  return data;
}

/* ------------------------------------------------------------------ */
/* latest template                                                    */
/* ------------------------------------------------------------------ */

export async function getLatestTemplateVersion(confId) {
  const { data } = await api.get(`/conferences/${confId}/latest`);
  return data;
}