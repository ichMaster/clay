"""
Perception: the unit of communication FROM the body TO the brain.

This is the whole "request" the bot sends when it asks what to do next.
It bundles exactly two things you named:

    1. the needs (levels + urgencies)
    2. the real picture around (local block patch + useful spatial features)

plus a little context about the last intent so the brain has continuity.

`to_prompt_dict()` is the seam for Lili: that dict is literally what gets
serialised into the LLM prompt later. The stub brain reads the structured
fields directly; the LLM brain will read the same data as JSON/text.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Perception:
    tick: int
    position: tuple                 # (x, z)
    needs: dict                     # name -> level
    urgencies: dict                 # name -> urgency
    surroundings: list              # local block patch (see world.surroundings)
    unvisited_nearby: tuple | None  # nearest unexplored cell
    buildable_nearby: tuple | None  # a nearby cell to stack onto
    last_intent: str = ""
    last_status: str = ""           # "done" | "interrupted" | ""

    def to_prompt_dict(self) -> dict:
        """What the LLM brain will receive. Keep it compact and readable."""
        return {
            "tick": self.tick,
            "position": list(self.position),
            "needs": self.needs,
            "urgencies": self.urgencies,
            "nearest_unexplored": list(self.unvisited_nearby) if self.unvisited_nearby else None,
            "buildable_spot": list(self.buildable_nearby) if self.buildable_nearby else None,
            "surroundings": self.surroundings,
            "last_intent": self.last_intent,
            "last_status": self.last_status,
        }


def build_perception(world, body) -> Perception:
    """Assemble the snapshot from the live world + body state."""
    x, z = body.pos
    return Perception(
        tick=body.tick_count,
        position=(x, z),
        needs=body.needs.levels(),
        urgencies=body.needs.urgencies(),
        surroundings=world.surroundings(x, z, radius=3),
        unvisited_nearby=world.nearest_unvisited(x, z),
        buildable_nearby=world.buildable_near(x, z),
        last_intent=str(body.current_intent) if body.current_intent else "",
        last_status=body.last_status,
    )
