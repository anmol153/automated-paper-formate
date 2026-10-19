import axios from "axios";
import { getCsrfToken, removeToken } from "../utils/auth";

// Relative by default: the Vite dev server proxies /api to the backend, which
// keeps the browser same-origin. VITE_API_BASE points a deployed build at a
// separate API host, and the component test at a known port.
export const api = axios.create({
  // Browser development uses Vite's same-origin proxy. The server-rendered test
  // harness and deployed builds may select a separate API host explicitly.
  baseURL: import.meta.env.DEV && !import.meta.env.SSR ? "/api/v1" : (import.meta.env.VITE_API_BASE || "/api/v1"),
  timeout: 120_000,
  withCredentials: true,
});

// Cookie sessions use a separate CSRF header for state-changing requests.
api.interceptors.request.use((config) => {
  const csrf = getCsrfToken();
  if (csrf && !["get", "head", "options"].includes((config.method || "get").toLowerCase())) {
    config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && error?.config?.url !== "/auth/google/complete" && typeof window !== "undefined") {
      window.dispatchEvent(new Event("paper:session-expired"));
    }
    return Promise.reject(error);
  },
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

export async function createConferenceSubmission(confId, file, { submitForReview = true, metadata } = {}) {
  const form = new FormData();
  form.append("file", file);
  form.append("submit_for_review", String(submitForReview));
  if (metadata) form.append("metadata_json", JSON.stringify(metadata));
  return (await api.post(`/conferences/${confId}/submissions`, form)).data;
}

export async function getSubmission(submissionId) {
  return (await api.get(`/submissions/${submissionId}`)).data;
}

export async function getConferenceSettings(id) {
  return (await api.get(`/conferences/${id}/settings`)).data;
}
export async function saveConferenceSettings(id, payload) {
  return (await api.put(`/conferences/${id}/settings`, payload)).data;
}
export async function createConferenceTrack(id, payload) {
  return (await api.post(`/conferences/${id}/tracks`, payload)).data;
}
export async function updateConferenceTrack(id, trackId, payload) {
  return (await api.put(`/conferences/${id}/tracks/${trackId}`, payload)).data;
}
export async function getPaperMetadata(id) {
  return (await api.get(`/submissions/${id}/metadata`)).data;
}
export async function savePaperMetadata(id, payload) {
  return (await api.put(`/submissions/${id}/metadata`, payload)).data;
}
export async function getPaperMetadataHistory(id, beforeVersion) {
  return (await api.get(`/submissions/${id}/metadata/history`, { params: { before_version: beforeVersion } })).data;
}

export async function getRevisions(submissionId) {
  return (await api.get(`/submissions/${submissionId}/revisions`)).data;
}

export async function comparePaperRevisions(submissionId, params) {
  return (await api.get(`/submissions/${submissionId}/revision-comparison`, { params })).data;
}

export async function getConferenceWorkflow(confId) {
  return (await api.get(`/conferences/${confId}/workflow`)).data;
}
export async function setConferenceWorkflow(confId, formattingGate) {
  return (await api.put(`/conferences/${confId}/workflow`, { formatting_gate: formattingGate })).data;
}
export async function getSubmissionWorkflow(id) {
  return (await api.get(`/submissions/${id}/workflow`)).data;
}
export async function transitionSubmission(id, payload) {
  return (await api.post(`/submissions/${id}/transitions`, payload)).data;
}
export async function assignSubmissionReviewer(id, reviewerId) {
  return (await api.post(`/submissions/${id}/review`, JSON.stringify(reviewerId), { headers: { "Content-Type": "application/json" } })).data;
}
export async function revokeSubmissionReviewer(id, assignmentId) {
  await api.delete(`/submissions/${id}/assignments/${assignmentId}`);
}
export async function getCollaborators(id) {
  return (await api.get(`/submissions/${id}/collaborators`)).data;
}
export async function saveCollaborator(id, userId, canEdit) {
  return (await api.put(`/submissions/${id}/collaborators`, { user_id: userId, can_edit: canEdit })).data;
}
export async function removeCollaborator(id, userId) {
  await api.delete(`/submissions/${id}/collaborators/${encodeURIComponent(userId)}`);
}
export async function getConversation(id) {
  return (await api.get(`/submissions/${id}/conversation`)).data;
}
export async function createConversation(id, payload) {
  return (await api.post(`/submissions/${id}/conversation`, payload)).data;
}
export async function replyToConversation(id, threadId, payload) {
  return (await api.post(`/submissions/${id}/conversation/${threadId}/comments`, payload)).data;
}
export async function editConversationComment(id, threadId, commentId, body, version) {
  return (await api.patch(`/submissions/${id}/conversation/${threadId}/comments/${commentId}`, { body, expected_version: version })).data;
}
export async function deleteConversationComment(id, threadId, commentId, version) {
  await api.delete(`/submissions/${id}/conversation/${threadId}/comments/${commentId}`, { params: { expected_version: version } });
}
export async function resolveConversation(id, threadId, resolved, expected) {
  return (await api.patch(`/submissions/${id}/conversation/${threadId}`, { resolved, expected_resolved: expected })).data;
}
export async function getActivity(id, before) {
  return (await api.get(`/submissions/${id}/activity`, { params: { before } })).data;
}

export async function getReviewConfiguration(confId) {
  return (await api.get(`/conferences/${confId}/review-configuration`)).data;
}
export async function saveReviewConfiguration(confId, body) {
  return (await api.put(`/conferences/${confId}/review-configuration`, body)).data;
}
export async function getFormalReviews(id) {
  return (await api.get(`/submissions/${id}/reviews`)).data;
}
export async function saveFormalReview(id, body) {
  return (await api.put(`/submissions/${id}/reviews/mine`, body)).data;
}
export async function getReviewHistory(id, reviewId) {
  return (await api.get(`/submissions/${id}/reviews/${reviewId}/history`)).data;
}
export async function releaseFormalReviews(id, revisionId) {
  return (await api.post(`/submissions/${id}/reviews/release`, { expected_revision_id: revisionId })).data;
}
export async function getReviewConflicts(id) {
  return (await api.get(`/submissions/${id}/conflicts`)).data;
}
export async function declareReviewConflict(id, reviewerId, reason) {
  return (await api.post(`/submissions/${id}/conflicts`, { reviewer_id: reviewerId, reason })).data;
}
export async function resolveReviewConflict(id, conflictId, version, reason) {
  return (await api.patch(`/submissions/${id}/conflicts/${conflictId}`, { expected_version: version, reason })).data;
}
export async function getReviewerWorkspace() {
  return (await api.get("/reviewer/workspace")).data;
}
export async function getConferenceReviewProgress(confId) {
  return (await api.get(`/conferences/${confId}/review-progress`)).data;
}
export async function declareOwnConflict(assignmentId, reason) {
  return (await api.post(`/reviewer/assignments/${assignmentId}/conflict`, { reason })).data;
}
export async function withdrawOwnConflict(conflictId, version, reason) {
  return (await api.post(`/reviewer/conflicts/${conflictId}/withdraw`, { expected_version: version, reason })).data;
}

export async function getRevisionChecks(submissionId, revisionId) {
  return (await api.get(`/submissions/${submissionId}/revisions/${revisionId}/checks`)).data;
}

export async function uploadRevision(submissionId, file, parentId, summary, requestKey) {
  const form = new FormData();
  form.append("file", file);
  form.append("parent_revision_id", parentId);
  form.append("change_summary", summary);
  form.append("request_key", requestKey);
  return (await api.post(`/submissions/${submissionId}/revisions`, form)).data;
}

export async function recheckRevision(submissionId, revisionId) {
  return (await api.post(`/submissions/${submissionId}/check-compliance`, { revision_id: revisionId })).data;
}

export async function downloadRevision(submissionId, revisionId, filename) {
  const { data } = await api.get(`/submissions/${submissionId}/revisions/${revisionId}/file`, { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function getRevisionPreview(submissionId, revisionId, signal) {
  try {
    const response = await api.get(`/submissions/${submissionId}/revisions/${revisionId}/preview`, { responseType: "blob", signal });
    const count = Number(response.headers["x-paper-page-count"]);
    return { data: response.data, pageCount: Number.isInteger(count) && count > 0 ? count : null };
  } catch (error) {
    // Axios returns JSON errors as blobs too when responseType is blob.
    if (error.response?.data instanceof Blob && error.response.data.type?.includes("json")) {
      try { error.response.data = JSON.parse(await error.response.data.text()); } catch { /* Keep the HTTP error. */ }
    }
    throw error;
  }
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

export async function listConferences(query) {
  const { data } = await api.get("/conferences/", { params: { q: query } });
  return Array.isArray(data) ? data : data.conferences ?? [];
}

export async function getConference(confId) {
  const { data } = await api.get(`/conferences/${confId}`);
  return data;
}

export async function createConference(payload) {
  const { data } = await api.post("/conferences/", payload);
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

export async function listConferenceInvitations(confId, before) {
  return (await api.get(`/conferences/${confId}/invitations`, { params: { before } })).data;
}
export async function createConferenceInvitation(confId, payload) {
  return (await api.post(`/conferences/${confId}/invitations`, payload)).data;
}
export async function revokeConferenceInvitation(confId, id) {
  return (await api.delete(`/conferences/${confId}/invitations/${id}`)).data;
}
export async function inspectInvitation(token) {
  return (await api.post('/invitations/inspect', { token })).data;
}
export async function acceptInvitation(token) {
  return (await api.post('/invitations/accept', { token })).data;
}

export async function listConferenceSubmissions(confId, query) {
  const { data } = await api.get(`/conferences/${confId}/submissions`, { params: { q: query } });
  return Array.isArray(data) ? data : data.submissions ?? [];
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

/* ------------------------------------------------------------------ */
/* auth                                                                */
/* ------------------------------------------------------------------ */

export async function getGoogleSignInConfig() {
  return (await api.get("/auth/google/config")).data;
}
export async function getGoogleConnection() {
  return (await api.get("/auth/google/connection")).data;
}
export async function createGoogleChallenge(password) {
  return password === undefined ? (await api.post("/auth/google/challenge")).data
    : (await api.post("/auth/google/link/challenge", { password })).data;
}
export async function completeGoogleSignIn(challengeId, credential) {
  return (await api.post("/auth/google/complete", { challenge_id: challengeId, credential })).data;
}

export async function login(email, password) {
  const { data } = await api.post("/auth/login", new URLSearchParams({ username: email, password }));
  removeToken();
  return data;
}

export async function register(email, password, full_name) {
  const { data } = await api.post("/auth/register", {
    email,
    password,
    full_name,
  });
  return data;
}

export async function logout() {
  await api.post("/auth/logout");
  removeToken();
}

export async function getCurrentUser() {
  const { data } = await api.get("/auth/me");
  return data;
}

export async function listUnreadNotifications() {
  const { data } = await api.get("/notifications/unread");
  return data;
}

export async function listNotifications(unreadOnly = false) {
  const { data } = await api.get(`/notifications?unread_only=${unreadOnly}`);
  return data;
}

export async function getNotificationFeed({ unreadOnly = false, before, limit = 25, signal } = {}) {
  const { data } = await api.get("/notifications/feed", {
    params: { unread_only: unreadOnly, before, limit }, signal,
  });
  return data;
}

export async function countUnreadNotifications(signal) {
  const { data } = await api.get("/notifications/count-unread", { signal });
  return data.count;
}

export async function markNotificationRead(notificationId) {
  const { data } = await api.patch(`/notifications/${notificationId}`);
  return data;
}

export async function markAllNotificationsRead() {
  const { data } = await api.patch(`/notifications/read-all`);
  return data;
}

export async function getLatestTemplateVersion(confId) {
  const { data } = await api.get(`/conferences/${confId}/templates/latest`);
  return data;
}

export async function listConferenceTemplateVersions(confId) {
  return (await api.get(`/conferences/${confId}/templates`)).data;
}

export async function getConferenceTemplateVersion(confId, templateId) {
  return (await api.get(`/conferences/${confId}/templates/${encodeURIComponent(templateId)}`)).data;
}

export async function publishConferenceTemplate(confId, rules) {
  return (await api.post(`/conferences/${confId}/templates`, rules)).data;
}

export async function diffTemplateVersions(confId, oldId, newId) {
  const { data } = await api.post(`/conferences/${confId}/templates/diff`, {
    old_template_id: oldId, new_template_id: newId,
  });
  return data;
}
