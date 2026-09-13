"""Resolving which company a caller belongs to (ADR 0060, R-58).

The tenant comes from the `tenant` claim (a Keycloak user attribute).
`resolve_tenant_ref` is pure; the row lookup in `resolve_tenant` / `_id` is
covered against a real database in test_authored_content.py.
"""
from backend import auth, tenants

# pylint: disable=missing-function-docstring


def _ctx(**kw):
    return auth.AuthContext(**{"sub": "u", "roles": [], "token": "t", **kw})


def test_tenant_claim_is_the_ref():
    assert tenants.resolve_tenant_ref(_ctx(tenant="solox")) == "solox"


def test_no_tenant_claim_is_the_default_tenant():
    assert tenants.resolve_tenant_ref(_ctx()) == tenants.DEFAULT_TENANT_REF


def test_a_blank_tenant_claim_falls_through_to_default():
    assert tenants.resolve_tenant_ref(_ctx(tenant="   ")) == tenants.DEFAULT_TENANT_REF


def test_the_claim_is_trimmed():
    assert tenants.resolve_tenant_ref(_ctx(tenant="  appollo  ")) == "appollo"
