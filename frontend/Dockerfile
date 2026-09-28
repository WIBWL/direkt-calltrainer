# The SPA, built with Vite and served by Caddy. Locally Caddy also forwards
# /api, /ws and /health to the backend so the browser sees one origin (no CORS,
# and the Keycloak redirect lands on the same host); in deployment the external
# reverse proxy does that and static.Caddyfile runs. Built from frontend/.

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
# The OIDC issuer is baked into the SPA at build time (see src/oidcConfig.ts
# and `envPrefix` in vite.config.ts -- the SPA reads the backend's own
# variable name, not a VITE_-prefixed copy of it). compose.yaml passes it; a
# bare `docker build` falls back to the local default.
ARG OIDC_ISSUER=http://localhost:18081/realms/direkt
ENV OIDC_ISSUER=$OIDC_ISSUER
RUN npm run build

FROM caddy:2-alpine
EXPOSE 80
COPY Caddyfile static.Caddyfile spa.caddy /etc/caddy/
COPY --from=build /app/dist /srv
