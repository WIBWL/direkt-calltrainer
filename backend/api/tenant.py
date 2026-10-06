"""`GET /api/tenant`: the caller's company name, or null for `default` (ADR 0060)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth import AuthContext, require_user
from backend.tenants import resolve_tenant

router = APIRouter(prefix="/api/tenant", dependencies=[Depends(require_user)])


@router.get("")
def get_tenant(user: AuthContext = Depends(require_user)) -> dict:
    tenant = resolve_tenant(user)
    return {"name": None if tenant.is_default else tenant.name}
