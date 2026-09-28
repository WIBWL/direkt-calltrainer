# Deployment

How the Calltrainer goes live. This repository builds the three images and pushes them to `registry.internal.efre-direkt.de`; the stack that runs them is in **`direkt-infrastructure`**, `public/calltrainer/compose.yml`, included from `public/compose.yml` on the DiReKT Hetzner host beside the dataplatform. There, Traefik terminates TLS and routes two hosts, WUD updates the three app containers when a new `latest` appears, and the secrets are Docker secrets. Nothing is deployed from this repository and the server needs no checkout of it.

| Host | Service | Port |
|---|---|---|
| `calltrainer.efre-direkt.de` | `calltrainer-frontend` — the SPA (nginx) | 80 |
| `calltrainer-backend.efre-direkt.de` | `calltrainer-backend` — the API and the call's WebSocket | 8000 |
| — | `calltrainer-worker`, `calltrainer-db` (Postgres 17), `calltrainer-redis` | — |

The worker, Postgres and Redis sit on the stack's own network `calltrainer_internal`; the backend and the worker also join `proxy`, where they reach the LLM gateway as `http://litellm:4000` (inside the host, past the public IP allowlist).

## Releasing a version

From a clean checkout of the commit to ship:

```
git tag v1.2.3 && git push origin v1.2.3
scripts/build-and-push.sh                 # all three; or name some: frontend backend worker
```

The script refuses to run unless HEAD carries a `v*` tag that has been pushed, and pushes each image twice: `:v1.2.3` (what a rollback pins) and `:latest` (what the stack runs and WUD watches). It builds with a buildx `docker-container` builder named `wud` and `--provenance=true`, because WUD's digest watching only works on an OCI index — a plain `docker push` of `latest` is never picked up (`direkt-infrastructure/public/README.md`). amd64 only: praat-parselmouth ships no Linux arm64 wheel. It needs bash 4 and `docker login registry.internal.efre-direkt.de`.

WUD checks hourly, pulls the new `latest`, recreates the container and prunes the old image. **The schema migrates itself when the new backend starts** — see "Every later deployment" for the dump to take first.

## Once, before the first start

### Secrets

On the host, beside the stack's `compose.yml` (`secrets/` is gitignored in `direkt-infrastructure`):

| File | Content | Read by |
|---|---|---|
| `public/calltrainer/secrets/calltrainer_direkt_api_key.txt` | a LiteLLM key for the gateway | backend, worker |
| `public/calltrainer/secrets/calltrainer_kugelaudio_api_key.txt` | the KugelAudio key | backend |
| `public/calltrainer/secrets/calltrainer_postgres_password.txt` | long and random, e.g. `openssl rand -base64 32` | Postgres, backend, worker |

Postgres applies its password **only when `container_data/pgdata` is first created** — set it before the first start. The app reads each as `NAME_FILE=/run/secrets/...` (ADR 0106); the database URL names no password, `POSTGRES_PASSWORD_FILE` supplies it, so the one file is the only place it lives.

### Settings

Everything else is written into the stack's `compose.yml`, not a `.env`: every value is either the same for every deployment of this stack or a secret above.

| Setting | Value there |
|---|---|
| `POSTGRES_URL` | `postgresql://calltrainer@calltrainer-db:5432/calltrainer` |
| `REDIS_URL` | `redis://calltrainer-redis:6379` |
| `DIREKT_URL` | `http://litellm:4000` |
| `STT_MODEL`, `LLM_MODEL`, `KUGELAUDIO_MODEL` | as in `.env.example` (ADR 0103) |
| `OIDC_ISSUER` | `https://keycloak.efre-direkt.de/realms/direkt` — backend and frontend, the same value |
| `CORS_ORIGINS` (backend) | `https://calltrainer.efre-direkt.de` (ADR 0107) |
| `API_URL` (frontend) | `https://calltrainer-backend.efre-direkt.de` |

The images set `LOG_FORMAT=json`. `OIDC_ISSUER` and `API_URL` reach the SPA at container start (`frontend/docker/render-config.sh` writes `/config.js`), so the frontend image is the same everywhere; changing either needs the container recreated, not a rebuild. The backend pins `keycloak.efre-direkt.de` to the host's LAN address (`extra_hosts`), as the dataplatform does, so its OIDC discovery rides the local Traefik.

What is deliberately a constant in the code rather than a setting:

| Value | Where |
|---|---|
| Keycloak client id `direkt-calltrainer` | `frontend/src/oidcConfig.ts` |
| Token audience `direkt-calltrainer` | `backend/auth.py` (`OIDC_AUDIENCE`) |

### Traefik

The two routers use the shared `websecure` entrypoint and the `*.efre-direkt.de` wildcard certificate. HTTPS is not optional: the browser grants the microphone only in a secure context. A headers middleware (`calltrainer-headers`, on both routers) sets `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` and `Permissions-Policy: microphone=(self), camera=(), geolocation=()`; the frontend container compresses its own files.

**Check on the first deployment:** a call's WebSocket can sit quiet for a while when the User thinks. Traefik v3's entrypoint timeouts apply to the shared `websecure` entrypoint; if calls are cut off after about a minute of silence, raise `respondingTimeouts` there (in `public/compose.yml`, affecting every service), since nothing in the Calltrainer's stack can.

### Keycloak (the real realm)

Locally, `keycloak/direkt-realm.json` sets all of this up; in the realm at `keycloak.efre-direkt.de` it has to be done by hand. The JSON file is the template.

1. **Client** `direkt-calltrainer`: public (client authentication off), standard flow on, PKCE `S256`.
   - Valid redirect URIs: `https://calltrainer.efre-direkt.de/*`
   - Valid post logout redirect URIs: `https://calltrainer.efre-direkt.de/*`
   - Web origins: `https://calltrainer.efre-direkt.de` (the SPA's; the backend's host never talks to Keycloak from a browser)
2. **Audience mapper** on the client: type *Audience*, included custom audience `direkt-calltrainer`, added to the access token. Without it `backend/auth.py` rejects every token.
3. **User profile**: declare the attribute `tenant`, *view* and *edit* **admin only**. This is a security boundary (ADR 0060): a user who can set their own `tenant` reads another company's shared Scenarios. Do not set the unmanaged attribute policy to *Enabled*.
4. **Tenant mapper** on the client: type *User Attribute*, attribute `tenant`, claim `tenant`, added to the access token.
5. **Users**: give each one a `tenant` whose value is a seeded tenant (`solox`, `appollo`; see `shared/db/seed_data.py`). An unknown value or none lands in the `default` tenant. A new company is a seed change plus a deployment.
6. Realm: *Require SSL* at least `external requests`. The development users `niklas`/`mathias`/`eberhard` do not exist there and must not.

### Legal

- The **privacy statement has not yet been reviewed by the data protection officer.** That blocks going live with real users. If the text changes afterwards, raise `CURRENT_VERSION` in `backend/consent.py` so every earlier consent is asked again.
- The privacy statement names Hetzner and KugelAudio as processors. Check that the path from the Hetzner server to the university gateway (audio and transcripts) is covered there.
- Review the imprint and the accessibility statement (`frontend/src/components/legal/`) for the domain and the operation.

## Starting

In `public/` on the host:

```
docker compose pull calltrainer-frontend calltrainer-backend calltrainer-worker
docker compose up -d
docker compose ps -a | grep calltrainer
```

Start without naming single services: `up -d calltrainer-backend` does not start the worker, and wrap-ups then silently never appear.

The database needs no manual step: the backend migrates and seeds it at startup (`backend/db/provision.py`). `Database provisioning failed` in its log means no Personas or Scenarios are loaded and no Session will be stored.

### Check the backends

```
docker compose exec calltrainer-backend python -m backend.scripts.check_backends
```

Must report OK for STT, LLM and TTS. The same check runs at startup (`Startup check: … FAILED` in the log) but does not stop the app from booting.

### Acceptance

1. `https://calltrainer-backend.efre-direkt.de/health/ready` answers 200.
2. Log in at `https://calltrainer.efre-direkt.de` through Keycloak and land back in the app.
3. Grant consent and hold a call (the microphone prompt appears, the Persona answers audibly). The browser's network tab shows the API requests going to `calltrainer-backend.` without CORS errors.
4. After the call the wrap-up appears (if not: `docker compose ps -a` — is `calltrainer-worker` running?).
5. The training shows in the history on the profile page; delete it once.

## Every later deployment

WUD rolls out a new `latest` by itself, so the step that has to come *before* the tag is pushed is the backup. There is no downgrade path for a migrated schema:

```
docker compose exec -T calltrainer-db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backup-$(date +%F).dump
```

The file contains transcripts. Delete it once the deployment has succeeded rather than keeping it — see below. Then push the tag and run `scripts/build-and-push.sh`; within the hour WUD recreates the containers. Read `docker compose logs calltrainer-backend --tail 100` for `Database provisioning failed` and `Startup check` afterwards.

Rolling back the code is pinning the previous version's tag in the stack (`calltrainer-backend:v1.2.2` etc.) and `docker compose up -d` — the schema is not rolled back with it, hence the dump. Put `latest` back once a fixed version is pushed, or WUD stops following.

## Operation

- **Logs**: stdout only, one JSON object per line (ADR 0105), collected by Alloy into Loki (`direkt-infrastructure/internal/`); `docker compose logs calltrainer-backend` on the host. The Session id is the `session` field. Neither the backend nor the worker logs spoken content.
- **Retention**: the six-month deletion runs daily inside the app (ADR 0067). `docker compose exec calltrainer-backend python -m backend.scripts.apply_retention` shows what is due.
- **Missing wrap-ups**: `docker compose ps -a`, then `docker compose exec calltrainer-backend python -m backend.scripts.requeue_feedback --apply`.
- **Capacity**: gunicorn runs one worker process. How many concurrent calls that carries has not been measured; test it before a larger group of users.

## Backups — deliberately not set up

There are no regular backups. Whoever introduces them has to record **a retention rule in ADR 0066 in the same change**: the deletion paths (deleting one training, withdrawing consent, the six-month period) are complete today because no copies exist. A backup without a period of its own would keep deleted transcripts. Until then: only the dump before a deployment, deleted afterwards.
