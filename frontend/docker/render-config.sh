#!/bin/sh
# Writes config.js from env vars. nginx runs this from /docker-entrypoint.d/ on start.
set -eu

# Required: a wrong issuer wouldn't fail at boot, just 401 on every request.
# The backend reads the same name, so one .env line names both.
: "${OIDC_ISSUER:?must be set, e.g. https://keycloak.efre-direkt.de/realms/direkt}"

# Optional: the backend's origin (it lists this one in CORS_ORIGINS). Unset means
# the SPA's own origin.
cat > /usr/share/nginx/html/config.js <<CONFIG
window.__APP_CONFIG__ = {
  oidcIssuer: "${OIDC_ISSUER}",
  apiUrl: "${API_URL:-}"
};
CONFIG
