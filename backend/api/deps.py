from fastapi import Depends

from backend.auth import AuthContext, require_user
from backend.tenants import ResolvedTenant, resolve_tenant


def current_tenant(user: AuthContext = Depends(require_user)) -> ResolvedTenant:
    """Resolved once per request from the token; never sent by the client (ADR 0060)."""
    return resolve_tenant(user)


def current_tenant_id(tenant: ResolvedTenant = Depends(current_tenant)) -> int:
    return tenant.id
