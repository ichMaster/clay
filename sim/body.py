"""
Body: the bot that lives on fast ticks.

Every tick the body:
    1. decays its needs (it is alive, time passes)
    2. decides whether it needs a new decision, and if so asks the brain
    3. adopts a new intent if the brain has one ready
    4. executes one step of its current intent (pure reactive code)

The brain is consulted only at moments (3). Between them the body runs
itself: it walks, it places blocks, it rests -- hundreds of ticks per
single brain call. That gap is what makes life feel continuous instead of
turn-based.
"""

from __future__ import annotations

from .intent import Intent, GOTO, BUILD, REST, WANDER, IDLE
from .needs import Needs
from .perception import build_perception


def _step_toward(pos, target, world):
    """Greedy 4-neighbour step that reduces Manhattan distance. A* + jump
    cost is the natural upgrade for rough terrain."""
    x, z = pos
    tx, tz = target
    best, best_d = pos, abs(tx - x) + abs(tz - z)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, nz = x + dx, z + dz
        if world.is_walkable(nx, nz):
            d = abs(tx - nx) + abs(tz - nz)
            if d < best_d:
                best_d, best = d, (nx, nz)
    return best


class Body:
    # when to wake the brain for a fresh "what next?"
    HEARTBEAT = 200          # ask at least this often, even if nothing changed
    WANDER_STEPS = 6         # a wander intent lasts roughly this many ticks
    REST_TARGET = 0.95       # rest until this level
    BUILD_BLOCKS = 1         # blocks placed per build intent

    def __init__(self, world, brain, start=None):
        self.world = world
        self.brain = brain
        self.pos = start or (world.width // 2, world.depth // 2)
        self.needs = Needs.default()
        self.current_intent: Intent | None = None
        self.last_status = ""
        self.tick_count = 0
        self.last_decision_tick = -10 ** 9
        self._intent_progress = 0
        self.just_decided = None
        self.brain_decisions = 0
        self.world.mark_visited(*self.pos)

    # ---- main loop --------------------------------------------------------
    def tick(self):
        self.tick_count += 1
        self.needs.tick()
        self.just_decided = None     # set only when a BRAIN decision lands this tick

        if self._needs_decision() and not self.brain.busy:
            self.brain.request(build_perception(self.world, self))

        new_intent = self.brain.poll()
        if new_intent is not None:
            self._adopt(new_intent)
            self.just_decided = new_intent
            self.brain_decisions += 1

        # Reactive default: if there is nothing to do and the brain was not
        # consulted (nothing mattered enough), the body keeps itself alive
        # with a low-stakes wander -- no brain call needed just to idle.
        if self.current_intent is None or self.last_status == "done":
            self._adopt(Intent(WANDER, reason="idling"), is_decision=False)

        self._execute_step()

    def _adopt(self, intent, is_decision=True):
        self.current_intent = intent
        self._intent_progress = 0
        self.last_status = ""
        if is_decision:
            self.last_decision_tick = self.tick_count

    # ---- decide WHEN to think --------------------------------------------
    def _needs_decision(self) -> bool:
        # cold start
        if self.current_intent is None:
            return True
        # a SUBSTANTIVE intent just finished -> ask what is next
        if self.last_status == "done" and self.current_intent.kind in (GOTO, BUILD, REST):
            return True
        # a need crossed the acting threshold WHILE the body is only drifting
        # -> escalate to the brain. If a substantive intent is already running,
        # let it finish first (don't re-ask every tick).
        if self.current_intent.kind in (WANDER, IDLE) and self.needs.most_urgent().urgency > 0.6:
            return True
        # periodic check-in even if nothing changed
        if self.tick_count - self.last_decision_tick > self.HEARTBEAT:
            return True
        return False

    # ---- execute the current intent (reactive, no brain) -----------------
    def _execute_step(self):
        it = self.current_intent
        if it is None:
            return
        self._intent_progress += 1

        if it.kind == GOTO:
            self._do_goto(it)
        elif it.kind == BUILD:
            self._do_build(it)
        elif it.kind == REST:
            self._do_rest(it)
        elif it.kind == WANDER:
            self._do_wander(it)
        else:  # IDLE
            self.last_status = "done"

    def _move_to(self, cell, novelty_gain=0.06):
        self.pos = cell
        if self.world.mark_visited(*cell):
            self.needs.replenish("novelty", novelty_gain)   # new ground feeds novelty

    def _do_goto(self, it):
        if it.target is None or self.pos == it.target:
            self.last_status = "done"
            return
        nxt = _step_toward(self.pos, it.target, self.world)
        if nxt == self.pos:                 # stuck / arrived as close as possible
            self.last_status = "done"
            return
        self._move_to(nxt)
        if self.pos == it.target:
            self.last_status = "done"

    def _do_build(self, it):
        target = it.target
        if target is None:
            self.last_status = "done"
            return
        adjacent = abs(target[0] - self.pos[0]) + abs(target[1] - self.pos[1]) <= 1
        if not adjacent:
            self._move_to(_step_toward(self.pos, target, self.world))
            return
        self.world.place_block(*target)
        self.needs.replenish("creation", 0.45)
        self.last_status = "done"

    def _do_rest(self, it):
        self.needs.replenish("rest", 0.02)
        if self.needs.items["rest"].level >= self.REST_TARGET:
            self.last_status = "done"

    def _do_wander(self, it):
        # one short hop to a walkable neighbour
        x, z = self.pos
        import random
        opts = [(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if self.world.is_walkable(x + dx, z + dz)]
        if opts:
            self._move_to(random.choice(opts), novelty_gain=0.015)  # weak: aimless
        if self._intent_progress >= self.WANDER_STEPS:
            self.last_status = "done"
