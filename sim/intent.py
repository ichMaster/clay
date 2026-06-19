"""
Intent: the unit of communication FROM the brain TO the body.

The brain never drives the bot frame by frame. It returns one high-level
intent ("go to that cell", "build here", "rest") and the body executes it
over many ticks on its own. `reason` is free text -- a stub fills it with a
rule name; later it becomes Lili's inner-monologue line.
"""

from __future__ import annotations
from dataclasses import dataclass, field

# intent kinds the body knows how to execute
GOTO = "goto"
BUILD = "build"
REST = "rest"
WANDER = "wander"
IDLE = "idle"


@dataclass
class Intent:
    kind: str
    target: tuple | None = None     # (x, z) cell, when relevant
    meta: dict = field(default_factory=dict)
    reason: str = ""

    def __str__(self):
        t = f" -> {self.target}" if self.target else ""
        return f"{self.kind}{t} ({self.reason})"
