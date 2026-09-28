# ADR 0106: Every Setting Required, Any From a File

## Status

Accepted

## Context

Settings came from three places: `load_dotenv()` in two modules, compose's `env_file`, and defaults in the code (`POSTGRES_USER`/`POSTGRES_DB` `trainer`, `POSTGRES_HOST` `localhost`, `REDIS_URL` `redis://localhost:6379`). The database URL was assembled from five variables. A deployment handed the API keys over as plain environment variables, visible in `docker inspect`. The dataplatform does it differently: `.env.example` holds `export` lines that are sourced into the shell, every variable is required, and a deployment mounts its secrets as Docker secrets.

## Decision

`shared/env.py` is the one reader. `required(name)` returns the variable, or the stripped contents of the file `name_FILE` names, and refuses to start if neither is set or both are. There are no defaults in the code; `.env.example` holds the development values and is sourced (`source .env`), and nothing calls `load_dotenv()`.

The database is one `POSTGRES_URL` (any `postgres://`/`postgresql://` scheme). An optional `POSTGRES_PASSWORD` (or its `_FILE`) replaces the URL's password, so a deployment keeps the password in the one Docker secret the Postgres container reads too (`POSTGRES_PASSWORD_FILE`) and names the rest in the URL.

The pipeline settings split by process: the gateway and the LLM (`DIREKT_URL`, `DIREKT_API_KEY`, `LLM_MODEL`) are `shared/clients/config.py` and read by both; STT and KugelAudio (`STT_MODEL`, `KUGELAUDIO_*`) are `backend/clients/config.py`, so the worker no longer needs them. `OIDC_JWKS_URL` is gone: the backend runs where it reaches the realm under the issuer's own name. `CORS_ORIGINS` is the one optional setting, because its absence means something (no CORS at all).

## Consequences

A process started without the environment fails at once, naming the variable. Tests take their database server from the sourced `POSTGRES_URL` and claim it, and `REDIS_URL`, with unusable values before anything is imported (`shared/tests/fixtures.py`). python-dotenv is no longer a dependency.
