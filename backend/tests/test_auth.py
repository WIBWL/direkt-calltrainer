"""Token verification and the role gate (F-31, F-50, ADR 0009, 0109)."""

import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt.exceptions import PyJWKClientConnectionError

from backend import auth
from backend.app import app

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
        "resource_access": {auth.OIDC_CLIENT_ID: {"roles": ["trainer"]}},
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


def test_organization_alias_is_the_tenant():
    assert auth.verify_token(_token(organization=["company-a"])).tenant == "company-a"


def test_organization_map_with_attributes_reads_the_alias():
    claim = {"company-b": {"id": "0b7e", "region": ["nord"]}}
    assert auth.verify_token(_token(organization=claim)).tenant == "company-b"


def test_absent_empty_or_blank_organization_is_none():
    assert auth.verify_token(_token()).tenant is None
    assert auth.verify_token(_token(organization=[])).tenant is None
    assert auth.verify_token(_token(organization=["   "])).tenant is None


def test_more_than_one_organization_is_none():
    assert auth.verify_token(_token(organization=["company-a", "company-b"])).tenant is None


def test_the_retired_tenant_claim_is_ignored():
    assert auth.verify_token(_token(tenant="company-a")).tenant is None


@pytest.mark.parametrize(
    "bad",
    [
        {"aud": "some-other-service"},
        # Addressed to the client that logs in, not to the API.
        {"aud": auth.OIDC_CLIENT_ID},
        {"iss": "http://evil.invalid/realms/x"},
        {"exp": int(time.time()) - 10},
        {"sub": None},
    ],
    ids=["wrong-audience", "client-audience", "wrong-issuer", "expired", "no-subject"],
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
        raise PyJWKClientConnectionError("keycloak down")

    monkeypatch.setattr(auth, "_jwks_client", boom)
    with pytest.raises(HTTPException) as e:
        auth.verify_token(_token())
    assert e.value.status_code == 503


def test_an_unreachable_keycloak_does_not_close_the_socket_as_unauthenticated(monkeypatch):
    def boom():
        raise PyJWKClientConnectionError("keycloak down")

    monkeypatch.setattr(auth, "_jwks_client", boom)
    with pytest.raises(HTTPException) as e:
        auth.authenticate_ws({"token": _token()})
    assert e.value.status_code == 503


def test_an_unknown_kid_is_still_the_callers_problem(monkeypatch):
    def boom():
        raise jwt.exceptions.PyJWKClientError("no matching key")

    monkeypatch.setattr(auth, "_jwks_client", boom)
    with pytest.raises(HTTPException) as e:
        auth.verify_token(_token())
    assert e.value.status_code == 401


def test_a_token_without_an_expiry_is_rejected():
    with pytest.raises(HTTPException) as e:
        auth.verify_token(_token(exp=None))
    assert e.value.status_code == 401


def test_authenticate_ws_reads_the_handshake_token():
    assert auth.authenticate_ws({"token": _token()}).sub == "user-123"
    assert auth.authenticate_ws({}) is None
    assert auth.authenticate_ws({"token": "not-a-jwt"}) is None


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _admitted(**overrides) -> str:
    return _token(resource_access={auth.OIDC_CLIENT_ID: {"roles": [auth.REQUIRED_ROLE]}},
                  **overrides)


async def test_a_caller_with_the_role_is_admitted():
    caller = await auth.require_user(_bearer(_admitted()))
    assert caller.sub == "user-123"
    assert caller.admitted


@pytest.mark.parametrize(
    "resource_access",
    [
        {},
        {auth.OIDC_CLIENT_ID: {"roles": ["trainer"]}},
        # The same name as a role of another client is not this client's role.
        {"some-other-client": {"roles": [auth.REQUIRED_ROLE]}},
    ],
    ids=["no-roles", "other-role", "other-client"],
)
async def test_a_valid_token_without_the_role_is_403(resource_access):
    with pytest.raises(HTTPException) as e:
        await auth.require_user(_bearer(_token(resource_access=resource_access)))
    assert e.value.status_code == 403


def test_a_realm_role_of_the_same_name_does_not_count():
    ctx = auth.verify_token(_token(realm_access={"roles": [auth.REQUIRED_ROLE]}))
    assert not ctx.admitted


@pytest.fixture
async def unauthorised_client():
    """The app with the real `require_user`, and no database behind it: every
    request here is refused before one would be needed."""
    app.dependency_overrides.pop(auth.require_user, None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/personas"),
        ("GET", "/api/scenarios"),
        ("POST", "/api/scenarios/document"),
        ("GET", "/api/sessions"),
        ("POST", "/api/sessions/00000000-0000-0000-0000-000000000000/reverse"),
        ("POST", "/api/sessions/00000000-0000-0000-0000-000000000000/follow-up"),
        ("GET", "/api/me/data"),
        ("GET", "/api/consent"),
        ("GET", "/api/focus"),
        ("GET", "/api/tenant"),
    ],
)
async def test_every_router_refuses_a_caller_without_the_role(unauthorised_client, method, path):
    response = await unauthorised_client.request(
        method, path, headers={"Authorization": f"Bearer {_token()}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == auth.NOT_ADMITTED
