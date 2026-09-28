# Deployment

How the Calltrainer goes live on a server. `compose.yaml` describes local development; a deployment layers `compose.prod.yaml` on top of it, which changes only what a server must not inherit: the local Keycloak and its `localhost` issuer are dropped, nothing publishes a port, and the frontend and backend join the network of an **external reverse proxy**, which terminates TLS and routes between them. This repository ships no proxy for deployment.

```
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

## Once, before the first start

### Server

- Docker Engine with Compose **2.24.4 or later** (`docker compose version`); `compose.prod.yaml` uses `!reset`/`!override`.
- amd64. `praat-parselmouth` ships no Linux arm64 wheel.
- Firewall: the stack publishes no port at all. Postgres, Redis, the backend and the frontend container are reachable only over Docker networks; what faces the internet is the external proxy's business.
- The server must be able to **reach the DiReKT gateway (`DIREKT_URL`)**. By default it is reachable only from the university network or its VPN, and the server is at Hetzner. Check this first (see "Check the backends" below): without the gateway there is no speech recognition and no reply.

### External reverse proxy

The proxy's Docker network must exist before the first start (`PROXY_NETWORK` in `.env`); Compose joins it but never creates it. On it the containers answer as `calltrainer-frontend:80` and `calltrainer-backend:8000`. The proxy has to:

- **Terminate TLS** for the domain. HTTPS is not optional: the browser grants the microphone only in a secure context.
- **Route by path**, all on the one domain: `/api*`, `/ws*` and `/health*` to `calltrainer-backend:8000`, everything else to `calltrainer-frontend:80`. The browser must see one origin — there is no CORS middleware, and Keycloak redirects back to that origin. A backend path that reaches the frontend by mistake answers 404 (`frontend/static.Caddyfile`).
- **Pass the WebSocket upgrade** on `/ws/session` and keep the connection open for the length of a call: no short idle/read timeout (nginx's default of 60 s would cut a call off while the User is thinking).
- **Accept request bodies of at least 20 MB** (document upload; nginx's default is 1 MB).
- Set the headers the app relies on: `Strict-Transport-Security "max-age=31536000"`, `X-Content-Type-Options "nosniff"`, `Referrer-Policy "strict-origin-when-cross-origin"` and `Permissions-Policy "microphone=(self), camera=(), geolocation=()"`. Compression is already done by the frontend container.

For Caddy as the external proxy that is:

```
calltrainer.example.org {
	header Strict-Transport-Security "max-age=31536000"
	header X-Content-Type-Options "nosniff"
	header Referrer-Policy "strict-origin-when-cross-origin"
	header Permissions-Policy "microphone=(self), camera=(), geolocation=()"

	@backend path /api* /ws* /health*
	reverse_proxy @backend calltrainer-backend:8000
	reverse_proxy calltrainer-frontend:80
}
```

### `.env`

`cp .env.example .env`, then fill in:

| Variable | Value |
|---|---|
| `DIREKT_API_KEY` | key for the DiReKT gateway |
| `KUGELAUDIO_API_KEY` | key for KugelAudio |
| `POSTGRES_PASSWORD` | long and random, e.g. `openssl rand -base64 32`. Set it **before the first start**: Postgres applies it only when the volume is created. |
| `OIDC_ISSUER` | `https://keycloak.efre-direkt.de/realms/direkt` |
| `DIREKT_URL` | `https://llm.efre-direkt.de`, unless the server reaches the gateway by another route |
| `PROXY_NETWORK` | the name of the external reverse proxy's Docker network |
| `STT_MODEL`, `LLM_MODEL`, `KUGELAUDIO_MODEL` | leave as in `.env.example`; the same in development and deployment |

That is the whole file. `.env` is not in the repository and on the server should be readable by the deploying user only (`chmod 600 .env`).

`OIDC_ISSUER` is baked into the frontend at build time. Changing it needs `--build`; a restart is not enough.

### What is deliberately *not* in `.env`

These are the same in development and deployment, so they are constants in the code. Changing one is a code change and a new build.

| Value | Where |
|---|---|
| Keycloak client id `direkt-calltrainer` | `frontend/src/oidcConfig.ts` |
| Token audience `direkt-calltrainer` | `backend/auth.py` (`OIDC_AUDIENCE`) |
| Postgres role and database `trainer` | `backend/db/session.py` (`DEFAULT_USER`/`DEFAULT_DATABASE`) and the `db` service in `compose.yaml` |
| Postgres host and port, Redis URL | set by `compose.yaml` for the containers; the code defaults to `localhost` for a host-side run |

### Keycloak (the real realm)

Locally, `keycloak/direkt-realm.json` sets all of this up; in the realm at `keycloak.efre-direkt.de` it has to be done by hand. The JSON file is the template.

1. **Client** `direkt-calltrainer`: public (client authentication off), standard flow on, PKCE `S256`.
   - Valid redirect URIs: `https://<domain>/*`
   - Valid post logout redirect URIs: `https://<domain>/*`
   - Web origins: `https://<domain>`
2. **Audience mapper** on the client: type *Audience*, included custom audience `direkt-calltrainer`, added to the access token. Without it `backend/auth.py` rejects every token.
3. **User profile**: declare the attribute `tenant`, *view* and *edit* **admin only**. This is a security boundary (ADR 0060): a user who can set their own `tenant` reads another company's shared Scenarios. Do not set the unmanaged attribute policy to *Enabled*.
4. **Tenant mapper** on the client: type *User Attribute*, attribute `tenant`, claim `tenant`, added to the access token.
5. **Users**: give each one a `tenant` whose value is a seeded tenant (`solox`, `appollo`; see `backend/db/seed_data.py`). An unknown value or none lands in the `default` tenant. A new company is a seed change plus a deployment.
6. Realm: *Require SSL* at least `external requests`. The development users `niklas`/`mathias`/`eberhard` do not exist there and must not.

### Legal

- The **privacy statement has not yet been reviewed by the data protection officer.** That blocks going live with real users. If the text changes afterwards, raise `CURRENT_VERSION` in `backend/consent.py` so every earlier consent is asked again.
- The privacy statement names Hetzner and KugelAudio as processors. Check that the path from the Hetzner server to the university gateway (audio and transcripts) is covered there.
- Review the imprint and the accessibility statement (`frontend/src/components/legal/`) for the domain and the operation.

## Starting

```
git pull
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml ps
```

Always start without a service name: `up -d backend` does not start the worker, and wrap-ups then silently never appear.

The database needs no manual step: the app migrates and seeds it at startup (`backend/db/provision.py`). `Database provisioning failed` in the log means no Personas or Scenarios are loaded and no Session will be stored.

An alias keeps the two files from being forgotten:

```
alias dc='docker compose -f compose.yaml -f compose.prod.yaml'
```

### Check the backends

```
dc exec backend python scripts/check_backends.py
```

Must report OK for STT, LLM and TTS. The same check runs at startup (`Startup check: … FAILED` in the log) but does not stop the app from booting.

### Acceptance

1. `https://<domain>/health/ready` answers 200.
2. Log in through Keycloak and land back in the app.
3. Grant consent and hold a call (the microphone prompt appears, the Persona answers audibly).
4. After the call the wrap-up appears (if not: `dc ps -a` — is the `worker` running?).
5. The training shows in the history on the profile page; delete it once.

## Every later deployment

1. **Back up first.** There is no downgrade path for a migrated schema:
   ```
   dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backup-$(date +%F).dump
   ```
   The file contains transcripts. Delete it once the deployment has succeeded rather than keeping it — see below.
2. `git pull`, then `dc up -d --build`.
3. Read `dc logs backend --tail 100` for `Database provisioning failed` and `Startup check`.

## Operation

- **Logs**: `dc logs <service>` (Docker rotates them at 5 × 20 MB per `compose.prod.yaml`) and `logs/calltrainer.log`, which starts over with every process start (ADR 0055). Neither contains spoken content.
- **Retention**: the six-month deletion runs daily inside the app (ADR 0067). `dc exec backend python scripts/apply_retention.py` shows what is due.
- **Missing wrap-ups**: `dc ps -a`, then `dc exec backend python scripts/requeue_feedback.py --apply`.
- **Capacity**: gunicorn runs one worker process. How many concurrent calls that carries has not been measured; test it before a larger group of users.

## Backups — deliberately not set up

There are no regular backups. Whoever introduces them has to record **a retention rule in ADR 0066 in the same change**: the deletion paths (deleting one training, withdrawing consent, the six-month period) are complete today because no copies exist. A backup without a period of its own would keep deleted transcripts. Until then: only the dump before a deployment, deleted afterwards.
