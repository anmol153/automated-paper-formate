// Authentication tokens are HttpOnly cookies; discard tokens from older builds.
export const removeToken = () => {
  if (typeof window !== "undefined") window.localStorage.removeItem("access_token");
};

export const getCsrfToken = () => {
  if (typeof document === "undefined") return "";
  const cookie = document.cookie.split("; ").find((part) => part.startsWith("paper_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("paper_csrf=".length)) : "";
};
