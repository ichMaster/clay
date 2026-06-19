"""
Simulation: ties the world, the body and the brain into one tickable thing.

A renderer (terminal or Ursina) just calls `step()` on a schedule and reads
state. The simulation itself is headless and framework-agnostic, so the same
core runs under a 3D game window, a terminal log, or a unit test.
"""

from __future__ import annotations

from .world import World
from .body import Body
from .brain import Brain, StubBrain


class Simulation:
    def __init__(self, world: World | None = None, brain: Brain | None = None,
                 start=None):
        self.world = world or World()
        self.brain = brain or StubBrain()
        self.body = Body(self.world, self.brain, start=start)
        self.last_intent_str = ""

    def step(self):
        self.body.tick()
        decided = self.body.just_decided           # brain decision, or None
        if decided is not None:
            self.last_intent_str = str(decided)
        return decided
