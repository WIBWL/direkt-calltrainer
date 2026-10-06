"""Resolving the caller's tenant from the `organization` claim (ADR 0060)."""
from backend import auth, tenants

# pylint: disable=missing-function-docstring


def _ctx(**kw):
    return auth.AuthContext(**{"sub": "u", "roles": [], "token": "t", **kw})


def test_tenant_claim_is_the_ref():
    assert tenants.resolve_tenant_ref(_ctx(tenant="company-a")) == "company-a"


def test_no_tenant_claim_is_the_default_tenant():
    assert tenants.resolve_tenant_ref(_ctx()) == tenants.DEFAULT_TENANT_REF


def test_a_blank_tenant_claim_falls_through_to_default():
    assert tenants.resolve_tenant_ref(_ctx(tenant="   ")) == tenants.DEFAULT_TENANT_REF


def test_the_claim_is_trimmed():
    assert tenants.resolve_tenant_ref(_ctx(tenant="  company-b  ")) == "company-b"
