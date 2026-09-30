"""Keycloak / OIDC bearer-token authentication (ADR 0009).

The SPA sends the access token in the `Authorization` header on REST and inside
the `session.start` message on the WebSocket; this verifies it against the JWKS.
A valid token is not enough: the caller also needs the client role
`calltrainer-user` (ADR 0109), since every route can cause model work."""

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWKClientConnectionError

from shared.env import required

logger = logging.getLogger(__name__)


# No default: the SPA and backend must name the same realm, and a default that
# disagrees doesn't fail at boot — discovery succeeds, then every request 401s
# far from the cause. The keys are found through the issuer's own discovery
# document, so the backend must reach the realm under the name the browser uses.
OIDC_ISSUER = required("OIDC_ISSUER").rstrip("/")

# A constant, not config: a value that disagrees with the realm just yields 401s
# rather than a boot failure, so hard-coding it is safer than an env var nobody
# would notice was wrong. This is the audience the realm's audience-mapper adds
# to Calltrainer tokens (keycloak/direkt-realm.json). It names the API, not the
# client the SPA logs in with.
OIDC_AUDIENCE = "calltrainer-backend"

# The client the SPA logs in with, whose client roles the token carries under
# `resource_access` (frontend/src/oidcConfig.ts names the same client).
OIDC_CLIENT_ID = "calltrainer-frontend"

# The client role (on `OIDC_CLIENT_ID`) that admits a caller at all (ADR
# 0109). A constant for the reason the audience is: a role name that disagrees
# with the realm only locks everyone out, which is loud, not silently wrong.
REQUIRED_ROLE = "calltrainer-user"

_ALGORITHMS = ["RS256"]

# HTTPBearer(auto_error=False): we raise our own 401 so the message is ours and
# a missing header and a bad token look identical to the client.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    """The verified caller. `sub` is the Keycloak user id, written as
    `session.subject_id` (ADR 0031/0034). `tenant` is the alias of the one
    Keycloak Organization the caller is a member of, from the `organization`
    claim; it picks whose shared Scenarios the caller sees (ADR 0060,
    `backend/tenants.py`). Missing means the `default` tenant."""

    sub: str
    roles: list[str]
    token: str
    tenant: str | None = None

    @property
    def admitted(self) -> bool:
        """Whether the caller holds `REQUIRED_ROLE`."""
        return REQUIRED_ROLE in self.roles


def _organization(payload: dict) -> str | None:
    """The alias of the caller's one Keycloak Organization, or `None`.

    The `organization` client scope puts a list of aliases in the token (a map
    alias → attributes once its mapper adds attributes; the keys are the same).
    More than one is no answer rather than the first: the list's order is not a
    choice anybody made, and a wrong company reads another's shared Scenarios.
    Keycloak itself leaves the claim out for a multi-member user unless the
    client asks for `organization:*`, so this only guards that case."""
    claim = payload.get("organization")
    if isinstance(claim, str):
        claim = [claim]
    if not isinstance(claim, (list, dict)):
        return None
    aliases = [a.strip() for a in claim if isinstance(a, str) and a.strip()]
    return aliases[0] if len(aliases) == 1 else None


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """The realm's JWKS client, its `jwks_uri` resolved from the OIDC discovery
    document. Built once; caches keys and refetches on an unknown `kid`."""
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
            # PyJWT checks `exp` only when the claim is present, and requires
            # nothing by default: a realm-signed token without one was a
            # credential that never expired.
            options={"require": ["exp"]},
        )
    except (PyJWKClientConnectionError, httpx.HTTPError) as e:
        # Before the PyJWTError branch, which this inherits from. An unreachable
        # JWKS is infrastructure and must be a 5xx (ADR 0009): as a 401 the SPA
        # sends everyone to login, so a Keycloak outage looks like mass expiry.
        logger.error("JWKS unavailable, cannot verify tokens: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "authentication backend unavailable"
        ) from e
    except jwt.PyJWTError as e:
        # Only token-level failures land here -- including a `kid` the realm
        # does not know, which is the caller's problem and stays a 401.
        logger.warning("bearer token rejected: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from e

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token has no subject")

    resource_access = payload.get("resource_access") or {}
    roles = list((resource_access.get(OIDC_CLIENT_ID) or {}).get("roles") or [])
    return AuthContext(sub=sub, roles=roles, token=token, tenant=_organization(payload))


# What a logged-in caller without the role is told, on REST and on the socket.
NOT_ADMITTED = "Ihr Konto ist für den Calltrainer nicht freigeschaltet."


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    """FastAPI dependency: requires a valid bearer JWT carrying `REQUIRED_ROLE`,
    returns the caller. 401 without a valid token, 403 without the role -- the
    one is fixed by logging in, the other is not, and the SPA must not send the
    User round the login again for it. Override it in tests via
    `app.dependency_overrides[require_user]`."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    # Off the event loop. Verifying a token is a synchronous HTTP round trip
    # whenever the JWKS cache cannot answer -- and a token with a `kid` the
    # cache does not hold forces a fresh fetch past it, which any caller can
    # produce at will. The container runs a single worker, so that round trip
    # stalled every call streaming audio on this loop (Q-03, ADR 0034).
    caller = await asyncio.to_thread(verify_token, credentials.credentials)
    if not caller.admitted:
        logger.warning("Caller without the %s role refused", REQUIRED_ROLE)
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_ADMITTED)
    return caller


def authenticate_ws(message: dict) -> AuthContext | None:
    """Verify the `token` carried in a WebSocket `session.start` message.
    Returns the caller, or `None` if the token is missing/invalid. Whether the
    caller holds the role is `AuthContext.admitted`, the handshake's to check,
    since it answers the two differently."""
    token = message.get("token")
    if not isinstance(token, str) or not token:
        return None
    try:
        return verify_token(token)
    except HTTPException as e:
        if e.status_code != status.HTTP_401_UNAUTHORIZED:
            # An unreachable Keycloak is not a bad token, and answering the
            # handshake with "Authentication required" would tell the User to
            # log in again during an outage that logging in cannot fix
            # (ADR 0009). Let it travel: the socket closes on the error instead.
            raise
        return None


async def check_realm() -> None:
    """Log an error if the realm's keys are unreachable at startup. Does not
    stop the app (matches how `lifespan` treats DiReKT)."""
    url = f"{OIDC_ISSUER}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        logger.info("OIDC realm reachable (%s)", url)
    except httpx.HTTPError as e:
        logger.error("OIDC realm unreachable (%s): %s — logins and every API call will fail", url, e)
