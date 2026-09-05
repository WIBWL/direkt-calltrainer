"""REST routes for the Scenario library and User-authored Scenarios (ADR 0058).

`GET /api/scenarios` feeds the selection screen: every Scenario the caller may
see, each badged `builtin` (a shipped built-in), `own` (one they authored) or
`tenant` (shared by a colleague). The list withholds the prompt fields exactly
as before (ADR 0043/0045) — they are the answer key to the exercise. The detail
and write routes serve only the caller's own rows.

`POST /api/scenarios/document` (F-58) is a stateless helper: it extracts an
uploaded text-layer PDF and has the LLM condense it into a fact list for the
editor's Fakten field (`backend/documents.py`), storing nothing.

The wire vocabulary is English, matching the schema (ADR 0057, extended to this
surface by ADR 0061). `backend/library.py` does the sanitising (ADR 0059); this
module only validates shape and length and maps the card field `name` onto the
`title` column. A Scenario is addressed by its `extern_id` (ADR 0050); the write
routes are owner-scoped by the Keycloak `sub` and the resolved tenant, never by
anything the client sends.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from openai import OpenAIError
from pydantic import BaseModel, Field

from backend import library
from backend.api.deps import current_tenant, current_tenant_id
from backend.auth import AuthContext, require_user
from backend.authored_text import FIELD_LIMITS, clean
from backend.db.models import VISIBILITY_TENANT
from backend.documents import (
    MAX_TEXT,
    DocumentError,
    extract_pdf_text,
    reject_oversize_upload,
    summarise_facts,
)
from backend.tenants import ResolvedTenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenarios")


def _limited(field: str, *, required: bool):
    cap = FIELD_LIMITS[field]
    return Field(..., min_length=1, max_length=cap) if required \
        else Field("", max_length=cap)


class ScenarioInput(BaseModel):
    """The fields an authoring caller sets. `name` / `short_description` are the
    card; `description` and the three case fields are prompt input (ADR 0045)
    and may be left empty — an empty case means "improvise"."""

    name: str = _limited("title", required=True)
    short_description: str = _limited("short_description", required=True)
    # The situation is what the model gets as context -- an authored Scenario
    # without it is not a scenario, so it is required (the built-in seed rows
    # all carry one; ADR 0045 only allows the *case* fields to be blank).
    description: str = _limited("description", required=True)
    case_facts: str = _limited("case_facts", required=False)
    call_goal: str = _limited("call_goal", required=False)
    success_condition: str = _limited("success_condition", required=False)

    def to_library(self) -> dict:
        """1:1 with the schema columns, except the card field `name`, which is
        the `title` column (ADR 0061)."""
        data = self.model_dump()
        data["title"] = data.pop("name")
        return data


class VisibilityInput(BaseModel):
    # `private` <-> `tenant` only; `public` is a review decision (ADR 0060 phase 3).
    visibility: str = Field(..., pattern="^(private|tenant)$")


def _origin(scenario, subject: str) -> str:
    """Who the Scenario belongs to, from the caller's point of view. `own` wins
    over `tenant` -- the author still owns and can edit a Scenario they shared;
    `shared` (below) is the separate "visible to the company" flag the company
    filter uses."""
    if scenario.created_by == subject:
        return "own"
    if scenario.visibility == VISIBILITY_TENANT:
        return "tenant"
    return "builtin"


def _card(scenario, subject: str) -> dict:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        "origin": _origin(scenario, subject),
        # True once shared with the company -- for the author's own Scenarios
        # too, which `origin` still reports as `own`.
        "shared": scenario.visibility == VISIBILITY_TENANT,
    }


def _detail(scenario) -> dict:
    """The full row, for the editor. Only ever returned for the caller's own
    Scenario, so the case fields are theirs to see."""
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        "description": scenario.description,
        "case_facts": scenario.case_facts,
        "call_goal": scenario.call_goal,
        "success_condition": scenario.success_condition,
        # Always `private` or `tenant` here -- `_detail` only runs for the
        # caller's own rows, never a `public` built-in.
        "visibility": scenario.visibility,
    }


@router.get("")
def list_scenarios(
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> list[dict]:
    """Every Scenario the caller may select, each badged builtin/own/tenant."""
    return [_card(s, user.sub) for s in library.list_scenarios(user.sub, tenant_id)]


@router.post("/document")
async def extract_document(
    file: UploadFile = File(...),
    _user: AuthContext = Depends(require_user),
) -> dict:
    """Extract the text from an uploaded text-layer PDF and let the LLM condense
    it into a fact list for the editor's Fakten field (F-58). Stateless: nothing
    is stored, the client puts the returned text into the field and the User
    edits it before saving. `summarised` is False when the LLM was unreachable
    and the raw (truncated) text is returned instead."""
    try:
        reject_oversize_upload(file.size)
        data = await file.read()
        raw, pages = extract_pdf_text(data)
    except DocumentError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        text = await summarise_facts(raw)
        summarised = True
    except OpenAIError:
        logger.warning("Document summary failed; returning raw text", exc_info=True)
        text = clean(raw)[:MAX_TEXT].strip()
        summarised = False
    return {"text": text, "pages": pages, "summarised": summarised}


# `FIELD_LIMITS` is keyed by column name; `title` reaches the client as the card
# field `name` (ADR 0061), so the editor's limits endpoint reports it that way.
_LIMIT_FIELD_NAMES = {"title": "name"}


# Defined before "/{extern_id}" so the literal path is matched first.
@router.get("/field-limits")
def field_limits(_user: AuthContext = Depends(require_user)) -> dict[str, int]:
    """The maximum length the API enforces for each authorable Scenario field.
    The editor caps its inputs from here, so its limits are the same source that
    validates them rather than a hand-kept mirror that drifts (ADR 0063)."""
    return {_LIMIT_FIELD_NAMES.get(f, f): cap for f, cap in FIELD_LIMITS.items()}


# Defined before "/{extern_id}" so the literal path is matched first.
@router.get("/{extern_id}")
def get_scenario(
    extern_id: str,
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    """Full detail for one of the caller's own Scenarios (to populate the
    editor). A built-in, or another User's, is a 404 — it is not editable and
    its case must not leak."""
    scenario = library.get_scenario(extern_id, user.sub, tenant_id)
    if scenario is None or scenario.created_by != user.sub:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return _detail(scenario)


@router.post("", status_code=201)
def create_scenario(
    body: ScenarioInput,
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    """Author a Scenario. It lands private, owned by the caller (ADR 0058)."""
    scenario = library.create_scenario(body.to_library(), user.sub, tenant_id)
    return _detail(scenario)


@router.patch("/{extern_id}")
def update_scenario(
    extern_id: str,
    body: ScenarioInput,
    user: AuthContext = Depends(require_user),
) -> dict:
    """Edit one of the caller's own Scenarios; 404 if it is not theirs."""
    scenario = library.update_scenario(extern_id, body.to_library(), user.sub)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return _detail(scenario)


@router.put("/{extern_id}/visibility")
def set_visibility(
    extern_id: str,
    body: VisibilityInput,
    user: AuthContext = Depends(require_user),
    tenant: ResolvedTenant = Depends(current_tenant),
) -> dict:
    """Share the caller's Scenario with their company, or make it private again
    (R-58). Only the author may; `public` is not a choice offered here."""
    # "Share" means "with my colleagues" (ADR 0060) -- a caller in the `default`
    # tenant has none, so `tenant` visibility would just expose the row to every
    # other company-less account. The UI hides the toggle for them; this is the
    # matching server guard.
    if body.visibility == "tenant" and tenant.is_default:
        raise HTTPException(
            status_code=409,
            detail="Ohne Unternehmen kann ein Szenario nicht geteilt werden.",
        )
    scenario = library.set_scenario_visibility(
        extern_id, body.visibility, user.sub, tenant.id
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return _detail(scenario)


@router.delete("/{extern_id}", status_code=204)
def delete_scenario(
    extern_id: str, user: AuthContext = Depends(require_user)
) -> Response:
    """Retire one of the caller's own Scenarios (soft, ADR 0058)."""
    if not library.deactivate_scenario(extern_id, user.sub):
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return Response(status_code=204)
