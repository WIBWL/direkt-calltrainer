"""Which company a caller belongs to (ADR 0060, R-58).

The tenant is resolved for each request from the verified token: a `tenant`
claim — a Keycloak user attribute an admin sets when creating the account,
mapped into the access token by the `calltrainer tenant` protocol mapper. It
matches `tenant.extern_ref` directly. A token without it, or with an unknown
value (a typo'd attribute), resolves to the seeded `default` tenant rather than
erroring.

The client never supplies a tenant. `resolve_tenant_id` is the one entry point
the API and the WebSocket handshake call; `backend/library.py` then scopes every
read and stamps every authored row with the id it returns.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from backend.auth import AuthContext
from backend.db.models import Tenant
from backend.db.session import session_scope

DEFAULT_TENANT_REF = "default"


@dataclass(frozen=True)
class ResolvedTenant:
    """The `tenant` row a caller resolves to, as plain values (the ORM row is
    detached once `session_scope` closes)."""

    id: int
    ref: str
    name: str

    @property
    def is_default(self) -> bool:
        """True for the catch-all tenant — "no company", so the UI hides the
        company filter chip and badge."""
        return self.ref == DEFAULT_TENANT_REF


def resolve_tenant_ref(auth: AuthContext) -> str:
    """The `tenant.extern_ref` this caller resolves to, before the row lookup."""
    if auth.tenant and auth.tenant.strip():
        return auth.tenant.strip()
    return DEFAULT_TENANT_REF


def resolve_tenant(auth: AuthContext) -> ResolvedTenant:
    """The full `tenant` row this caller resolves to. An unknown ref falls back
    to the seeded `default` tenant."""
    ref = resolve_tenant_ref(auth)
    with session_scope() as db:
        row = db.scalar(select(Tenant).where(Tenant.extern_ref == ref))
        if row is None and ref != DEFAULT_TENANT_REF:
            row = db.scalar(select(Tenant).where(Tenant.extern_ref == DEFAULT_TENANT_REF))
        if row is None:
            raise RuntimeError(
                "no 'default' tenant is seeded — provisioning did not run"
            )
        return ResolvedTenant(row.tenant_id, row.extern_ref, row.name)


def resolve_tenant_id(auth: AuthContext) -> int:
    """Just the `tenant_id` — the common case, for scoping library reads."""
    return resolve_tenant(auth).id
