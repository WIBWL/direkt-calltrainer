# The SPA, built with Vite and served by nginx. Locally nginx also forwards
# /api, /ws and /health to the backend so the browser sees one origin (no CORS,
# and the Keycloak redirect lands on the same host); in deployment the external
# reverse proxy does that and static.nginx.conf runs. Built from frontend/.

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
# No settings are baked in: the OIDC issuer is read from the container's
# environment at start (spa.conf.template serves it as /config.js).
RUN npm run build

FROM nginx:1-alpine
EXPOSE 80
# Required at runtime; compose.yaml sets it.
ENV OIDC_ISSUER=""
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf static.nginx.conf /etc/nginx/
COPY spa.conf.template /etc/nginx/templates/
COPY --from=build /app/dist /usr/share/nginx/html
