"""
sim: the headless simulation core.

Everything here is framework-agnostic and dependency-free (stdlib only). A
renderer (run_headless.py, game.py) imports `Simulation` and `World` from this
package and calls `step()` on a schedule. The brain is swappable -- see
`brains/llm_brain_template.py` for the LLM version of `StubBrain`.
"""

from .world import World
from .needs import Needs, Need
from .intent import Intent, GOTO, BUILD, REST, WANDER, IDLE
from .perception import Perception, build_perception
from .brain import Brain, StubBrain
from .body import Body
from .simulation import Simulation

__all__ = [
    "Simulation",
    "World",
    "Body",
    "Brain",
    "StubBrain",
    "Needs",
    "Need",
    "Intent",
    "Perception",
    "build_perception",
    "GOTO",
    "BUILD",
    "REST",
    "WANDER",
    "IDLE",
]
