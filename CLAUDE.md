# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Clay is a starter core for an agent ("a creature") that lives in a voxel world. A
**body** runs on fast ticks (movement, pathfinding, need decay, executing the last
intent) entirely in plain code. A **brain** is consulted only at moments that matter
and returns one high-level intent. The whole point of the design is that the brain is a
swappable component: a rule-based `StubBrain` today, an LLM ("Lili"/"Lumi") tomorrow,
with **zero changes to the body**. The README is in Ukrainian; this file captures the
operational facts in English.

## Package layout

```
sim/                  # the headless core (package, stdlib-only)
  __init__.py         # exports Simulation, World, StubBrain, Intent, etc.
  world.py  needs.py  intent.py  perception.py  brain.py  body.py  simulation.py
brains/
  __init__.py
  llm_brain_template.py   # imports `from sim.brain ...`, `from sim.intent ...`
run_headless.py       # entry point — `from sim import ...`   (stays at root)
game.py               # entry point — `from sim import ...`   (stays at root)
```

- Modules under `sim/` use **relative imports** (`from .world import World`); entry
  points use **absolute package imports** (`from sim import Simulation`). Keep it this
  way — if you add a module to `sim/`, import its siblings with `.`, not `sim.`.
- `sim/__init__.py` is the public surface. `run_headless.py` and `game.py` import
  `Simulation`, `World`, `StubBrain` from it by name — if you rename those, update the
  re-exports there too.

## Architecture: the body/brain contract

The data flows in a loop, and the seams between the two halves are the load-bearing part
of the codebase:

```
body (fast ticks)  ──Perception──>  brain  ──Intent──>  body
 decay needs, move,   "what next?"       executes intent
 execute last intent                     for hundreds of ticks alone
```

- **`Perception`** (`perception.py`) is the request body→brain: needs levels +
  urgencies, a local patch of the world, nearest unexplored cell, a buildable spot, and
  last-intent continuity. `to_prompt_dict()` is the **seam for the LLM** — that dict is
  literally what gets serialized into the prompt. Keep it compact and JSON-friendly.
- **`Intent`** (`intent.py`) is the reply brain→body: one of `goto` / `build` / `rest` /
  `wander` / `idle`, an optional `(x, z)` target, and a free-text `reason`. The body
  executes it over many ticks with no further brain calls.
- **`Brain`** (`brain.py`) is an ABC with exactly three members:
  `request(perception)`, `poll()` (returns an `Intent` once, else `None`), and the
  `busy` property. This **request/poll split is what makes the LLM swap free**:
  `StubBrain` answers synchronously (`busy` always `False`); `LLMBrain`
  (`llm_brain_template.py`) kicks off a daemon thread in `request()` and returns from
  `poll()` only when the model replies — meanwhile the body keeps executing the previous
  intent, so there is never a freeze. Any new brain must preserve this contract and never
  block in `request()`.

### When the brain wakes (body.py `_needs_decision`)

The brain is **not** consulted every tick — that gap is the design's whole reason for
existing. It wakes only on: cold start, a *substantive* intent (`goto`/`build`/`rest`)
finishing, a need crossing urgency `0.6` while merely drifting, or the `HEARTBEAT`
interval (default 200 ticks). Otherwise the body self-drives with a low-stakes `wander`
and makes **no** brain call. In headless runs this is ~1 brain call per ~18 ticks.

### The world (world.py)

A heightmap + bot-placed blocks. Pure spatial truth — it knows nothing about needs or the
brain. Pathfinding is **2D greedy** over the `(x, z)` grid (`_step_toward` in `body.py`),
not A*; every in-bounds cell is `is_walkable` and step height is ignored. A* + jump cost
is the documented natural upgrade. Terrain is deterministic value-noise (stdlib only, no
numpy), seeded by `World.seed`.

### Renderers are thin shells

`Simulation.step()` (`simulation.py`) is the only thing a renderer calls; it returns the
brain decision for this tick (or `None`). `run_headless.py` (terminal, stdlib-only) and
`game.py` (Ursina 3D) both just call `step()` on a schedule and read state — **all life
logic stays in `sim/`**. `game.py` glides the bot visually between cells while the sim
works in discrete cells ("backend in cells, frontend in motion"). Voxels use a flat
**Minecraft palette** (`game.py` `_PALETTE` / `height_color`, coloured by elevation).
**macOS rendering gotcha (the black-screen bug):** on this Mac, Panda3D/Ursina gets an
OpenGL **2.1 / GLSL 1.20** context (via Metal), but Ursina's built-in shaders are
`#version 130/140` — they fail to compile, so every entity renders **pure black** (HUD text
survives via Panda's own text pipeline). The fix is `game.py`'s custom **`VOXEL_SHADER`**, a
minimal `#version 120` shader that compiles there and shades each face by its normal (no
scene lights needed); it's set on every cube via `shader=VOXEL_SHADER`. Don't "simplify" it
back to the default shader. (Colours are still built with `color.rgb32(r,g,b)` since the
palette is 0–255 and Ursina's `color.rgb` expects 0–1.) `game.py` also has an **optional
manual mode**
(renderer-only, doesn't touch the core): `M` toggles AUTO↔MANUAL, `WASD`/arrows step the
bot, `B` stacks a block; in MANUAL the brain stops moving the bot but needs still decay.
The Ukrainian player guide is [ПОСІБНИК.md](ПОСІБНИК.md).

## Commands

The core has **no dependencies** (Python stdlib only). There is no test suite, linter, or
build step in the repo. Once the package layout is in place (see above):

```bash
# headless run (works anywhere, no graphics)
python run_headless.py
python run_headless.py --ticks 4000 --map-every 300 --seed 7

# 3D voxel view (local only)
pip install ursina
python game.py

# LLM brain (the "Lili" swap)
pip install anthropic
cp .env.example .env    # then paste your key into ANTHROPIC_API_KEY
```

Headless map glyphs: `@` bot, `#` placed block, `.` explored, ` ` untouched.

## Swapping in / writing an LLM brain

`llm_brain_template.py` is the worked example. To turn the generic agent into "Lili",
the file documents four steps: replace `SYSTEM_PROMPT` with the persona/voice, feed a
wider NEEDS dict (her six instead of the generic three), add personality layers into
prompt context, and optionally add a `say` field alongside `kind`/`target` — **the
`Intent` contract out stays the same**. The `anthropic` import is lazy so the package
loads without the SDK. `_work` catches all exceptions and falls back to a `wander` intent
so a model error never kills the body.

**LLM config lives in `.env`** (not in code). `brains/config.py` is a stdlib `.env`
loader (no `python-dotenv`) read on import; it populates `os.environ` (real env vars win)
and exposes `MODEL` (default `claude-haiku-4-5` — kept deliberately for a high-frequency
real-time loop), `MAX_TOKENS` (default 200), `API_KEY`, and `is_configured()`. The SDK
reads `ANTHROPIC_API_KEY` from the environment automatically once the loader has run.
`.env` is gitignored; `.env.example` is the committed template. **The project has its own
venv at `clay/.venv`** (gitignored) with `ursina` + `anthropic` installed — run with
`.venv/bin/python game.py` (the system `python3` has neither; recreate with
`python3 -m venv .venv && .venv/bin/pip install ursina anthropic`).

When wiring a brain in, mirror the stub exactly:
`Simulation(world=World(), brain=LLMBrain())`.

## Tuning levers (from README)

| lever | location | effect |
|---|---|---|
| `TICK_INTERVAL` | `game.py` | speed of life |
| `HEARTBEAT` | `body.py` | max ticks between brain calls |
| need `decay` | `needs.py` | how fast needs rise |
| `ACT_THRESHOLD` | `brain.py` (StubBrain) | urgency needed before acting |

Intent granularity trades off against brain-call frequency: fine single-cell `goto`s mean
many calls; for an LLM, issue **broader** intents ("explore that region") so one call
covers hundreds of ticks.
