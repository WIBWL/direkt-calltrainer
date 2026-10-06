"""Bearer-token verification and the role gate (ADR 0009, 0109)."""

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


# No default: a mismatched realm passes discovery and then 401s everything. The
# backend must reach the realm under the name the browser uses.
OIDC_ISSUER = required("OIDC_ISSUER").rstrip("/")

# Constants: a mismatch is loud (401s or a lockout), unlike a forgotten env var.
OIDC_AUDIENCE = "calltrainer-backend"

OIDC_CLIENT_ID = "calltrainer-frontend"

REQUIRED_ROLE = "calltrainer-user"

_ALGORITHMS = ["RS256"]

# auto_error=False: a missing header and a bad token get the same 401.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    """`tenant` is the caller's one Organization alias; None means `default` (ADR 0060)."""

    sub: str
    roles: list[str]
    token: str
    tenant: str | None = None

    @property
    def admitted(self) -> bool:
        return REQUIRED_ROLE in self.roles


def _organization(payload: dict) -> str | None:
    """The one Organization alias, or None. Several is no answer rather than the
    first: their order is nobody's choice, and a wrong company would read
    another's Scenarios. The claim may be a list or a map keyed by alias."""
    claim = payload.get("organization")
    if isinstance(claim, str):
        claim = [claim]
    if not isinstance(claim, (list, dict)):
        return None
    aliases = [a.strip() for a in claim if isinstance(a, str) and a.strip()]
    return aliases[0] if len(aliases) == 1 else None


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """Built once; refetches keys on an unknown `kid`."""
    discovery_url = f"{OIDC_ISSUER}/.well-known/openid-configuration"
    resp = httpx.get(discovery_url, timeout=10.0)
    resp.raise_for_status()
    jwks_uri = resp.json().get("jwks_uri")
    if not jwks_uri:
        raise RuntimeError(f"OIDC discovery document at {discovery_url} has no jwks_uri")
    return jwt.PyJWKClient(jwks_uri)


def verify_token(token: str) -> AuthContext:
    """401 for any token problem; a JWKS/discovery failure stays a 5xx, because
    a 401 would send everyone to login during an outage."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            issuer=OIDC_ISSUER,
            audience=OIDC_AUDIENCE,
            # PyJWT requires nothing by default: without this a token with no
            # `exp` never expires.
            options={"require": ["exp"]},
        )
    except (PyJWKClientConnectionError, httpx.HTTPError) as e:
        # Before PyJWTError, which this inherits from.
        logger.error("JWKS unavailable, cannot verify tokens: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "authentication backend unavailable"
        ) from e
    except jwt.PyJWTError as e:
        # Includes an unknown `kid`: the caller's problem, a 401.
        logger.warning("bearer token rejected: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from e

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token has no subject")

    resource_access = payload.get("resource_access") or {}
    roles = list((resource_access.get(OIDC_CLIENT_ID) or {}).get("roles") or [])
    return AuthContext(sub=sub, roles=roles, token=token, tenant=_organization(payload))


NOT_ADMITTED = "Ihr Konto ist für den Calltrainer nicht freigeschaltet."


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    """401 without a valid token, 403 without the role: the SPA must not send
    the User round the login for the latter."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    # Off the event loop: an unknown `kid` forces a synchronous JWKS fetch any
    # caller can trigger, which stalled every live call on the single worker.
    caller = await asyncio.to_thread(verify_token, credentials.credentials)
    if not caller.admitted:
        logger.warning("Caller without the %s role refused", REQUIRED_ROLE)
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_ADMITTED)
    return caller


def authenticate_ws(message: dict) -> AuthContext | None:
    """None for a missing or invalid token; the role is the handshake's to check."""
    token = message.get("token")
    if not isinstance(token, str) or not token:
        return None
    try:
        return verify_token(token)
    except HTTPException as e:
        if e.status_code != status.HTTP_401_UNAUTHORIZED:
            # An outage is not a bad token; telling the User to log in cannot fix it.
            raise
        return None


async def check_realm() -> None:
    """Logs only, like the gateway check."""
    url = f"{OIDC_ISSUER}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        logger.info("OIDC realm reachable (%s)", url)
    except httpx.HTTPError as e:
        logger.error("OIDC realm unreachable (%s): %s — logins and every API call will fail", url, e)
