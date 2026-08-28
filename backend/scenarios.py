"""The Scenario value object the backend works with.

The Scenarios themselves live in the database and are loaded through
`backend/library.py` (ADR 0041); this module only defines their shape.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
