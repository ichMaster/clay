"""
World: a small voxel terrain.

The world is a body-of-truth that exists independently of the brain.
It stores a heightmap (the surface the bot walks on) and lets blocks be
placed on top. The bot moves on the surface; pathfinding is 2D over the
(x, z) grid while the visual world is 3D voxel columns.

Nothing here knows about the LLM or the bot's needs. It only answers
spatial questions: what is around, what is reachable, what is unexplored.
"""

from __future__ import annotations
from dataclasses import dataclass, field


def _hash01(x: int, z: int, seed: int) -> float:
    """Deterministic hash -> float in [0, 1). Stdlib only, no numpy."""
    h = (x * 374761393 + z * 668265263 + seed * 2654435761) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def _value_noise(x: int, z: int, seed: int, scale: int) -> float:
    """Bilinear value noise over a coarse hash grid -> [0, 1)."""
    gx, gz = x // scale, z // scale
    fx, fz = (x % scale) / scale, (z % scale) / scale
    a = _hash01(gx, gz, seed)
    b = _hash01(gx + 1, gz, seed)
    c = _hash01(gx, gz + 1, seed)
    d = _hash01(gx + 1, gz + 1, seed)
    ab = a + (b - a) * fx
    cd = c + (d - c) * fx
    return ab + (cd - ab) * fz


@dataclass
class World:
    width: int = 32          # x
    depth: int = 32          # z
    seed: int = 7
    max_terrain: int = 5     # base terrain tops out around here
    heightmap: list = field(default_factory=list)   # heightmap[x][z] -> surface height
    placed: dict = field(default_factory=dict)      # (x, z) -> count of blocks placed by the bot
    visited: set = field(default_factory=set)       # (x, z) cells the bot has stepped on

    def __post_init__(self):
        if not self.heightmap:
            self.generate()

    # ---- terrain ----------------------------------------------------------
    def generate(self):
        self.heightmap = []
        for x in range(self.width):
            col = []
            for z in range(self.depth):
                n = 0.6 * _value_noise(x, z, self.seed, 8) + 0.4 * _value_noise(x, z, self.seed + 99, 4)
                col.append(int(n * self.max_terrain))
            self.heightmap.append(col)

    # ---- queries ----------------------------------------------------------
    def in_bounds(self, x: int, z: int) -> bool:
        return 0 <= x < self.width and 0 <= z < self.depth

    def surface_height(self, x: int, z: int) -> int:
        """Top of the column = terrain height + any blocks the bot placed."""
        return self.heightmap[x][z] + self.placed.get((x, z), 0)

    def is_walkable(self, x: int, z: int) -> bool:
        # On this starter every in-bounds cell is walkable (the bot steps onto
        # the surface). Step height is ignored for simplicity; A* + jump cost
        # is the natural upgrade.
        return self.in_bounds(x, z)

    # ---- actions the body performs ---------------------------------------
    def place_block(self, x: int, z: int) -> bool:
        if not self.in_bounds(x, z):
            return False
        self.placed[(x, z)] = self.placed.get((x, z), 0) + 1
        return True

    def mark_visited(self, x: int, z: int) -> bool:
        """Returns True if this cell is newly visited (grounds the novelty need)."""
        cell = (x, z)
        new = cell not in self.visited
        self.visited.add(cell)
        return new

    # ---- the "real picture around" sent to the brain ---------------------
    def surroundings(self, x: int, z: int, radius: int = 3) -> list:
        """Local patch of the world: relative cell offsets, surface height,
        whether visited, whether a block sits there. This is the raw spatial
        perception handed to the brain."""
        patch = []
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                cx, cz = x + dx, z + dz
                if not self.in_bounds(cx, cz):
                    continue
                patch.append({
                    "dx": dx,
                    "dz": dz,
                    "height": self.surface_height(cx, cz),
                    "visited": (cx, cz) in self.visited,
                    "built": self.placed.get((cx, cz), 0),
                })
        return patch

    def nearest_unvisited(self, x: int, z: int, search: int = 12):
        """Closest unexplored cell within a search box, or a far random-ish
        fallback. Grounds the novelty drive in real geography."""
        best = None
        best_d = 10 ** 9
        lo_x, hi_x = max(0, x - search), min(self.width, x + search + 1)
        lo_z, hi_z = max(0, z - search), min(self.depth, z + search + 1)
        for cx in range(lo_x, hi_x):
            for cz in range(lo_z, hi_z):
                if (cx, cz) in self.visited:
                    continue
                d = abs(cx - x) + abs(cz - z)
                if d < best_d and d > 0:
                    best_d, best = d, (cx, cz)
        return best

    def buildable_near(self, x: int, z: int, radius: int = 2):
        """A nearby cell the bot can stack a block onto. Grounds creation."""
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if dx == 0 and dz == 0:
                    continue
                cx, cz = x + dx, z + dz
                if self.in_bounds(cx, cz):
                    return (cx, cz)
        return None
