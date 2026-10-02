/// <reference types="vite/client" />

interface Window {
  // Set by /config.js from the container's environment (spa.conf.template); the
  // backend reads the same name.
  readonly OIDC_ISSUER?: string;
}
