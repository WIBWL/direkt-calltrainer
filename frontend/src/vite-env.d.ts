/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Not VITE_-prefixed on purpose: see oidcConfig.ts and `envPrefix` in
  // vite.config.ts. The backend reads the same two names.
  readonly OIDC_ISSUER: string;
  readonly OIDC_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
