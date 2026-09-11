"""The Persona and Scenario library, read from the database (ADR 0041).

The one place where the `persona` and `scenario` reference tables are read,
written and mapped onto the frozen value objects the rest of the backend uses.
Callers get plain dataclasses, so nothing outside this module has to know about
SQLAlchemy sessions or detached instances.

Since ADR 0058 the `scenario` table also holds User-authored rows, so every read
is scoped to the caller (`subject`) and, since ADR 0060, their company
(`tenant_id`, resolved in `backend/tenants.py`): a row is visible if it is
`public` (every shipped built-in), shared with the caller's tenant, or authored
by the caller. The client addresses a row by its `extern_id` (ADR 0050), never
by the internal id or the `key` slug, which an authored row does not have.
Authored text is run through `backend.authored_text.clean` on the way in
(ADR 0059).

Deliberately uncached: an edited Persona or Scenario takes effect on the next
Session, which is the whole point of loading them from the database.

Both readers filter on `active`. Retired rows are deactivated rather than
deleted, because a stored Session references them (ADR 0026, provision.py), so
this filter is the entire mechanism that removes one from the selection --
skipping it here would leave a retired row on offer.
"""
from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from backend.authored_text import clean
from backend.db import models
from backend.db.session import session_scope
from backend.personas import Persona, PersonaVoice
from backend.scenarios import OriginSession, Scenario

# Fields an authoring caller may set on a Scenario. `description` and the three
# case fields are prompt input (ADR 0045); `title` / `short_description` are the
# card and `briefing` the trainee's own text (ADR 0054). Everything else on the
# row (ids, ownership, `active`) is set here.
_SCENARIO_FIELDS = (
    "title", "short_description", "briefing",
    "description", "case_facts", "call_goal", "success_condition",
    "category",
)

# Authorable fields whose column is nullable, so an explicit None is a value --
# "no category" -- and has to reach the row rather than being skipped. Every
# other field maps to a NOT NULL column and must never be handed one.
_NULLABLE_SCENARIO_FIELDS = frozenset({"category"})


def _to_persona(row: models.Persona) -> Persona:
    ordered = sorted(row.objections, key=lambda e: e.position)
    return Persona(
        id=str(row.extern_id),
        name=row.name,
        language_id=row.language_code,
        language_name=row.language.name,
        voice=PersonaVoice(
            tts_voice=row.tts_voice,
            kugelaudio_voice_id=row.kugelaudio_voice_id,
        ),
        role_label=row.role_label,
        traits_label=row.traits_label,
        training_goal=row.training_goal,
        role=row.role,
        traits=row.traits,
        behavior=row.behavior,
        # Sorted here rather than left to the relationship's `order_by`: that
        # only orders what the database returns, so the mapping would depend on
        # how the row was obtained. `position` (ADR 0026) is the authored
        # order, and it is the order the prompt gets.
        objections=tuple(objection.text for objection in ordered),
        # Same source, same order: the label of objection i is at index i.
        objection_labels=tuple(
            objection.text_label or "" for objection in ordered
        ),
        avatar_url=row.avatar_url,
    )


def _to_scenario(row: models.Scenario) -> Scenario:
    return Scenario(
        id=str(row.extern_id),
        name=row.title,
        short_description=row.short_description,
        briefing=row.briefing,
        description=row.description,
        case_facts=row.case_facts,
        description_label=row.description_label,
        case_facts_label=row.case_facts_label,
        call_goal=row.call_goal,
        success_condition=row.success_condition,
        category=row.category,
        created_by=row.created_by,
        visibility=row.visibility,
        follow_up=row.derived_from_session_id is not None,
        reverse=row.reverse,
        origin_session=_to_origin_session(row.origin_session),
        reverse_brief=row.reverse_brief,
    )


def _to_origin_session(row: models.Session | None) -> OriginSession | None:
    """The Session a reverse replays (ADR 0070), or None once it is gone --
    the foreign key is `SET NULL`, so this is a normal state and not an error."""
    if row is None:
        return None
    return OriginSession(
        id=str(row.extern_id), persona=row.persona.name, started_at=row.started_at
    )


# The origin Session and its Persona, loaded with the Scenario rather than left
# to a lazy load: every listing renders the card of every reverse, and one
# query per row would be the N+1 the selection screen notices first.
_WITH_ORIGIN = joinedload(models.Scenario.origin_session).joinedload(
    models.Session.persona
)


def _visible_to(model, subject: str, tenant_id: int):
    """The WHERE clause for the library a caller may see (ADR 0058, extended by
    ADR 0060): public rows, rows shared with the caller's tenant, and the
    caller's own. Never trusts a value from the client — `subject` and
    `tenant_id` are both derived server-side from the verified token."""
    return or_(
        model.visibility == models.VISIBILITY_PUBLIC,
        and_(
            model.visibility == models.VISIBILITY_TENANT,
            model.tenant_id == tenant_id,
        ),
        model.created_by == subject,
    )


def _as_extern_id(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


# Visibility values a User may set on their own row: not `public` (that needs
# review, ADR 0060 phase 3).
_USER_SETTABLE_VISIBILITY = (models.VISIBILITY_PRIVATE, models.VISIBILITY_TENANT)


def _shareable_ref(extern_id: str, visibility: str) -> uuid.UUID | None:
    """The parsed extern_id, or None if the requested visibility is one a User
    may not set themselves or the id is malformed."""
    if visibility not in _USER_SETTABLE_VISIBILITY:
        return None
    return _as_extern_id(extern_id)


# --- Personas ---------------------------------------------------------------
#
# Personas are curated, not User-authored (unlike Scenarios): there is no
# create/edit here, and no visibility scoping -- every selectable Persona is a
# public built-in.


def list_personas() -> list[Persona]:
    """Every selectable Persona, inactive ones left out, ordered by name."""
    with session_scope() as db:
        rows = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.language),
                joinedload(models.Persona.objections),
            )
            .where(models.Persona.active)
            .order_by(models.Persona.name)
        ).unique().all()  # unique(): a joined collection yields one row per objection
        return [_to_persona(row) for row in rows]


def get_persona(extern_id: str) -> Persona | None:
    """The Persona with this `extern_id`, or None if it does not exist or is
    inactive."""
    ref = _as_extern_id(extern_id)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.language),
                joinedload(models.Persona.objections),
            )
            .where(models.Persona.extern_id == ref, models.Persona.active)
        ).unique().one_or_none()
        return _to_persona(row) if row is not None else None


# --- Scenarios -------------------------------------------------------------


def list_scenarios(subject: str, tenant_id: int) -> list[Scenario]:
    """Every Scenario this caller may select, oldest first.

    By creation time rather than by title: the caller sees them grouped by
    category (`backend/api/scenarios.py` sorts on top of this order), and within
    a category the order a User can predict is the one they were made in.
    """
    with session_scope() as db:
        rows = db.scalars(
            select(models.Scenario)
            .options(_WITH_ORIGIN)
            .where(
                models.Scenario.active,
                _visible_to(models.Scenario, subject, tenant_id),
            )
            .order_by(models.Scenario.created_at, models.Scenario.scenario_id)
        ).all()
        return [_to_scenario(row) for row in rows]


def get_scenario(extern_id: str, subject: str, tenant_id: int) -> Scenario | None:
    """The Scenario with this `extern_id`, or None — see `get_persona`."""
    ref = _as_extern_id(extern_id)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario)
            .options(_WITH_ORIGIN)
            .where(
                models.Scenario.extern_id == ref,
                models.Scenario.active,
                _visible_to(models.Scenario, subject, tenant_id),
            )
        ).one_or_none()
        return _to_scenario(row) if row is not None else None


def create_scenario(
    data: dict,
    subject: str,
    tenant_id: int | None,
    derived_from_session_id: int | None = None,
) -> Scenario:
    """Author a private Scenario (ADR 0058), stamped with the caller's tenant so
    sharing is later a `visibility` flip (ADR 0060).

    The single write path into `scenario`, the drafted follow-up included
    (ADR 0069, through `create_follow_up` below) — which is what keeps
    sanitising, caps and ownership in one place. A caller with no tenant claim
    to stamp with passes None; `set_scenario_visibility` stamps such a row when
    it is first shared.
    """
    with session_scope() as db:
        row = models.Scenario(
            created_by=subject,
            tenant_id=tenant_id,
            visibility=models.VISIBILITY_PRIVATE,
            active=True,
            derived_from_session_id=derived_from_session_id,
            **_sanitised(data, _SCENARIO_FIELDS),
        )
        db.add(row)
        db.flush()
        db.refresh(row)
        return _to_scenario(row)


def update_scenario(extern_id: str, data: dict, subject: str) -> Scenario | None:
    """Edit a Scenario the caller authored. None if it is not theirs.

    A reverse is not among them (ADR 0070): it is a copy of a case that was
    played, and editing it would leave a row claiming to replay a conversation
    it no longer matches. Excluded in the WHERE clause rather than checked
    afterwards, so it answers exactly like a row that is not the caller's.
    """
    ref = _as_extern_id(extern_id)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).where(
                models.Scenario.extern_id == ref,
                models.Scenario.created_by == subject,
                models.Scenario.reverse.is_(False),
            )
        ).one_or_none()
        if row is None:
            return None
        for field, value in _sanitised(data, _SCENARIO_FIELDS).items():
            setattr(row, field, value)
        db.flush()
        db.refresh(row)
        return _to_scenario(row)


def deactivate_scenario(extern_id: str, subject: str) -> bool:
    """Retire a Scenario the caller authored (soft)."""
    return _deactivate(models.Scenario, extern_id, subject)


def set_scenario_visibility(
    extern_id: str, visibility: str, subject: str, tenant_id: int
) -> Scenario | None:
    """Share the caller's Scenario with their tenant, or make it private again
    (ADR 0060). Only `private` <-> `tenant`. None if the row is not theirs.

    A reverse is excluded for a second reason on top of the one in
    `update_scenario`: its briefing is derived from the author's own wrap-up
    (ADR 0070), so sharing the row would hand colleagues a reading of that
    person's feedback.

    A row that somehow has no `tenant_id` (created before tenant stamping) is
    stamped with the caller's tenant here, so sharing still works."""
    ref = _shareable_ref(extern_id, visibility)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).where(
                models.Scenario.extern_id == ref,
                models.Scenario.created_by == subject,
                models.Scenario.reverse.is_(False),
            )
        ).one_or_none()
        if row is None:
            return None
        if row.tenant_id is None:
            row.tenant_id = tenant_id
        row.visibility = visibility
        db.flush()
        return _to_scenario(row)


# --- Written from a Session (ADR 0069, ADR 0070) ---------------------------
#
# Two kinds of Scenario are not authored but built out of a finished Session:
# the follow-up drafted from its Feedback and the reverse that replays it. Both
# are asked for by the User, both are stored, and both are at most one per
# Session -- a UNIQUE column each says so. They live here for the reason
# everything else does: this is the only module that writes the table.


def _restore(where) -> Scenario | None:
    """The row this Session already produced, made selectable again if the User
    had removed it. None if there is none.

    Shared by the two lookups below because the reason is shared: the create
    routes ask for the existing row *before* they call a model, so pressing the
    button twice costs nothing and yields the same Scenario. Reactivating
    rather than returning the retired row is what keeps that answer usable -- a
    deactivated Scenario is absent from the library, so handing back its id
    would name something the selection screen cannot show.
    """
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).options(_WITH_ORIGIN).where(where)
        ).one_or_none()
        if row is None:
            return None
        row.active = True
        db.flush()
        return _to_scenario(row)


def restore_reverse(origin_session_id: int) -> Scenario | None:
    """The reverse already made from this Session (ADR 0070), or None."""
    return _restore(models.Scenario.origin_session_id == origin_session_id)


def restore_follow_up(session_id: int) -> Scenario | None:
    """The follow-up already drafted from this Session (ADR 0069), or None."""
    return _restore(models.Scenario.derived_from_session_id == session_id)


def create_follow_up(
    draft: dict, subject: str, tenant_id: int | None, session_id: int
) -> Scenario | None:
    """Store one drafted follow-up as the caller's own Scenario (ADR 0069).

    `create_scenario` with the provenance filled in, plus the same answer to
    the same race the reverse has below: `derived_from_session_id` is UNIQUE,
    so two overlapping requests for one Session end with one row, and the
    loser reads it rather than raising. Nothing else differs -- a follow-up is
    an authored Scenario in every respect the rest of this module knows about,
    which is why it goes through the ordinary write path.

    None only where the row the loser went looking for has itself gone in the
    meantime, which the route answers exactly as it answers a Session that is
    no longer there.
    """
    try:
        return create_scenario(draft, subject, tenant_id, derived_from_session_id=session_id)
    except IntegrityError:
        return restore_follow_up(session_id)


def create_reverse(
    origin_session_id: int, subject: str, tenant_id: int, brief: dict
) -> Scenario | None:
    """Write the reverse of one Session (ADR 0070). None if that Session is gone.

    The case is copied from the Scenario that was actually played, here rather
    than in the caller: this module already owns what a Scenario row is made
    of, and a copy assembled outside it would be a second place to update when
    a field is added.

    Lands private and owned by the caller, like an authored Scenario -- but
    unlike one it can never be shared or edited (see the two guards above). The
    text is not run through `clean()` on the way in: the case is a copy of a
    row that was cleaned when it was written, and the briefing is sanitised by
    `backend/reversals.py` as it comes out of the model.

    The route looks for an existing reverse before it gets here, so the UNIQUE
    constraint is only reached when two requests for the same Session overlap
    -- a second tab, or a double click that outran the button's disabled state.
    That is answered with the row that won rather than with a 500: both callers
    asked for the same thing and there is exactly one of it. The briefing the
    loser generated is dropped, which costs a model call and nothing else.
    """
    try:
        return _insert_reverse(origin_session_id, subject, tenant_id, brief)
    except IntegrityError:
        return restore_reverse(origin_session_id)


def _insert_reverse(
    origin_session_id: int, subject: str, tenant_id: int, brief: dict
) -> Scenario | None:
    """The write itself, in a transaction of its own so the caller above can let
    it fail and read instead -- `session_scope` has rolled it back by then."""
    with session_scope() as db:
        origin = db.get(models.Session, origin_session_id)
        if origin is None:
            return None
        played = origin.scenario
        row = models.Scenario(
            created_by=subject,
            tenant_id=tenant_id,
            visibility=models.VISIBILITY_PRIVATE,
            active=True,
            reverse=True,
            origin_session_id=origin_session_id,
            reverse_brief=brief,
            title=played.title,
            short_description=played.short_description,
            description=played.description,
            case_facts=played.case_facts,
            call_goal=played.call_goal,
            success_condition=played.success_condition,
            # Carried over so a reverse sits under the same category filter as
            # the call it replays -- it is the same kind of call, seen from the
            # other side (ADR 0072).
            category=played.category,
        )
        db.add(row)
        db.flush()
        db.refresh(row)
        return _to_scenario(row)


# --- shared helpers -------------------------------------------------------


def _sanitised(data: dict, fields: tuple[str, ...]) -> dict:
    """Pick the authorable fields out of `data` and run the string ones through
    `clean` (ADR 0059). A field the caller omitted is left out, so the same
    helper serves create (all fields) and a partial update. A None reaches the
    row only for a nullable column -- that is how a category is cleared."""
    out = {}
    for field in fields:
        if field not in data:
            continue
        if data[field] is None and field not in _NULLABLE_SCENARIO_FIELDS:
            continue
        value = data[field]
        out[field] = clean(value) if isinstance(value, str) else value
    return out


def _deactivate(model, extern_id: str, subject: str) -> bool:
    ref = _as_extern_id(extern_id)
    if ref is None:
        return False
    with session_scope() as db:
        row = db.scalars(
            select(model).where(
                model.extern_id == ref, model.created_by == subject
            )
        ).one_or_none()
        if row is None:
            return False
        row.active = False
        return True
