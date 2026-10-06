"""Scenario routes (ADR 0058, 0062): listing, detail, authoring, sharing and the
PDF helper (F-58). Reverses and follow-ups can only be deleted here."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from openai import OpenAIError
from pydantic import BaseModel, Field
# Starlette's, not FastAPI's subclass: it is what `request.form()` returns.
from starlette.datastructures import UploadFile

from shared.db.models import SCENARIO_CATEGORIES, VISIBILITY_TENANT
from backend import library, recommendations
from backend.api.deps import current_tenant, current_tenant_id
from backend.auth import AuthContext, require_user
from backend.authored_text import FIELD_LIMITS, WIRE_FIELD_LIMITS, clean
from backend.documents import (
    MAX_TEXT,
    ExtractedDocument,
    document_name,
    merge_document_text,
    reject_oversize_batch,
    reject_oversize_upload,
    reject_too_many,
    summarise_facts,
)
from backend import limits
from backend.pdf_text import DocumentError, read_pdf
from backend.tenants import ResolvedTenant

logger = logging.getLogger(__name__)

# On the router, so no route can be reachable unauthenticated by omission.
router = APIRouter(prefix="/api/scenarios", dependencies=[Depends(require_user)])


def _limited(field: str, *, required: bool):
    cap = FIELD_LIMITS[field]
    return Field(..., min_length=1, max_length=cap) if required \
        else Field("", max_length=cap)


# Derived from the same tuple as the CHECK constraint.
_CATEGORY_PATTERN = "^(" + "|".join(SCENARIO_CATEGORIES) + "|)$"


class ScenarioInput(BaseModel):
    """`description` is required; the case fields may be empty ("improvise")."""

    name: str = _limited("title", required=True)
    short_description: str = _limited("short_description", required=True)
    # For the trainee, never the model (ADR 0054).
    briefing: str = _limited("briefing", required=False)
    # The situation is required; only the case fields may be blank (ADR 0045).
    description: str = _limited("description", required=True)
    case_facts: str = _limited("case_facts", required=False)
    call_goal: str = _limited("call_goal", required=False)
    # A closed vocabulary (ADR 0072); "" becomes NULL.
    category: str = Field("", pattern=_CATEGORY_PATTERN)

    def to_library(self) -> dict:
        """`name` is the `title` column; an empty category is NULL."""
        data = self.model_dump()
        data["title"] = data.pop("name")
        data["category"] = data["category"] or None
        return data


class VisibilityInput(BaseModel):
    # `public` needs review (ADR 0060).
    visibility: str = Field(..., pattern="^(private|tenant)$")


def _origin(scenario, subject: str) -> str:
    """`own` wins over `tenant`; `shared` says separately whether it is shared."""
    if scenario.created_by == subject:
        return "own"
    if scenario.visibility == VISIBILITY_TENANT:
        return "tenant"
    return "builtin"


def _origin_session(origin) -> dict | None:
    """None for an ordinary Scenario, or a reverse whose Session was deleted."""
    if origin is None:
        return None
    return {
        "id": origin.id,
        "persona": origin.persona,
        "started_at": origin.started_at.isoformat(),
    }


def _card(scenario, subject: str) -> dict:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        # On the card, so it shows before the call without a second request.
        "briefing": scenario.briefing,
        # The German twin for a built-in, whose `description` is English prompt text.
        "description": scenario.description_label or scenario.description,
        "category": scenario.category,
        "origin": _origin(scenario, subject),
        # Also for the author's own, which `origin` still reports as `own`.
        "shared": scenario.visibility == VISIBILITY_TENANT,
        # Neither editable nor shareable, like a reverse (ADR 0069).
        "follow_up": scenario.follow_up,
        # Separates reverses into their own filter and suppresses the edit.
        "reverse": scenario.reverse,
        "origin_session": _origin_session(scenario.origin_session),
        # Set by the listing for suggested cards (F-62).
        "recommendation": None,
    }


# The level-1 filter order (ADR 0072); the stable sort keeps creation order inside.
_ORIGIN_ORDER = ("builtin", "own", "follow_up", "reverse", "tenant")


def _origin_group(card: dict) -> int:
    """Follow-ups and reverses are `own` on the wire but grouped separately."""
    if card["reverse"]:
        return _ORIGIN_ORDER.index("reverse")
    return _ORIGIN_ORDER.index("follow_up" if card["follow_up"] else card["origin"])


def _detail(scenario, subject: str) -> dict:
    """`editable` comes from the verified `sub`. A built-in withholds `call_goal`
    (the answer key) and `case_facts` (its briefing replaces them) as None, not ""
    (ADR 0054, 0062)."""
    built_in = scenario.created_by is None
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        "briefing": scenario.briefing,
        # The German twin where there is one.
        "description": scenario.description_label or scenario.description,
        "case_facts": None if built_in else (scenario.case_facts_label or scenario.case_facts),
        "call_goal": None if built_in else scenario.call_goal,
        # "" so the editor's select has a value.
        "category": scenario.category or "",
        "visibility": scenario.visibility,
        # The write routes refuse reverses and follow-ups, so no edit is offered.
        "editable": (
            scenario.created_by == subject and
            not scenario.reverse and
            not scenario.follow_up
        ),
        "reverse": scenario.reverse,
        "follow_up": scenario.follow_up,
        "origin_session": _origin_session(scenario.origin_session),
        "reverse_brief": scenario.reverse_brief,
    }


def _cards(subject: str, tenant_id: int) -> list[dict]:
    """One ordering for the listing and for `/next`, which breaks ties by it."""
    return sorted(
        (_card(s, subject) for s in library.list_scenarios(subject, tenant_id)),
        key=_origin_group,
    )


def _candidate(card: dict) -> recommendations.Candidate:
    return recommendations.Candidate(card["id"], card["category"], card["reverse"])


@router.get("")
def list_scenarios(
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> list[dict]:
    cards = _cards(user.sub, tenant_id)
    picks = recommendations.for_subject(user.sub, [_candidate(card) for card in cards])
    for card in cards:
        pick = picks.get(card["id"])
        if pick:
            card["recommendation"] = {"call_type": pick.call_type, "goals": list(pick.goals)}
    return cards


@router.get("/{extern_id}/next")
def next_calls(
    extern_id: str,
    persona: str,
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> list[dict]:
    """F-64. Needs no stored Session, so it works for an unkept call."""
    cards = _cards(user.sub, tenant_id)
    by_id = {card["id"]: card for card in cards}
    people = {p.id: p for p in library.list_personas()}
    if extern_id not in by_id or persona not in people:
        raise HTTPException(status_code=404, detail="Unknown scenario or persona")

    partners = [recommendations.Partner(p.id, p.language_id) for p in people.values()]
    offers = recommendations.next_for_subject(
        user.sub,
        _candidate(by_id[extern_id]),
        recommendations.Partner(persona, people[persona].language_id),
        [_candidate(card) for card in cards],
        partners,
    )
    return [
        {
            "kind": offer.kind,
            "scenario_id": offer.scenario_id,
            "scenario_name": by_id[offer.scenario_id]["name"],
            "persona_id": offer.persona_id,
            "persona_name": people[offer.persona_id].name,
            "language": people[offer.persona_id].language_name,
            "recommendation": (
                {"call_type": offer.recommendation.call_type,
                 "goals": list(offer.recommendation.goals)}
                if offer.recommendation else None
            ),
            "unplayed": offer.unplayed,
        }
        for offer in offers
    ]


async def _read_documents(uploads: list[UploadFile]) -> list[ExtractedDocument]:
    """One unusable document fails the batch. Declared sizes are checked before
    reading, the running total after."""
    if not uploads:
        raise DocumentError("Es wurde keine Datei ausgewählt.")
    reject_too_many(len(uploads))

    documents: list[ExtractedDocument] = []
    # A lone upload needs no label in messages.
    named = len(uploads) > 1
    total = 0
    for upload in uploads:
        name = document_name(upload.filename)
        label = name if named else ""
        reject_oversize_upload(upload.size, label)
        data = await upload.read()
        total += len(data)
        reject_oversize_batch(total)
        text, pages = await read_pdf(data, label)
        documents.append(ExtractedDocument(name=name, pages=pages, text=text))
    return documents


@router.post("/document")
async def extract_document(
    request: Request, user: AuthContext = Depends(require_user)
) -> dict:
    """Condense PDFs into one fact list (F-58); `summarised` is False when the
    model failed and raw text is returned. The form is parsed here, not declared:
    FastAPI parses a declared body before checking the login (ADR 0109)."""
    limits.enforce(limits.DOCUMENT_SUMMARIES, user.sub)
    # Starlette's 1000-file cap answers in English; MAX_DOCUMENTS refuses first in German.
    async with request.form() as form:
        files = [f for f in form.getlist("files") if isinstance(f, UploadFile)]
        try:
            documents = await _read_documents(files)
        except DocumentError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    raw = merge_document_text(documents)
    try:
        text = await summarise_facts(raw)
        summarised = True
    except OpenAIError:
        logger.warning("Document summary failed; returning raw text", exc_info=True)
        text = clean(raw)[:MAX_TEXT].strip()
        summarised = False
    return {
        "text": text,
        "pages": sum(doc.pages for doc in documents),
        "summarised": summarised,
        "documents": [{"name": doc.name, "pages": doc.pages} for doc in documents],
    }


# Before "/{extern_id}", so the literal path wins.
@router.get("/field-limits")
def field_limits() -> dict[str, int]:
    """Served so the editor validates against the same source (ADR 0063)."""
    return WIRE_FIELD_LIMITS


@router.get("/{extern_id}")
def get_scenario(
    extern_id: str,
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    """Another User's private row is a 404, like an unknown id."""
    scenario = library.get_scenario(extern_id, user.sub, tenant_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return _detail(scenario, user.sub)


@router.post("", status_code=201)
def create_scenario(
    body: ScenarioInput,
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    scenario = library.create_scenario(body.to_library(), user.sub, tenant_id)
    return _detail(scenario, user.sub)


@router.patch("/{extern_id}")
def update_scenario(
    extern_id: str,
    body: ScenarioInput,
    user: AuthContext = Depends(require_user),
) -> dict:
    scenario = library.update_scenario(extern_id, body.to_library(), user.sub)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return _detail(scenario, user.sub)


@router.put("/{extern_id}/visibility")
def set_visibility(
    extern_id: str,
    body: VisibilityInput,
    user: AuthContext = Depends(require_user),
    tenant: ResolvedTenant = Depends(current_tenant),
) -> dict:
    # The default tenant has no colleagues; sharing would expose the row to every
    # company-less account.
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
    return _detail(scenario, user.sub)


@router.delete("/{extern_id}", status_code=204)
def delete_scenario(
    extern_id: str, user: AuthContext = Depends(require_user)
) -> Response:
    if not library.deactivate_scenario(extern_id, user.sub):
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return Response(status_code=204)
