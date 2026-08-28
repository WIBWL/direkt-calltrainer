"""The Persona value objects the backend works with.

The Personas themselves live in the database and are loaded through
`backend/library.py` (ADR 0041); this module only defines their shape, so
that `backend/session/` can depend on it without pulling in database access.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaVoice:
    tts_voice: str
    kugelaudio_voice_id: int


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    language_id: str
    voice: PersonaVoice
    role: str
    traits: str
    behavior: str
