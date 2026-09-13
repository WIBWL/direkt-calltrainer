"""REST routes for the Scenario library and User-authored Scenarios (ADR 0058).

`GET /api/scenarios` feeds the selection screen: every Scenario the caller may
see, each badged `builtin` (a shipped built-in), `own` (one they authored) or
`tenant` (shared by a colleague), and `follow_up` where the worker wrote it from
one of their own Sessions (ADR 0069). The list carries card fields only.

`GET /api/scenarios/{id}` is the read view behind that list (ADR 0062): any
Scenario the caller may select, with `editable` saying whether they may also
open the editor on it. `call_goal` — the caller's intent and the bar that
settles it — is the answer key to the exercise (ADR 0043/0045) and is withheld
from a built-in. The *write* routes remain owner-scoped.

`POST /api/scenarios/document` (F-58) is a stateless helper: it extracts the
uploaded text-layer PDFs -- several at once -- and has the LLM condense them
into one fact list for the editor's Fakten field (`backend/documents.py`),
storing nothing.

A reverse (ADR 0070) and a follow-up (ADR 0069) are rows of this table too,
listed and read through the same routes and badged `own` like anything else the
caller owns. Each is written by its own route on the Session
(`POST /api/sessions/{id}/reverse`, `.../follow-up`) and by nothing here: the
edit and share routes below refuse both. A reverse copies a case that was
actually played and carries a briefing built from its author's own wrap-up; a
follow-up is drafted to sit exactly at that wrap-up's improvement point. In
either case an edited row would no longer be the thing the Session produced,
and a shared one would pass on a reading of the author's feedback. DELETE
takes both: the one action left on them is removing them again.

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

from backend import library, recommendations
from backend.api.deps import current_tenant, current_tenant_id
from backend.auth import AuthContext, require_user
from backend.authored_text import FIELD_LIMITS, WIRE_FIELD_LIMITS, clean
from backend.db.models import SCENARIO_CATEGORIES, VISIBILITY_TENANT
from backend.documents import (
    MAX_TEXT,
    DocumentError,
    ExtractedDocument,
    document_name,
    extract_pdf_text,
    merge_document_text,
    reject_oversize_batch,
    reject_oversize_upload,
    summarise_facts,
)
from backend.tenants import ResolvedTenant

logger = logging.getLogger(__name__)

# The requirement sits on the router, as it does on the other five: every
# route below needs a verified caller, and a tenth one added later would
# otherwise be reachable unauthenticated with nothing to say so -- no test
# fails, no warning, and the browser works. The routes that take a `user`
# parameter still do, because they *use* it; only the two that named one
# purely to force the check have lost it.
router = APIRouter(prefix="/api/scenarios", dependencies=[Depends(require_user)])


def _limited(field: str, *, required: bool):
    cap = FIELD_LIMITS[field]
    return Field(..., min_length=1, max_length=cap) if required \
        else Field("", max_length=cap)


# "" (no category) or one of the three F-03 contexts (ADR 0072). Kept in step
# with the CHECK constraint by deriving it from the same tuple.
_CATEGORY_PATTERN = "^(" + "|".join(SCENARIO_CATEGORIES) + "|)$"


class ScenarioInput(BaseModel):
    """The fields an authoring caller sets. `name` / `short_description` are the
    card and `briefing` the trainee's own text (ADR 0054); `description` and the
    three case fields are prompt input (ADR 0045) and may be left empty — an
    empty case means "improvise"."""

    name: str = _limited("title", required=True)
    short_description: str = _limited("short_description", required=True)
    # Display, addressed to the trainee, never to the model (ADR 0054).
    # Optional: a Scenario without one briefs nobody, which is what every row
    # authored before this field existed does.
    briefing: str = _limited("briefing", required=False)
    # The situation is what the model gets as context -- an authored Scenario
    # without it is not a scenario, so it is required (the built-in seed rows
    # all carry one; ADR 0045 only allows the *case* fields to be blank).
    description: str = _limited("description", required=True)
    case_facts: str = _limited("case_facts", required=False)
    call_goal: str = _limited("call_goal", required=False)
    # Display/filter only (ADR 0072), never prompt input -- and a closed
    # vocabulary rather than the free text it replaces, so the value the
    # category filter runs on is one the database will accept. "" is the empty
    # choice the editor offers and reaches the column as NULL.
    category: str = Field("", pattern=_CATEGORY_PATTERN)

    def to_library(self) -> dict:
        """1:1 with the schema columns, except the card field `name`, which is
        the `title` column (ADR 0061), and the empty category, which is NULL."""
        data = self.model_dump()
        data["title"] = data.pop("name")
        data["category"] = data["category"] or None
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


def _origin_session(origin) -> dict | None:
    """The conversation a reverse replays, for its card (ADR 0070). None for an
    ordinary Scenario, and for a reverse whose Session has since been deleted —
    the row outlives it, so the client renders both cases."""
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
        # On the card rather than only on the detail route: the briefing is
        # shown before the call from the list the selection screen already
        # holds (ADR 0054), without a second request. Nothing is withheld
        # here in any case — this text is written to be read by whoever
        # plays the Scenario.
        "briefing": scenario.briefing,
        # Null for an uncategorised Scenario; the category filter then only
        # shows it under "Alle" (ADR 0072).
        "category": scenario.category,
        "origin": _origin(scenario, subject),
        # True once shared with the company -- for the author's own Scenarios
        # too, which `origin` still reports as `own`.
        "shared": scenario.visibility == VISIBILITY_TENANT,
        # Drafted from a Session's feedback (ADR 0069). A category of its own in
        # the library, carried beside `origin` rather than as a value of it: it
        # is the caller's own Scenario, but like a reverse it is neither
        # editable nor shareable -- it is the exercise one reading of their
        # feedback produced, and an edited one is no longer that.
        "follow_up": scenario.follow_up,
        # A reverse (ADR 0070) is `origin: "own"` like anything else the caller
        # owns; this is what separates it out into its own filter, and what
        # tells the card not to offer an edit it would be refused.
        "reverse": scenario.reverse,
        "origin_session": _origin_session(scenario.origin_session),
        # Set by the listing for the few it suggests (F-62), with the reason;
        # a view over the cards, so a suggested one keeps its own origin too.
        "recommendation": None,
    }


# The order the selection screen shows the origins in, matching its level-1
# filter (ADR 0072). Not `scenario.category`, which is the thematic level-2
# filter. `library.list_scenarios` returns them by creation time and Python's
# sort is stable, so that order survives inside each group.
_ORIGIN_ORDER = ("builtin", "own", "follow_up", "reverse", "tenant")


def _origin_group(card: dict) -> int:
    """Which level-1 group a card belongs to. Three of the five are not values
    of `origin`: a follow-up (ADR 0069) and a reverse (ADR 0070) are both
    `own` on the wire and are separated out here, exactly as the filter
    separates them. A row is never both."""
    if card["reverse"]:
        return _ORIGIN_ORDER.index("reverse")
    return _ORIGIN_ORDER.index("follow_up" if card["follow_up"] else card["origin"])


def _detail(scenario, subject: str) -> dict:
    """One Scenario as the client reads it (ADR 0062).

    Two audiences, one payload: the editor, which opens only on a row the
    caller owns, and the read-only info panel, which opens on any row they
    may select. `editable` is what separates them, and it is decided here
    from the verified `sub` rather than taken from the client.

    A built-in withholds `call_goal` — None, not "", so the client can tell
    "withheld" from "the author left it empty". That field is the caller's
    *intent* and the bar by which the call is done; reading it in advance
    would hand the trainee the answer to the
    exercise. `description` and `case_facts` are the situation, which comes
    up in the call anyway, so they are served. A Scenario the caller or a
    colleague authored withholds nothing: they wrote it, or work with the
    person who did.

    A reverse (ADR 0070) is authored and therefore withholds nothing either,
    which is the exception that ADR deliberately takes to ADR 0043: the played
    case reaches the client because seeing what the Persona had is the point,
    and the User has just heard it play out.
    """
    # No author at all = a shipped built-in. A colleague's shared row has an
    # author, just not this caller, and is served in full.
    built_in = scenario.created_by is None
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        "briefing": scenario.briefing,
        # The display twin where there is one, the field itself otherwise
        # (ADR 0062). A built-in's prompt text is English (ADR 0043) and the
        # seed carries a German twin for it; an authored Scenario has no twin
        # because its author already wrote it in their own language. Same wire
        # name either way: the client shows one text and never both.
        "description": scenario.description_label or scenario.description,
        "case_facts": scenario.case_facts_label or scenario.case_facts,
        "call_goal": None if built_in else scenario.call_goal,
        # "" rather than null, so the editor's select has a value to sit on.
        "category": scenario.category or "",
        # `public` for a built-in now that this route serves one. The editor
        # never sees that value: it opens only where `editable` is true.
        "visibility": scenario.visibility,
        # Authorship, not visibility: a colleague's shared Scenario is
        # readable but not editable (ADR 0058 -- only the author may write).
        # And the two kinds built from a Session are the caller's own yet still
        # not editable: the write routes exclude both in their WHERE clause
        # (ADR 0069, ADR 0070), so a panel that offered the edit would open an
        # editor whose Save answers 404.
        "editable": (
            scenario.created_by == subject and
            not scenario.reverse and
            not scenario.follow_up
        ),
        "reverse": scenario.reverse,
        # Beside `reverse` and for the same reason the panel needs it: these
        # two are the rows whose only action is deletion.
        "follow_up": scenario.follow_up,
        "origin_session": _origin_session(scenario.origin_session),
        # The German briefing the User reads during a reverse call; null on
        # every other row.
        "reverse_brief": scenario.reverse_brief,
    }


@router.get("")
def list_scenarios(
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> list[dict]:
    """Every Scenario the caller may select, each badged builtin/own/tenant,
    grouped by origin and by creation time within one."""
    cards = sorted(
        (_card(s, user.sub) for s in library.list_scenarios(user.sub, tenant_id)),
        key=_origin_group,
    )
    picks = recommendations.for_subject(user.sub, [
        recommendations.Candidate(card["id"], card["category"], card["reverse"])
        for card in cards
    ])
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
    """What to play after a call on this Scenario with this Persona (F-64).

    Needs no stored Session, so it answers for a call that was not kept too. A
    Scenario or Persona the caller cannot select is a 404, as everywhere.
    """
    cards = sorted(
        (_card(s, user.sub) for s in library.list_scenarios(user.sub, tenant_id)),
        key=_origin_group,
    )
    by_id = {card["id"]: card for card in cards}
    people = {p.id: p for p in library.list_personas()}
    if extern_id not in by_id or persona not in people:
        raise HTTPException(status_code=404, detail="Unknown scenario or persona")

    def candidate(card: dict) -> recommendations.Candidate:
        return recommendations.Candidate(card["id"], card["category"], card["reverse"])

    partners = [recommendations.Partner(p.id, p.language_id) for p in people.values()]
    offers = recommendations.next_for_subject(
        user.sub,
        candidate(by_id[extern_id]),
        recommendations.Partner(persona, people[persona].language_id),
        [candidate(card) for card in cards],
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
    """Every upload, read and extracted, in the order they were sent.

    One file at a time and checked as it goes: the per-file ceiling against the
    declared size *before* reading, the total against what has actually arrived
    *after*. A client that sends no Content-Length therefore still cannot get
    more than one oversized file past the gate. The first unusable document
    fails the whole request -- a half-applied batch would leave the User
    guessing which of their files made it into the field."""
    if not uploads:
        raise DocumentError("Es wurde keine Datei ausgewählt.")

    documents: list[ExtractedDocument] = []
    # Named only when there is more than one: a lone upload needs no label, and
    # the single-file messages stay the sentences they always were.
    named = len(uploads) > 1
    total = 0
    for upload in uploads:
        name = document_name(upload.filename)
        label = name if named else ""
        reject_oversize_upload(upload.size, label)
        data = await upload.read()
        total += len(data)
        reject_oversize_batch(total)
        text, pages = extract_pdf_text(data, label)
        documents.append(ExtractedDocument(name=name, pages=pages, text=text))
    return documents


@router.post("/document")
async def extract_document(files: list[UploadFile] = File(...)) -> dict:
    """Extract the text from the uploaded text-layer PDFs and let the LLM
    condense them into one fact list for the editor's Fakten field (F-58).

    Several files are summarised *together*, in one model call: the field holds
    one list, and two documents condensed apart would repeat every fact they
    share. Stateless: nothing is stored, the client puts the returned text into
    the field and the User edits it before saving. `summarised` is False when
    the LLM was unreachable and the raw (truncated) text is returned instead."""
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
        # The whole batch, so the client can say what was read without adding up
        # a list it would otherwise only need for that.
        "pages": sum(doc.pages for doc in documents),
        "summarised": summarised,
        "documents": [{"name": doc.name, "pages": doc.pages} for doc in documents],
    }


# Defined before "/{extern_id}" so the literal path is matched first.
@router.get("/field-limits")
def field_limits() -> dict[str, int]:
    """The maximum length the API enforces for each authorable Scenario field.
    The editor caps its inputs from here, so its limits are the same source that
    validates them rather than a hand-kept mirror that drifts (ADR 0063). Keyed
    as the client knows the fields, so the `title` column reports as the card
    field `name` (ADR 0061); that renaming lives in `authored_text.py`."""
    return WIRE_FIELD_LIMITS


# Defined before "/{extern_id}" so the literal path is matched first.
@router.get("/{extern_id}")
def get_scenario(
    extern_id: str,
    user: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    """One Scenario the caller may select, for the info panel and — where
    `editable` says so — for the editor (ADR 0062).

    Scoped by `library.get_scenario`, which serves built-ins, rows shared
    with the caller's company, and their own. Another User's private row is
    invisible there and stays a 404, indistinguishable from an unknown id
    (ADR 0031/0050)."""
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
    """Author a Scenario. It lands private, owned by the caller (ADR 0058)."""
    scenario = library.create_scenario(body.to_library(), user.sub, tenant_id)
    return _detail(scenario, user.sub)


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
    return _detail(scenario, user.sub)


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
    return _detail(scenario, user.sub)


@router.delete("/{extern_id}", status_code=204)
def delete_scenario(
    extern_id: str, user: AuthContext = Depends(require_user)
) -> Response:
    """Retire one of the caller's own Scenarios (soft, ADR 0058)."""
    if not library.deactivate_scenario(extern_id, user.sub):
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return Response(status_code=204)
