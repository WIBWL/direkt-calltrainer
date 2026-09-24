"""The Persona and Scenario library, read from the database (ADR 0041), uncached.

The one place the `persona`/`scenario` tables are read, written and mapped to dataclasses.
Reads are scoped to the caller's `sub` and `tenant_id` (ADR 0058/0060), rows addressed by
`extern_id` (ADR 0050). The `active` filter is the only thing hiding a retired row."""
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
    "description", "case_facts", "call_goal",
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
        voice=PersonaVoice(kugelaudio_voice_id=row.kugelaudio_voice_id),
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
    """Every Scenario this caller may select, oldest first (creation order is the
    one a User can predict; `backend/api/scenarios.py` groups on top of it)."""
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


def played_scenario_ids(subject: str) -> set[str]:
    """The ids of every Scenario this subject has a stored Session on."""
    with session_scope() as db:
        rows = db.scalars(
            select(models.Scenario.extern_id)
            .join(models.Session, models.Session.scenario_id == models.Scenario.scenario_id)
            .where(models.Session.subject_id == subject)
            .distinct()
        ).all()
        return {str(extern_id) for extern_id in rows}


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

    The single write path into `scenario`, follow-ups included (ADR 0069). No
    tenant claim passes None; `set_scenario_visibility` stamps it on first share."""
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


# What the write routes below match on, beside ownership: a row that was
# authored rather than built from a finished Session. `follow_up` is not a
# column -- it is `derived_from_session_id is not None` (see `_to_scenario`),
# so the absence of that provenance is what says "hand-authored" here.
_AUTHORED_ONLY = (
    models.Scenario.reverse.is_(False),
    models.Scenario.derived_from_session_id.is_(None),
)


def update_scenario(extern_id: str, data: dict, subject: str) -> Scenario | None:
    """Edit a Scenario the caller authored. None if it is not theirs.

    Reverses (ADR 0070) and follow-ups (ADR 0069) are excluded in the WHERE clause:
    an edited one is no longer the call or the exercise it was built from, and
    they answer exactly like a row that is not the caller's."""
    ref = _as_extern_id(extern_id)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).where(
                models.Scenario.extern_id == ref,
                models.Scenario.created_by == subject,
                *_AUTHORED_ONLY,
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
    Reverses and follow-ups are excluded -- sharing one would hand colleagues a
    reading of the author's feedback. A row without `tenant_id` is stamped here."""
    ref = _shareable_ref(extern_id, visibility)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).where(
                models.Scenario.extern_id == ref,
                models.Scenario.created_by == subject,
                *_AUTHORED_ONLY,
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
# The follow-up and the reverse: asked for by the User, at most one per Session
# (a UNIQUE column each), and here because this module is the table's only writer.


def _restore(where) -> Scenario | None:
    """The row this Session already produced, reactivated if the User had removed
    it. None if there is none.

    The create routes ask this *before* calling a model, so a second press costs
    nothing; reactivating matters because a retired row is absent from the library."""
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

    `create_scenario` plus provenance. `derived_from_session_id` is UNIQUE, so of
    two overlapping requests the loser reads the winner's row instead of raising;
    None only if that row has meanwhile gone too."""
    try:
        return create_scenario(draft, subject, tenant_id, derived_from_session_id=session_id)
    except IntegrityError:
        return restore_follow_up(session_id)


def create_reverse(
    origin_session_id: int, subject: str, tenant_id: int, brief: dict
) -> Scenario | None:
    """Write the reverse of one Session (ADR 0070). None if that Session is gone.

    Copies the played case here, where the row's shape is owned. Not re-cleaned (the
    case was cleaned when written; `reversals.py` sanitises the briefing). On a UNIQUE
    race the winner's row is returned rather than a 500."""
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
            # The German display twins travel with their fields; without them the
            # info panel showed a built-in's case in English. NULL for an authored one.
            description_label=played.description_label,
            case_facts_label=played.case_facts_label,
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
