"""Keycloak bearer-token verification (backend/auth.py; F-31, F-50, ADR 0009).

A valid token is accepted and its `sub`/roles surfaced; a bad token is a 401,
not a 500; a JWKS/infra failure is *not* masked as a 401.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.exceptions import PyJWKClientConnectionError

from backend import auth

# pylint: disable=missing-function-docstring,too-few-public-methods

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJWK:
    key = _KEY.public_key()


class _FakeJWKClient:
    def get_signing_key_from_jwt(self, _token):
        return _FakeJWK()


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch):
    monkeypatch.setattr(auth, "_jwks_client", _FakeJWKClient)


def _token(**overrides) -> str:
    payload = {
        "sub": "user-123",
        "iss": auth.OIDC_ISSUER,
        "aud": auth.OIDC_AUDIENCE,
        "exp": int(time.time()) + 300,
        "resource_access": {auth.OIDC_AUDIENCE: {"roles": ["trainer"]}},
    }
    payload.update(overrides)
    # None removes a claim rather than setting it to null, so a test can ask
    # for a token that simply does not carry one.
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, _KEY, algorithm="RS256")


def test_valid_token_yields_sub_and_roles():
    ctx = auth.verify_token(_token())
    assert ctx.sub == "user-123"
    assert ctx.roles == ["trainer"]
    assert ctx.token


def test_token_without_roles_claim_is_fine():
    ctx = auth.verify_token(_token(resource_access={}))
    assert not ctx.roles


def test_tenant_claim_is_surfaced():
    """ADR 0060: the `tenant` claim (a Keycloak user attribute) is what
    `backend/tenants.py` resolves a company from."""
    assert auth.verify_token(_token(tenant="solox")).tenant == "solox"


def test_absent_or_blank_tenant_claim_is_none():
    assert auth.verify_token(_token()).tenant is None
    assert auth.verify_token(_token(tenant="   ")).tenant is None


@pytest.mark.parametrize(
    "bad",
    [
        {"aud": "some-other-service"},
        {"iss": "http://evil.invalid/realms/x"},
        {"exp": int(time.time()) - 10},
        {"sub": None},
    ],
    ids=["wrong-audience", "wrong-issuer", "expired", "no-subject"],
)
def test_bad_token_is_401(bad):
    with pytest.raises(HTTPException) as e:
        auth.verify_token(_token(**bad))
    assert e.value.status_code == 401


def test_tampered_signature_is_401():
    token = _token()[:-3] + "xxx"
    with pytest.raises(HTTPException) as e:
        auth.verify_token(token)
    assert e.value.status_code == 401


def test_jwks_infra_failure_is_not_masked_as_401(monkeypatch):
    """ADR 0009: an unreachable Keycloak is a 5xx, never a 401.

    Raises the exception PyJWT's own client raises: a bare `ConnectionError` is not a
    `PyJWTError` and would pass a handler that answers the real one with 401.
    """
    def boom():
        raise PyJWKClientConnectionError("keycloak down")

    monkeypatch.setattr(auth, "_jwks_client", boom)
    with pytest.raises(HTTPException) as e:
        auth.verify_token(_token())
    assert e.value.status_code == 503


def test_an_unreachable_keycloak_does_not_close_the_socket_as_unauthenticated(monkeypatch):
    """The handshake's counterpart: `authenticate_ws` answers None for a bad
    token, which closes the socket with "Authentication required". An outage
    must not get that answer, or the User is sent to a login that cannot help."""
    def boom():
        raise PyJWKClientConnectionError("keycloak down")

    monkeypatch.setattr(auth, "_jwks_client", boom)
    with pytest.raises(HTTPException) as e:
        auth.authenticate_ws({"token": _token()})
    assert e.value.status_code == 503


def test_an_unknown_kid_is_still_the_callers_problem(monkeypatch):
    """The narrow half of the same change: `PyJWKClientError` also covers a
    `kid` the realm does not know, and that is a token-level failure -- it
    stays a 401 rather than being reported as an outage."""
    def boom():
        raise jwt.exceptions.PyJWKClientError("no matching key")

    monkeypatch.setattr(auth, "_jwks_client", boom)
    with pytest.raises(HTTPException) as e:
        auth.verify_token(_token())
    assert e.value.status_code == 401


def test_a_token_without_an_expiry_is_rejected():
    """PyJWT requires no claim by default, so a realm-signed token with no
    `exp` was a credential that never expired."""
    with pytest.raises(HTTPException) as e:
        auth.verify_token(_token(exp=None))
    assert e.value.status_code == 401


def test_authenticate_ws_reads_the_handshake_token():
    assert auth.authenticate_ws({"token": _token()}).sub == "user-123"
    assert auth.authenticate_ws({}) is None
    assert auth.authenticate_ws({"token": "not-a-jwt"}) is None
