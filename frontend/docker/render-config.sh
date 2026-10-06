#!/bin/sh
# Writes config.js and the security headers at start (nginx's /docker-entrypoint.d/).
set -eu

# Required: a wrong issuer would only show as a 401 on every request.
: "${OIDC_ISSUER:?must be set, e.g. https://keycloak.efre-direkt.de/realms/direkt}"

# The backend's origin (ADR 0107); unset means the SPA's own.
API_URL="${API_URL:-}"

cat > /usr/share/nginx/html/config.js <<CONFIG
window.__APP_CONFIG__ = {
  oidcIssuer: "${OIDC_ISSUER}",
  apiUrl: "${API_URL}"
};
CONFIG

# The CSP names the API and Keycloak, known only here (ADR 0109). 'wasm-unsafe-eval'
# and blob: workers are the VAD's; 'unsafe-inline' styles the PDF export and style props.
origin() { printf '%s' "$1" | sed -E 's#^([a-z]+://[^/]+).*#\1#'; }
ISSUER_ORIGIN="$(origin "$OIDC_ISSUER")"
CONNECT="'self' ${ISSUER_ORIGIN}"
if [ -n "$API_URL" ]; then
  API_ORIGIN="$(origin "$API_URL")"
  # Older engines need the socket named.
  API_SOCKET="$(printf '%s' "$API_ORIGIN" | sed -E 's#^http#ws#')"
  CONNECT="${CONNECT} ${API_ORIGIN} ${API_SOCKET}"
fi
CSP="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; connect-src ${CONNECT}; img-src 'self' data: blob:; media-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; frame-src 'self' ${ISSUER_ORIGIN}; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"

# Only what Traefik's middleware does not set already (docs/deployment.md).
cat > /etc/nginx/security-headers.conf <<HEADERS
add_header Content-Security-Policy "${CSP}" always;
add_header X-Frame-Options "DENY" always;
HEADERS
