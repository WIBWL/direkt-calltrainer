"""Shared FastAPI dependencies for the API routes."""
from fastapi import Depends

from backend.auth import AuthContext, require_user
from backend.tenants import ResolvedTenant, resolve_tenant


def current_tenant(user: AuthContext = Depends(require_user)) -> ResolvedTenant:
    """The caller's tenant (ADR 0060), resolved once per request from the token.
    The client never sees or sends it. Routes that only need the id take
    `current_tenant_id`; the sharing route needs `is_default` too."""
    return resolve_tenant(user)


def current_tenant_id(tenant: ResolvedTenant = Depends(current_tenant)) -> int:
    """Just the caller's `tenant_id` -- for scoping library reads and stamping
    authored rows."""
    return tenant.id
