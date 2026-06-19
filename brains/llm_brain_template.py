"""
LLMBrain -- the swap target. THIS is where Lili plugs in.

The body never changes. It already calls:

    brain.request(perception)   # may be slow
    intent = brain.poll()       # None until ready
    brain.busy                  # True while thinking

StubBrain answered instantly. LLMBrain answers slowly, on a worker thread,
so the body keeps executing the previous intent (walking, building, resting)
during the seconds the model takes. When the answer lands, poll() returns it
and the body adopts the new intent on the next tick. No freeze, no rework.

To go from this generic agent to Lili:
  1. Replace SYSTEM_PROMPT with her canon (persona, voice).
  2. Feed her six NEEDS instead of the three generic ones (just a wider dict).
  3. Add the personality layers (OPINIONS / SELF_REGARD / RELATIONAL_FEELINGS /
     INNER_MONOLOGUE) into the prompt context.
  4. Keep the SAME Intent contract out, optionally adding a `say` / monologue
     field alongside `kind` / `target`.

This file guards the anthropic import so the package still loads without the
SDK installed. Install with:  pip install anthropic
"""

from __future__ import annotations
import json
import threading

from sim.brain import Brain
from sim.intent import Intent, GOTO, BUILD, REST, WANDER, IDLE
from . import config   # loads .env on import; supplies MODEL / MAX_TOKENS / API_KEY

# Generic placeholder persona. Swap for Lili's canon.
SYSTEM_PROMPT = """\
You are the mind of a small agent living in a voxel world. You are given your
needs and the world around you, and you decide ONE next action. You do not
control movement frame by frame -- you pick a single high-level intent and the
body carries it out on its own.

Reply with ONLY a JSON object, no prose, no markdown fences:
{"kind": "goto|build|rest|wander|idle", "target": [x, z] or null, "reason": "short"}

Guidance:
- If rest is the most depleted need, rest.
- If novelty is low, goto the nearest unexplored cell to seek new ground.
- If creation is low, build at a nearby buildable spot.
- Otherwise wander.
"""

_VALID = {GOTO, BUILD, REST, WANDER, IDLE}


class LLMBrain(Brain):
    def __init__(self, model: str | None = None, max_tokens: int | None = None):
        # All LLM config lives in .env (see brains/config.py); explicit args
        # here are just optional per-instance overrides.
        self.model = model or config.MODEL
        self.max_tokens = max_tokens or config.MAX_TOKENS
        self._pending: Intent | None = None
        self._busy = False
        self._lock = threading.Lock()

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def request(self, perception) -> None:
        with self._lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._work, args=(perception,), daemon=True).start()

    def poll(self):
        with self._lock:
            intent, self._pending = self._pending, None
            return intent

    # ---- worker thread ---------------------------------------------------
    def _work(self, perception):
        try:
            intent = self._call_model(perception)
        except Exception as exc:                       # never kill the body
            intent = Intent(WANDER, reason=f"fallback ({type(exc).__name__})")
        with self._lock:
            self._pending = intent
            self._busy = False

    def _call_model(self, perception) -> Intent:
        import anthropic  # imported lazily so the package loads without it
        client = anthropic.Anthropic()

        payload = json.dumps(perception.to_prompt_dict(), ensure_ascii=False)
        msg = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return self._parse(text)

    @staticmethod
    def _parse(text: str) -> Intent:
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)
        kind = data.get("kind", WANDER)
        if kind not in _VALID:
            kind = WANDER
        target = data.get("target")
        target = tuple(target) if isinstance(target, (list, tuple)) and len(target) == 2 else None
        return Intent(kind=kind, target=target, reason=data.get("reason", "")[:80])


# Usage (identical wiring to the stub):
#
#   from sim import Simulation, World
#   from brains.llm_brain_template import LLMBrain
#   sim = Simulation(world=World(), brain=LLMBrain())
#   while True: sim.step()
