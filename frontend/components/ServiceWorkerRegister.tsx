"use client";

import * as React from "react";
import { registerServiceWorker } from "../lib/serviceWorkerRegistration";

/**
 * Mounts once in the root layout. No UI — just kicks off SW registration
 * on the client after hydration.
 */
export function ServiceWorkerRegister() {
  React.useEffect(() => {
    registerServiceWorker();
  }, []);

  return null;
}
