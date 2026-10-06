"""Which company a caller belongs to (ADR 0060): the Organization alias from the
token, `default` otherwise. A new alias gets its row here on first sight."""
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
    """Plain values: the ORM row is detached once the scope closes."""

    id: int
    ref: str
    name: str

    @property
    def is_default(self) -> bool:
        return self.ref == DEFAULT_TENANT_REF


def resolve_tenant_ref(auth: AuthContext) -> str:
    if auth.tenant and auth.tenant.strip():
        return auth.tenant.strip()
    return DEFAULT_TENANT_REF


def resolve_tenant(auth: AuthContext) -> ResolvedTenant:
    """Created on first sight; `ON CONFLICT DO NOTHING` because two first
    requests can race. The name starts as the alias."""
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
    return resolve_tenant(auth).id
