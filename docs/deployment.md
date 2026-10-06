# Deployment

This repository builds three images and pushes them to `registry.internal.efre-direkt.de`. The stack that runs them is `direkt-infrastructure/public/calltrainer/compose.yml` on the DiReKT Hetzner host. Traefik terminates TLS, WUD pulls each new `latest` within the hour, and secrets are Docker secrets.

| Host | Service |
|---|---|
| `calltrainer.efre-direkt.de` | `calltrainer-frontend` (nginx, port 80) |
| `calltrainer-backend.efre-direkt.de` | `calltrainer-backend` (API and WebSocket, port 8000) |
| — | `calltrainer-worker`, `calltrainer-db` (Postgres 17), `calltrainer-redis` |

The backend and the worker reach the LLM gateway on the `proxy` network as `http://litellm:4000`.

## Releasing

```
git tag v1.2.3 && git push origin v1.2.3
scripts/build-and-push.sh                 # or: frontend backend worker
```

This pushes `:v1.2.3` and `:latest`. It needs bash 4 and `docker login registry.internal.efre-direkt.de`. On Windows, use Git Bash or WSL 2. `.gitattributes` forces LF on `*.sh`, because a CRLF `render-config.sh` builds fine and then keeps the frontend container from starting.

## Before the first start

### Secrets

Put these in `public/calltrainer/secrets/` on the host:

| File | Read by |
|---|---|
| `calltrainer_direkt_api_key.txt` (LiteLLM key) | backend, worker |
| `calltrainer_kugelaudio_api_key.txt` | backend |
| `calltrainer_postgres_password.txt` (`openssl rand -base64 32`) | Postgres, backend, worker |

Postgres applies its password only when `container_data/pgdata` is first created.

### Settings

These are set in the stack's `compose.yml`:

| Setting | Value |
|---|---|
| `POSTGRES_URL` | `postgresql://calltrainer@calltrainer-db:5432/calltrainer` |
| `REDIS_URL` | `redis://calltrainer-redis:6379` |
| `DIREKT_URL` | `http://litellm:4000` |
| `STT_MODEL`, `LLM_MODEL`, `KUGELAUDIO_MODEL` | as in `.env.example` |
| `OIDC_ISSUER` | `https://keycloak.efre-direkt.de/realms/direkt` (backend and frontend) |
| `CORS_ORIGINS` (backend) | `https://calltrainer.efre-direkt.de` |
| `API_URL` (frontend) | `https://calltrainer-backend.efre-direkt.de` |

### Traefik

HTTPS is required, because the browser grants the microphone only in a secure context. The frontend container sends its own CSP, so Traefik must not set a second one. If calls drop after about a minute of silence, raise `respondingTimeouts` on the shared `websecure` entrypoint.

### Keycloak (the real realm)

`keycloak/direkt-realm.json` is the template.

1. Create the client `calltrainer-frontend`: public, standard flow, PKCE `S256`. Set the redirect and post-logout URIs to `https://calltrainer.efre-direkt.de/*` and the web origin to `https://calltrainer.efre-direkt.de`. Turn direct access grants off.
2. Add an audience mapper on the client for `calltrainer-backend`, added to the access token.
3. Add the client role `calltrainer-user`, carried into the token as `resource_access.calltrainer-frontend.roles`. Assign it through a group, and do so before the backend goes out, or everyone is locked out.
4. Switch Organizations on, and add the `organization` client scope as a **Default** scope.
5. Create one Organization per company. Its alias becomes `tenant.extern_ref`, so pick it carefully: renaming it orphans the company's shared Scenarios. To set the display name: `UPDATE tenant SET name = '…' WHERE extern_ref = '<alias>'`.
6. Add members by admin or invitation only, because membership is a security boundary.
7. Set *Require SSL* to at least `external requests`. The dev users must not exist in this realm.

### Legal (blocking)

The project's privacy page (`PRIVACY_URL` in `frontend/src/routes.ts`) does not yet describe the Calltrainer. It must cover:

- the login claims
- audio to the DiReKT gateway and reply text to KugelAudio (Art. 28; sub-processors Verda AI and Hetzner)
- that the recording is never stored
- consent-gated storage, including aborted calls
- the derived exercises
- six-month retention
- focus goals
- the consent log
- user rights, logs and browser storage

After that, the data protection officer has to review it. Raise `CURRENT_VERSION` in `backend/consent.py` whenever the text changes. The project's accessibility statement must also be extended to name the Calltrainer.

## Starting

```
docker compose pull calltrainer-frontend calltrainer-backend calltrainer-worker
docker compose up -d          # without naming services, or the worker stays down
docker compose exec calltrainer-backend python -m backend.scripts.check_backends
```

The backend migrates and seeds the database itself.

**Acceptance:**

1. `/health/ready` answers 200.
2. Login works, and an account without the role sees "nicht freigeschaltet".
3. A call works with no CORS errors.
4. The wrap-up appears.
5. The training appears in the history and can be deleted.

## Later deployments

Take a dump before pushing the tag, because a migrated schema has no downgrade. Delete the dump afterwards, since it contains transcripts:

```
docker compose exec -T calltrainer-db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backup-$(date +%F).dump
```

To roll back, pin the previous tag in the stack. Put `latest` back afterwards, or WUD stops following.

## Operation

- **Logs:** JSON on stdout, collected into Loki.
- **Missing wrap-ups:** check `docker compose ps -a` first, then run `python -m backend.scripts.requeue_feedback --apply`.
- **Capacity:** gunicorn must stay at one worker process, because the per-account caps are counted in it (ADR 0109). Concurrent-call capacity has not been measured.
- **Backups:** none, deliberately. Adding backups requires a retention rule in ADR 0066.
