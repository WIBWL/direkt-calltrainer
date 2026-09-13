"""The caller's tenant, for the setup screen (ADR 0060).

`GET /api/tenant` tells the frontend which tenant the caller resolved to, so the
Scenario library can show a tenant filter chip and badge with the real name.
`null` means the caller is in the `default` tenant — no company, no chip. The
resolution itself is server-side (`backend/tenants.py`); the client never sends
or sets a tenant.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth import AuthContext, require_user
from backend.tenants import resolve_tenant

# On the router, like the other five (see api/scenarios.py for why).
router = APIRouter(prefix="/api/tenant", dependencies=[Depends(require_user)])


@router.get("")
def get_tenant(user: AuthContext = Depends(require_user)) -> dict:
    """The caller's resolved company name, or `null` for the `default` tenant --
    the setup screen shows a tenant filter chip and badge only when it is set."""
    tenant = resolve_tenant(user)
    return {"name": None if tenant.is_default else tenant.name}
