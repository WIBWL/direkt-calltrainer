// Runtime config from /config.js, written by docker/render-config.sh, so one image serves every deployment.

declare global {
  interface Window {
    __APP_CONFIG__?: {
      oidcIssuer?: string;
      apiUrl?: string;
    };
  }
}

const cfg = typeof window === "undefined" ? undefined : window.__APP_CONFIG__;

// No default: a wrong issuer fails as a distant 401, so fail loudly here.
if (!cfg?.oidcIssuer) {
  throw new Error(
    "OIDC_ISSUER is not set. Set it in the frontend container's environment (or the shell running Vite) and restart it.",
  );
}

/** The backend reads the same `OIDC_ISSUER`. */
export const oidcIssuer: string = cfg.oidcIssuer;

/** The backend's origin (ADR 0107); empty means the SPA's own, as with Vite's proxy. */
export const apiUrl: string = (cfg.apiUrl ?? "").replace(/\/+$/, "");
