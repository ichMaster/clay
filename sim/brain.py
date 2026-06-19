"""
Brain: the swap point.

The body never knows whether the brain is a few `if` statements or Lili
running on an LLM. It only knows this contract:

    brain.request(perception)   # ask "what next?" -- may be slow
    intent = brain.poll()       # None until an answer is ready
    brain.busy                  # True while a request is in flight

This request/poll split is what makes the LLM swap free. A StubBrain
answers instantly (poll returns immediately). An LLMBrain kicks off a
thread / async call in request() and returns the Intent from poll() only
once the model replies -- and the body loop does not change one line,
because it already keeps executing the previous intent while busy.

See brains/llm_brain_template.py for the Lili-shaped subclass.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import random

from .intent import Intent, GOTO, BUILD, REST, WANDER, IDLE


class Brain(ABC):
    @abstractmethod
    def request(self, perception) -> None:
        """Receive a perception snapshot and begin deciding."""

    @abstractmethod
    def poll(self):
        """Return an Intent if ready, else None. Consumes it once."""

    @property
    @abstractmethod
    def busy(self) -> bool:
        """True while a decision is still being computed."""


class StubBrain(Brain):
    """
    Rule-based placeholder. Picks the most urgent need and maps it to an
    intent grounded in the perceived world. Instant: no latency, never busy.

    This is intentionally simple and legible -- its only job is to make the
    bot visibly alive so the architecture can be watched working. Lili
    replaces this whole class, nothing else.
    """

    ACT_THRESHOLD = 0.6  # act on a need once its urgency crosses this

    def __init__(self, seed: int = 0):
        self._pending = None
        self._rng = random.Random(seed)

    def request(self, perception) -> None:
        self._pending = self._decide(perception)

    def poll(self):
        intent, self._pending = self._pending, None
        return intent

    @property
    def busy(self) -> bool:
        return False  # synchronous

    # ---- the actual policy (this is what Lili supersedes) ----------------
    def _decide(self, p) -> Intent:
        # find the most urgent need
        top_name = max(p.urgencies, key=p.urgencies.get)
        top_urg = p.urgencies[top_name]

        if top_urg < self.ACT_THRESHOLD:
            # nothing pressing -> low-key wander keeps her moving and alive
            return Intent(WANDER, reason="content, drifting")

        if top_name == "rest":
            return Intent(REST, reason="tired, settling to recover")

        if top_name == "novelty":
            target = p.unvisited_nearby
            if target:
                return Intent(GOTO, target=tuple(target), reason="restless, seeking new ground")
            return Intent(WANDER, reason="restless, wandering")

        if top_name == "creation":
            target = p.buildable_nearby
            if target:
                return Intent(BUILD, target=tuple(target), reason="urge to build something")
            return Intent(WANDER, reason="creative itch, looking for a spot")

        return Intent(IDLE, reason="no clear pull")
