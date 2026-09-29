"""Which company a caller belongs to (ADR 0060, R-58).

From the alias of the caller's one Keycloak Organization -- the `organization` claim,
read in `backend/auth.py` -- matched against `tenant.extern_ref`; none or several means
the seeded `default` tenant. An alias seen for the first time gets its row here, so a
company is set up in Keycloak alone and the seed carries no customer. The client
never supplies one; `resolve_tenant_id` is the single entry point."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shared.db.models import Tenant
from shared.db.session import session_scope
from backend.auth import AuthContext

logger = logging.getLogger(__name__)

DEFAULT_TENANT_REF = "default"
_REF_MAX = Tenant.__table__.c.extern_ref.type.length


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
    """The full `tenant` row this caller resolves to, created on first sight.

    The alias comes from a verified token and Organization membership is
    admin-managed, so creating the row trusts nothing Keycloak did not already
    decide. Its `name` starts as the alias -- the claim carries no display name
    -- and is ours to change afterwards. `ON CONFLICT DO NOTHING` because two
    first requests of a new company can race."""
    ref = resolve_tenant_ref(auth)
    if len(ref) > _REF_MAX:
        logger.warning("Organization alias longer than %d characters; using the default tenant",
                       _REF_MAX)
        ref = DEFAULT_TENANT_REF
    with session_scope() as db:
        if ref != DEFAULT_TENANT_REF:
            db.execute(insert(Tenant).values(extern_ref=ref, name=ref)
                       .on_conflict_do_nothing(index_elements=[Tenant.extern_ref]))
        row = db.scalar(select(Tenant).where(Tenant.extern_ref == ref))
        if row is None:
            raise RuntimeError(
                "no 'default' tenant is seeded — provisioning did not run"
            )
        return ResolvedTenant(row.tenant_id, row.extern_ref, row.name)


def resolve_tenant_id(auth: AuthContext) -> int:
    """Just the `tenant_id` — the common case, for scoping library reads."""
    return resolve_tenant(auth).id
