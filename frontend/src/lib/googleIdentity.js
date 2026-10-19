// The official button is loaded only when this feature is configured and active.
let loading;
export function loadGoogleIdentity() {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.referrerPolicy = window.location.protocol === "http:" && ["localhost", "127.0.0.1"].includes(window.location.hostname)
      ? "no-referrer-when-downgrade" : "strict-origin-when-cross-origin";
    const fail = () => {
      clearTimeout(timer); script.remove(); loading = null;
      reject(new Error("Google sign-in could not load. Check your connection or browser settings and try again."));
    };
    const timer = setTimeout(fail, 15000);
    script.onerror = fail;
    script.onload = () => {
      clearTimeout(timer);
      if (window.google?.accounts?.id) resolve(window.google.accounts.id); else fail();
    };
    document.head.appendChild(script);
  });
  return loading;
}
