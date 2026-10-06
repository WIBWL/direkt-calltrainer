# ADR 0106: Every Setting Required, Any From a File

## Context

Settings came from `load_dotenv()`, compose's `env_file` and code defaults, and secrets were plain environment variables.

## Decision

- `shared/env.py` is the one reader. `required(name)` returns the variable or the contents of the file `NAME_FILE` names, and refuses to start if neither or both are set. There are no defaults in code.
- `.env.example` holds `export` lines, sourced into the shell.
- The database is one `POSTGRES_URL`. An optional `POSTGRES_PASSWORD[_FILE]` replaces its password, so the password lives in the one secret the Postgres container also reads.
- Settings split by process: the gateway and the LLM are shared; STT and KugelAudio belong to the backend.
- `CORS_ORIGINS` is the one optional setting, because its absence means "no CORS".
- A value nobody changes is a constant, not a setting.

## Consequences

A process started without its environment fails at once and names the variable. Tests claim the database and Redis URLs with unusable values before any import.
