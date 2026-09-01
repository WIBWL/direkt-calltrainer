"""Keycloak / OIDC bearer-token authentication (ADR 0009).

The SPA logs in against Keycloak directly (Authorization Code + PKCE, public
client) and sends the access token as a bearer token — in the `Authorization`
header on REST, and inside the `session.start` message on the WebSocket
(browsers can't header a `WebSocket`). This module verifies it against the
realm's JWKS.

Mirrors `direkt-dataplatform`'s `shared-backend/src/index.ts`. Deliberately no
role *check* (docs/adr/0009): any valid realm token may use the app. `roles` is
still carried so a check can be added later without reshaping this.
"""

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)


def _issuer() -> str:
    value = os.environ.get("OIDC_ISSUER")
    if not value:
        # No default: the SPA and backend must name the same realm, and a
        # default that disagrees doesn't fail at boot — discovery succeeds, then
        # every request 401s far from the cause.
        raise RuntimeError("OIDC_ISSUER is required (see .env.example)")
    return value.rstrip("/")


OIDC_ISSUER = _issuer()

# Optional. When set, the JWKS is fetched from here instead of being resolved
# from the issuer's discovery document. Needed when the backend reaches Keycloak
# under a different host than the browser does — e.g. in compose the browser
# uses http://localhost:18081 (which is also the token `iss`) while the app
# container reaches http://keycloak:8080. The `iss` check still uses OIDC_ISSUER.
OIDC_JWKS_URL = os.environ.get("OIDC_JWKS_URL", "").rstrip("/") or None

# A constant, not config: a value that disagrees with the realm just yields 401s
# rather than a boot failure, so hard-coding it is safer than an env var nobody
# would notice was wrong. This is the audience the realm's audience-mapper adds
# to Calltrainer tokens (keycloak/direkt-realm.json).
OIDC_AUDIENCE = "calltrainer"

_ALGORITHMS = ["RS256"]

# HTTPBearer(auto_error=False): we raise our own 401 so the message is ours and
# a missing header and a bad token look identical to the client.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    """The verified caller. `sub` is the Keycloak user id — the value that
    becomes `session.subject_id` when ADR 0034's persistence lands (ADR 0031)."""

    sub: str
    roles: list[str]
    token: str


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """The realm's JWKS client. Uses `OIDC_JWKS_URL` if set, else resolves
    `jwks_uri` from the OIDC discovery document (parity with the reference).
    Built once; caches keys and refetches on an unknown `kid`."""
    if OIDC_JWKS_URL:
        return jwt.PyJWKClient(OIDC_JWKS_URL)
    discovery_url = f"{OIDC_ISSUER}/.well-known/openid-configuration"
    resp = httpx.get(discovery_url, timeout=10.0)
    resp.raise_for_status()
    jwks_uri = resp.json().get("jwks_uri")
    if not jwks_uri:
        raise RuntimeError(f"OIDC discovery document at {discovery_url} has no jwks_uri")
    return jwt.PyJWKClient(jwks_uri)


def verify_token(token: str) -> AuthContext:
    """Verify a Keycloak access token. Raises `HTTPException(401)` for any
    token-level problem (expired, bad signature, wrong iss/aud, malformed) —
    the client's fault. A JWKS/discovery failure propagates as a 5xx: that is
    infrastructure, not the caller, and must not be masked as a 401."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            issuer=OIDC_ISSUER,
            audience=OIDC_AUDIENCE,
        )
    except jwt.PyJWTError as e:
        # Only token-level failures land here. A failed JWKS fetch (Keycloak
        # down) raises something else and is left to 5xx on purpose — a 401 tells
        # the client to retry, which can't help, and hides the outage among
        # ordinary token-expiry 401s.
        logger.warning("bearer token rejected: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from e

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token has no subject")

    resource_access = payload.get("resource_access") or {}
    roles = list((resource_access.get(OIDC_AUDIENCE) or {}).get("roles") or [])
    return AuthContext(sub=sub, roles=roles, token=token)


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    """FastAPI dependency: requires a valid bearer JWT, returns the caller.
    Override it in tests via `app.dependency_overrides[require_user]`."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return verify_token(credentials.credentials)


def authenticate_ws(message: dict) -> AuthContext | None:
    """Verify the `token` carried in a WebSocket `session.start` message.
    Returns the caller, or `None` if the token is missing/invalid."""
    token = message.get("token")
    if not isinstance(token, str) or not token:
        return None
    try:
        return verify_token(token)
    except HTTPException:
        return None


async def check_realm() -> None:
    """Log an error if the realm's keys are unreachable at startup. Does not
    stop the app (matches how `lifespan` treats DiReKT)."""
    url = OIDC_JWKS_URL or f"{OIDC_ISSUER}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        logger.info("OIDC realm reachable (%s)", url)
    except httpx.HTTPError as e:
        logger.error("OIDC realm unreachable (%s): %s — logins and every API call will fail", url, e)
