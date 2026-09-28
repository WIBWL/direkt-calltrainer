// Runtime config from /config.js (`window.__APP_CONFIG__`), written at container
// start by docker/render-config.sh and served by vite.config.ts in dev and
// preview. So one image serves every deployment.

declare global {
  interface Window {
    __APP_CONFIG__?: {
      oidcIssuer?: string;
    };
  }
}

const cfg = typeof window === "undefined" ? undefined : window.__APP_CONFIG__;

// Required, deliberately without a default: every candidate value is wrong in
// some environment, and getting it wrong does not fail at build — the app just
// mints tokens the backend rejects, surfacing as a 401 far from the cause. Fail
// loudly instead.
if (!cfg?.oidcIssuer) {
  throw new Error(
    "OIDC_ISSUER is not set. Set it in the frontend container's environment (or the shell running Vite) and restart it.",
  );
}

/** The realm issuer URL; the backend reads the same `OIDC_ISSUER`. */
export const oidcIssuer: string = cfg.oidcIssuer;
