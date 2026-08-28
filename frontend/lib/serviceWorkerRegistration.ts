export function registerServiceWorker(): void {
  if (typeof window === "undefined") return;
  if (!("serviceWorker" in navigator)) return;
  if (process.env.NODE_ENV !== "production") return; // avoid caching during dev

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        registration.addEventListener("updatefound", () => {
          const newWorker = registration.installing;
          if (!newWorker) return;

          newWorker.addEventListener("statechange", () => {
            if (
              newWorker.state === "installed" &&
              navigator.serviceWorker.controller
            ) {
              // A new version is installed and ready to take over on next load.
              console.info(
                "[SW] New content is cached and will be used on next reload.",
              );
            }
          });
        });
      })
      .catch((error) => {
        console.error("[SW] Registration failed:", error);
      });
  });
}
