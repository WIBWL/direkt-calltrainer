#!/bin/sh
# Writes config.js and the security headers from env vars. nginx runs this from
# /docker-entrypoint.d/ on start.
set -eu

# Required: a wrong issuer wouldn't fail at boot, just 401 on every request.
# The backend reads the same name, so one .env line names both.
: "${OIDC_ISSUER:?must be set, e.g. https://keycloak.efre-direkt.de/realms/direkt}"

# Optional: the backend's origin (it lists this one in CORS_ORIGINS). Unset means
# the SPA's own origin.
API_URL="${API_URL:-}"

cat > /usr/share/nginx/html/config.js <<CONFIG
window.__APP_CONFIG__ = {
  oidcIssuer: "${OIDC_ISSUER}",
  apiUrl: "${API_URL}"
};
CONFIG

# The Content-Security-Policy names the two other hosts the SPA talks to, so it
# is written here, where they are known (ADR 0109). The page may only fetch from
# its own origin, the API (and its socket) and Keycloak; it runs no script it
# did not ship, and no other page may frame it. 'wasm-unsafe-eval' is the VAD's
# WebAssembly (onnxruntime-web), blob: workers its fallback; 'unsafe-inline'
# styles are what the PDF export and the React style props need.
origin() { printf '%s' "$1" | sed -E 's#^([a-z]+://[^/]+).*#\1#'; }
ISSUER_ORIGIN="$(origin "$OIDC_ISSUER")"
CONNECT="'self' ${ISSUER_ORIGIN}"
if [ -n "$API_URL" ]; then
  API_ORIGIN="$(origin "$API_URL")"
  # The call's socket: a CSP3 https: source covers wss:, older engines need it named.
  API_SOCKET="$(printf '%s' "$API_ORIGIN" | sed -E 's#^http#ws#')"
  CONNECT="${CONNECT} ${API_ORIGIN} ${API_SOCKET}"
fi
CSP="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; connect-src ${CONNECT}; img-src 'self' data: blob:; media-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; frame-src 'self' ${ISSUER_ORIGIN}; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"

# Included by every location in default.conf: an add_header in a location
# replaces the server's, it does not add to them. Only what Traefik does not
# already set: HSTS, nosniff, Referrer-Policy and Permissions-Policy come from
# its `calltrainer-headers` middleware (docs/deployment.md), and twice would
# be two headers. X-Frame-Options is frame-ancestors for older engines.
cat > /etc/nginx/security-headers.conf <<HEADERS
add_header Content-Security-Policy "${CSP}" always;
add_header X-Frame-Options "DENY" always;
HEADERS
