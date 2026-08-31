"""Keycloak bearer-token verification (backend/auth.py).

Covers F-31 (Accountsystem), F-50 (Login/Authentifizierung), ADR 0009: a valid
realm token is accepted and its `sub` / client roles surfaced; every kind of
bad token is a 401, not a 500; a JWKS/infra failure is *not* masked as a 401.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from backend import auth

# pylint: disable=missing-function-docstring,redefined-outer-name,too-few-public-methods

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
    return jwt.encode(payload, _KEY, algorithm="RS256")


def test_valid_token_yields_sub_and_roles():
    ctx = auth.verify_token(_token())
    assert ctx.sub == "user-123"
    assert ctx.roles == ["trainer"]
    assert ctx.token


def test_token_without_roles_claim_is_fine():
    ctx = auth.verify_token(_token(resource_access={}))
    assert not ctx.roles


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
    def boom():
        raise ConnectionError("keycloak down")

    monkeypatch.setattr(auth, "_jwks_client", boom)
    with pytest.raises(ConnectionError):
        auth.verify_token(_token())


def test_authenticate_ws_reads_the_handshake_token():
    assert auth.authenticate_ws({"token": _token()}).sub == "user-123"
    assert auth.authenticate_ws({}) is None
    assert auth.authenticate_ws({"token": "not-a-jwt"}) is None
