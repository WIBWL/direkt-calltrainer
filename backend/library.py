"""The only reader and writer of the `persona`/`scenario` tables (ADR 0041). Reads
are scoped by `sub` and tenant (ADR 0058/0060); `active` hides retired rows."""
from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from shared.db import models
from shared.db.session import session_scope
from backend.authored_text import clean
from backend.personas import Persona, PersonaVoice
from backend.scenarios import OriginSession, Scenario

# What an authoring caller may set; ids, ownership and `active` are set here.
_SCENARIO_FIELDS = (
    "title", "short_description", "briefing",
    "description", "case_facts", "call_goal",
    "category",
)

# Nullable, so an explicit None ("no category") reaches the row.
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
        hard=row.hard,
        # Sorted here, not by the relationship's order_by, so the mapping does
        # not depend on how the row was loaded.
        objections=tuple(objection.text for objection in ordered),
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
    """None once the Session is gone (SET NULL), a normal state."""
    if row is None:
        return None
    return OriginSession(
        id=str(row.extern_id), persona=row.persona.name, started_at=row.started_at
    )


# Joined, or every reverse card in a listing costs a query.
_WITH_ORIGIN = joinedload(models.Scenario.origin_session).joinedload(
    models.Session.persona
)


def _visible_to(model, subject: str, tenant_id: int):
    """Public rows, rows shared with the caller's tenant, and the caller's own.
    Both arguments come from the verified token."""
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


# `public` needs review and is not settable by Users.
_USER_SETTABLE_VISIBILITY = (models.VISIBILITY_PRIVATE, models.VISIBILITY_TENANT)


def _shareable_ref(extern_id: str, visibility: str) -> uuid.UUID | None:
    if visibility not in _USER_SETTABLE_VISIBILITY:
        return None
    return _as_extern_id(extern_id)


# Personas are curated: no authoring and no visibility scoping.


def list_personas() -> list[Persona]:
    with session_scope() as db:
        rows = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.language),
                joinedload(models.Persona.objections),
            )
            .where(models.Persona.active)
            .order_by(models.Persona.name)
        ).unique().all()
        return [_to_persona(row) for row in rows]


def get_persona(extern_id: str) -> Persona | None:
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


def list_scenarios(subject: str, tenant_id: int) -> list[Scenario]:
    """Oldest first; the route groups on top of that."""
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
    with session_scope() as db:
        rows = db.scalars(
            select(models.Scenario.extern_id)
            .join(models.Session, models.Session.scenario_id == models.Scenario.scenario_id)
            .where(models.Session.subject_id == subject)
            .distinct()
        ).all()
        return {str(extern_id) for extern_id in rows}


def get_scenario(extern_id: str, subject: str, tenant_id: int) -> Scenario | None:
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
    description_label: str | None = None,
) -> Scenario:
    """The single write path into `scenario`, follow-ups included. Lands private,
    stamped with the caller's tenant so sharing is a `visibility` flip."""
    with session_scope() as db:
        row = models.Scenario(
            created_by=subject,
            tenant_id=tenant_id,
            visibility=models.VISIBILITY_PRIVATE,
            active=True,
            derived_from_session_id=derived_from_session_id,
            description_label=description_label,
            **_sanitised(data, _SCENARIO_FIELDS),
        )
        db.add(row)
        db.flush()
        db.refresh(row)
        return _to_scenario(row)


# Hand-authored only: reverses and follow-ups are not editable or shareable.
_AUTHORED_ONLY = (
    models.Scenario.reverse.is_(False),
    models.Scenario.derived_from_session_id.is_(None),
)


def update_scenario(extern_id: str, data: dict, subject: str) -> Scenario | None:
    """None if it is not theirs; reverses and follow-ups answer the same way."""
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
    return _deactivate(models.Scenario, extern_id, subject)


def set_scenario_visibility(
    extern_id: str, visibility: str, subject: str, tenant_id: int
) -> Scenario | None:
    """Only `private` <-> `tenant`. Reverses and follow-ups are excluded: sharing
    one would hand colleagues a reading of the author's feedback."""
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


def _restore(where) -> Scenario | None:
    """Reactivates the row this Session already produced. Asked before any model
    call, so a second press costs nothing."""
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
    return _restore(models.Scenario.origin_session_id == origin_session_id)


def restore_follow_up(session_id: int) -> Scenario | None:
    return _restore(models.Scenario.derived_from_session_id == session_id)


def create_follow_up(
    draft: dict, subject: str, tenant_id: int | None, session_id: int
) -> Scenario | None:
    """On a UNIQUE race the loser reads the winner's row instead of raising."""
    try:
        return create_scenario(
            draft, subject, tenant_id,
            derived_from_session_id=session_id,
            description_label=draft.get("description_label") or None,
        )
    except IntegrityError:
        return restore_follow_up(session_id)


def create_reverse(
    origin_session_id: int, subject: str, tenant_id: int, brief: dict
) -> Scenario | None:
    """None if that Session is gone. Not re-cleaned: the case was cleaned when
    written. On a UNIQUE race the winner's row is returned."""
    try:
        return _insert_reverse(origin_session_id, subject, tenant_id, brief)
    except IntegrityError:
        return restore_reverse(origin_session_id)


def _insert_reverse(
    origin_session_id: int, subject: str, tenant_id: int, brief: dict
) -> Scenario | None:
    """In its own transaction, so the caller can let it fail and read instead."""
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
            # German display twins travel with their fields.
            description_label=played.description_label,
            case_facts_label=played.case_facts_label,
            # Same kind of call, so the same category filter (ADR 0072).
            category=played.category,
        )
        db.add(row)
        db.flush()
        db.refresh(row)
        return _to_scenario(row)


def _sanitised(data: dict, fields: tuple[str, ...]) -> dict:
    """Only the fields present; None reaches the row only for a nullable column."""
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
