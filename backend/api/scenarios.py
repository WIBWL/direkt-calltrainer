"""REST routes for the Scenario library and User-authored Scenarios (ADR 0058).

`GET /api/scenarios` feeds the selection screen: every Scenario the caller may
see, each badged `vorlage` (a shipped built-in), `eigen` (one they authored) or
`unternehmen` (shared by a colleague). The list withholds the prompt fields
exactly as before (ADR 0043/0045) — they are the answer key to the exercise.
The detail and write routes serve only the caller's own rows.

`POST /api/scenarios/dokument` (F-58) is a stateless helper: it extracts an
uploaded text-layer PDF and has the LLM condense it into a fact list for the
editor's Fakten field (`backend/documents.py`), storing nothing.

The wire stays German (protocol.ts). `backend/library.py` is the boundary to the
English schema and does the sanitising (ADR 0059); this module only validates
shape and length. A Scenario is addressed by its `extern_id` (ADR 0050); the
write routes are owner-scoped by the Keycloak `sub` and the resolved tenant,
never by anything the client sends.
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
from backend.db.models import VISIBILITY_PRIVATE, VISIBILITY_TENANT
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

# Wire visibility <-> schema visibility. The User may only choose between these
# two; `public` is a review decision (ADR 0060 phase 3).
_SICHTBARKEIT = {"privat": VISIBILITY_PRIVATE, "unternehmen": VISIBILITY_TENANT}


def _limited(field: str, *, required: bool):
    cap = FIELD_LIMITS[field]
    return Field(..., min_length=1, max_length=cap) if required \
        else Field("", max_length=cap)


class ScenarioInput(BaseModel):
    """The fields an authoring caller sets. `name` / `kurzbeschreibung` are the
    card; `beschreibung` and the three case fields are prompt input (ADR 0045)
    and may be left empty — an empty case means "improvise"."""

    name: str = _limited("title", required=True)
    kurzbeschreibung: str = _limited("short_description", required=True)
    szenariotyp: str = _limited("scenario_type", required=False)
    # The situation is what the model gets as context -- an authored Scenario
    # without it is not a scenario, so it is required (the built-in seed rows
    # all carry one; ADR 0045 only allows the *case* fields to be blank).
    beschreibung: str = _limited("description", required=True)
    fallfakten: str = _limited("case_facts", required=False)
    anrufziel: str = _limited("call_goal", required=False)
    erfolgsbedingung: str = _limited("success_condition", required=False)

    def to_library(self) -> dict:
        """Wire names -> the English column names `backend/library.py` expects."""
        return {
            "title": self.name,
            "short_description": self.kurzbeschreibung,
            "scenario_type": self.szenariotyp,
            "description": self.beschreibung,
            "case_facts": self.fallfakten,
            "call_goal": self.anrufziel,
            "success_condition": self.erfolgsbedingung,
        }


class VisibilityInput(BaseModel):
    sichtbarkeit: str = Field(..., pattern="^(privat|unternehmen)$")


def _herkunft(scenario, subject: str) -> str:
    """Who the Scenario belongs to, from the caller's point of view. `eigen`
    wins over `unternehmen` -- the author still owns and can edit a Scenario
    they shared; `geteilt` (below) is the separate "visible to the company"
    flag the company filter uses."""
    if scenario.created_by == subject:
        return "eigen"
    if scenario.visibility == VISIBILITY_TENANT:
        return "unternehmen"
    return "vorlage"


def _card(scenario, subject: str) -> dict:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        "herkunft": _herkunft(scenario, subject),
        # True once shared with the company -- for the author's own Scenarios
        # too, which `herkunft` still reports as `eigen`.
        "geteilt": scenario.visibility == VISIBILITY_TENANT,
    }


def _detail(scenario) -> dict:
    """The full row, for the editor. Only ever returned for the caller's own
    Scenario, so the case fields are theirs to see."""
    return {
        "id": scenario.id,
        "name": scenario.name,
        "kurzbeschreibung": scenario.short_description,
        "szenariotyp": scenario.scenario_type,
        "beschreibung": scenario.description,
        "fallfakten": scenario.case_facts,
        "anrufziel": scenario.call_goal,
        "erfolgsbedingung": scenario.success_condition,
        "sichtbarkeit": "unternehmen" if scenario.visibility == VISIBILITY_TENANT else "privat",
    }


@router.get("")
def list_scenarios(
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> list[dict]:
    """Every Scenario the caller may select, each badged vorlage/eigen/unternehmen."""
    return [_card(s, user.sub) for s in library.list_scenarios(user.sub, tenant_id)]


@router.post("/dokument")
async def extract_document(
    datei: UploadFile = File(...),
    _user: AuthContext = Depends(require_user),
) -> dict:
    """Extract the text from an uploaded text-layer PDF and let the LLM condense
    it into a fact list for the editor's Fakten field (F-58). Stateless: nothing
    is stored, the client puts the returned text into the field and the User
    edits it before saving. `zusammengefasst` is False when the LLM was
    unreachable and the raw (truncated) text is returned instead."""
    try:
        reject_oversize_upload(datei.size)
        data = await datei.read()
        raw, seiten = extract_pdf_text(data)
    except DocumentError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        text = await summarise_facts(raw)
        zusammengefasst = True
    except OpenAIError:
        logger.warning("Document summary failed; returning raw text", exc_info=True)
        text = clean(raw)[:MAX_TEXT].strip()
        zusammengefasst = False
    return {"text": text, "seiten": seiten, "zusammengefasst": zusammengefasst}


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


@router.put("/{extern_id}/sichtbarkeit")
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
    if body.sichtbarkeit == "unternehmen" and tenant.is_default:
        raise HTTPException(
            status_code=409,
            detail="Ohne Unternehmen kann ein Szenario nicht geteilt werden.",
        )
    scenario = library.set_scenario_visibility(
        extern_id, _SICHTBARKEIT[body.sichtbarkeit], user.sub, tenant.id
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
