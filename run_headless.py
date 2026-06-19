"""
Headless run: watch the bot live in the terminal. No graphics, runs anywhere.

It prints a line every time the brain makes a decision (a new intent), and
every so often draws a tiny top-down map plus the need bars, so you can see
the life cycle: explore when novelty drops, build when the creative urge
rises, rest when tired, drift otherwise.

    python run_headless.py
    python run_headless.py --ticks 4000 --map-every 300
"""

from __future__ import annotations
import argparse

from sim import Simulation


def bar(level: float, width: int = 12) -> str:
    filled = int(round(level * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def draw_map(sim: Simulation):
    w = sim.world
    bx, bz = sim.body.pos
    lines = []
    for z in range(w.depth):
        row = []
        for x in range(w.width):
            if (x, z) == (bx, bz):
                row.append("@")              # the bot
            elif w.placed.get((x, z)):
                row.append("#")              # a placed block
            elif (x, z) in w.visited:
                row.append(".")              # explored
            else:
                row.append(" ")              # untouched
        lines.append("".join(row))
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=3000)
    ap.add_argument("--map-every", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    from sim import World, StubBrain
    sim = Simulation(world=World(seed=args.seed), brain=StubBrain())

    print(f"Bot starts at {sim.body.pos}. Running {args.ticks} ticks.\n")
    decisions = 0

    for t in range(1, args.ticks + 1):
        intent = sim.step()
        if intent is not None:
            decisions += 1
            lv = sim.body.needs.levels()
            print(f"t={t:5d}  DECIDE  {intent}")
            print(f"          needs  "
                  f"novelty {bar(lv['novelty'])}  "
                  f"creation {bar(lv['creation'])}  "
                  f"rest {bar(lv['rest'])}")

        if t % args.map_every == 0:
            print(f"\n--- tick {t} | pos {sim.body.pos} | "
                  f"explored {len(sim.world.visited)} | "
                  f"built {sum(sim.world.placed.values())} ---")
            draw_map(sim)
            print()

    print(f"\nDone. {decisions} brain decisions over {args.ticks} ticks "
          f"(~1 every {args.ticks // max(decisions,1)} ticks).")


if __name__ == "__main__":
    main()
