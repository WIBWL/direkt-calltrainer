/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Not VITE_-prefixed on purpose: see oidcConfig.ts and `envPrefix` in
  // vite.config.ts. The backend reads the same name.
  readonly OIDC_ISSUER: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
