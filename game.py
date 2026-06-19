"""
Voxel renderer (Ursina) -- the Minecraft-style 3D view. Run locally:

    pip install ursina
    python game.py

The renderer is a thin shell over the same headless simulation. It does two
things only: draw the world + bot, and call sim.step() on a fixed schedule.
All life logic lives in sim/. The bot GLIDES between cells (frontend
interpolates motion) while the simulation works in discrete cells per tick --
the same "backend in cells, frontend in motion" split used in Haven.

Camera: mouse-drag to orbit, scroll to zoom (EditorCamera).
Manual control (optional): M toggles AUTO<->MANUAL, WASD/arrows move the bot,
B stacks a block. In MANUAL the brain stops driving; needs still decay.
"""

from ursina import (Ursina, Entity, EditorCamera, color, Vec3, Text, Shader,
                    lerp, time as utime, scene)

from sim import Simulation, World

TICK_INTERVAL = 0.08   # seconds between simulation ticks (lower = livelier)
GLIDE_SPEED = 6.0      # how fast the bot visually catches up to its cell


# A GLSL 1.20 voxel shader -- THE fix for the "black world".
# Ursina's built-in shaders are #version 130/140, which this Mac's OpenGL
# (reported as 2.1 / GLSL 1.20 via Metal) refuses to compile -- so every entity
# rendered as a black silhouette no matter the colour. This minimal #version 120
# shader compiles there, and shades each face by its normal (top brightest) so
# the voxels read as 3D without any scene lights.
VOXEL_SHADER = Shader(language=Shader.GLSL, vertex="""\
#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
varying vec3 world_normal;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    mat3 m = mat3(p3d_ModelMatrix[0].xyz, p3d_ModelMatrix[1].xyz, p3d_ModelMatrix[2].xyz);
    world_normal = normalize(m * p3d_Normal);
}
""", fragment="""\
#version 120
uniform vec4 p3d_ColorScale;          // Ursina sets this from the entity's `color`
varying vec3 world_normal;
void main() {
    vec3 light_dir = normalize(vec3(0.4, 1.0, 0.3));
    float shade = 0.62 + 0.38 * max(dot(world_normal, light_dir), 0.0);
    gl_FragColor = vec4(p3d_ColorScale.rgb * shade, p3d_ColorScale.a);
}
""")

# Minecraft-style palette: discrete block colours by elevation, low -> high.
# Values are 0-255; color.rgb32() converts them to Ursina's 0-1 range (which is
# what the shader's p3d_ColorScale expects).
_PALETTE = [
    (64, 120, 200),    # 0   water
    (222, 207, 140),   # 1   sand
    (96, 160, 75),     # 2   grass
    (66, 124, 58),     # 3   forest
    (128, 128, 128),   # 4   stone
    (240, 244, 248),   # 5+  snow
]


def height_color(h, max_h):
    """Map a surface height to a Minecraft-like block colour (water -> sand ->
    grass -> forest -> stone -> snow). Discrete strata read more clearly than a
    smooth gradient on blocky terrain."""
    idx = max(0, min(int(h), len(_PALETTE) - 1))
    return color.rgb32(*_PALETTE[idx])


app = Ursina()

world = World(seed=7)
sim = Simulation(world=world)

# --- terrain: one cube per column top --------------------------------------
terrain = {}
for x in range(world.width):
    for z in range(world.depth):
        h = world.surface_height(x, z)
        terrain[(x, z)] = Entity(
            model="cube",
            color=height_color(h, world.max_terrain),
            position=(x, h, z),
            scale=1,
            shader=VOXEL_SHADER,
        )

placed_entities = {}   # (x, z) -> top entity for blocks the bot stacks

# --- the bot ---------------------------------------------------------------
bx, bz = sim.body.pos
bot = Entity(model="cube", color=color.azure,
             position=(bx, world.surface_height(bx, bz) + 1, bz), scale=0.8,
             shader=VOXEL_SHADER)
bot_target = Vec3(bot.position)

# --- camera ----------------------------------------------------------------
# Colour + face shading come from VOXEL_SHADER (see top), so no scene lights are
# needed. The camera starts centred on the terrain and tilted down so the whole
# map is framed on launch.
cam = EditorCamera(rotation=(35, 0, 0))
cam.position = (world.width / 2, 2, world.depth / 2)
bot.world_parent = scene
hud = Text(text="", position=(-0.87, 0.46), scale=0.9)

_acc = 0.0
manual = False   # [M] toggles: False = brain drives, True = you drive (WASD/B)


def refresh_placed():
    """Add a cube for any newly placed block."""
    for (x, z), count in world.placed.items():
        if (x, z) not in placed_entities and count > 0:
            top = world.surface_height(x, z)
            placed_entities[(x, z)] = Entity(
                model="cube", color=color.orange,
                position=(x, top, z), scale=1, shader=VOXEL_SHADER)


# --- optional manual control ----------------------------------------------
# Press M to take the wheel. While manual, the brain no longer moves the bot --
# your key presses do. Time still passes, so needs keep decaying: you simply
# become the policy. Press M again to hand control back to the brain.
def _player_move(dx, dz):
    x, z = sim.body.pos
    nx, nz = x + dx, z + dz
    if world.is_walkable(nx, nz):
        sim.body.pos = (nx, nz)
        if world.mark_visited(nx, nz):
            sim.body.needs.replenish("novelty", 0.06)   # new ground feeds novelty


def _player_build():
    x, z = sim.body.pos
    world.place_block(x, z)                    # stack a block under the bot
    sim.body.needs.replenish("creation", 0.45)
    refresh_placed()


def input(key):
    global manual
    if key == "m":
        manual = not manual
        return
    if not manual:
        return
    if key in ("w", "up arrow"):
        _player_move(0, 1)
    elif key in ("s", "down arrow"):
        _player_move(0, -1)
    elif key in ("a", "left arrow"):
        _player_move(-1, 0)
    elif key in ("d", "right arrow"):
        _player_move(1, 0)
    elif key == "b":
        _player_build()


def update():
    global _acc, bot_target
    _acc += utime.dt
    if _acc >= TICK_INTERVAL:
        _acc = 0.0
        if manual:
            # you drive: keep time flowing (needs decay) but let the brain rest
            sim.body.tick_count += 1
            sim.body.needs.tick()
        else:
            sim.step()
        x, z = sim.body.pos
        bot_target = Vec3(x, world.surface_height(x, z) + 1, z)
        refresh_placed()
        n = sim.body.needs.levels()
        it = sim.body.current_intent
        mode = "MANUAL - you drive" if manual else "AUTO - brain drives"
        hud.text = (f"tick {sim.body.tick_count}   decisions {sim.body.brain_decisions}   mode: {mode}\n"
                    f"intent: {it}\n"
                    f"novelty {n['novelty']:.2f}  creation {n['creation']:.2f}  "
                    f"rest {n['rest']:.2f}\n"
                    f"[M] manual on/off    [WASD] move    [B] build")

    # glide toward the current cell (frontend interpolation)
    bot.position = lerp(bot.position, bot_target, min(1, GLIDE_SPEED * utime.dt))


app.run()
