import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 120_000,
});

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

export function errorMessage(error) {
  if (error?.response?.data?.detail) {
    const detail = error.response.data.detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }
  if (error?.code === "ECONNABORTED") return "Request timed out.";
  if (error?.message === "Network Error")
    return "Cannot reach the backend. Is it running on http://localhost:8000?";
  return error?.message || "Unexpected error.";
}
