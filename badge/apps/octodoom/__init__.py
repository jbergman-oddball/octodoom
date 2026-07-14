import sys
import os

sys.path.insert(0, "/system/apps/octodoom")
os.chdir("/system/apps/octodoom")

import math
import random
from badgeware import screen, PixelFont, Image, brushes, shapes, io, run, State, Matrix

# The real badge only ever has A/B/C/UP/DOWN, so io has no BUTTON_LEFT or
# BUTTON_RIGHT there and this stays None -- harmless, since `None in io.held`
# is just always False. The desktop *simulator*, though, maps the keyboard's
# arrow keys to BUTTON_LEFT/BUTTON_RIGHT, so wiring those in here as extra
# turn inputs makes testing on a keyboard (arrows to turn, space to fire)
# painless without touching how the physical badge buttons behave.
SIM_BUTTON_LEFT = getattr(io, "BUTTON_LEFT", None)
SIM_BUTTON_RIGHT = getattr(io, "BUTTON_RIGHT", None)

large_font = PixelFont.load("/system/assets/fonts/ziplock.ppf")
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")
logo = Image.load("assets/logo.png")
repo_qr = Image.load("assets/repo_qr.png")

SCREEN_W = screen.width
SCREEN_H = screen.height
HALF_H = SCREEN_H // 2

# Cast one ray every RAY_STEP columns and stretch it into a strip. On a
# 200MHz interpreted MicroPython loop, casting all 160 columns every frame
# is the single biggest cost in the engine; skipping columns is the cheapest
# way to buy back frame time without touching the (already branch-light) DDA
# inner loop.
RAY_STEP = 2
MAX_DDA_STEPS = 24  # map diagonal is ~21 cells; bounds the walk so a ray can never spin forever
FOV_PLANE = 0.66  # ~66 degree horizontal FOV
MOVE_SPEED = 2.6  # units/sec
ROT_SPEED = 2.2  # radians/sec
COLLISION_BUFFER = 0.25
DOOR_TRIGGER_DIST = 1.5
FIRE_RANGE = 9.0
FIRE_COOLDOWN_MS = 300
FIRE_CONE = 0.3  # max |transformX/transformY| considered "under the crosshair"
MAX_AMMO = 24
AMMO_REGEN_MS = 650  # passive regen instead of a dedicated reload button -- there's no button to spare
EMPTY_CLICK_FLASH_MS = 250
CROSSHAIR_Y_OFFSET = 14  # crosshair sits below the horizon; there's no vertical look to line it up otherwise
CONTACT_RANGE = 0.6
CONTACT_DAMAGE_PER_SEC = 25

ENEMY_FIRE_RANGE = 7.0
ENEMY_FIRE_RETRY_MS = 400  # how soon to re-check for a shot after being blocked/out of range
ENEMY_FIRE_COOLDOWN_MIN_MS = 1800
ENEMY_FIRE_COOLDOWN_MAX_MS = 3200
SPOT_TO_FIRE_DELAY_MS = 550  # grace window after a bug first becomes visible before it's allowed to shoot back
LOS_SAMPLE_STEP = 0.25
RUSHER_SPEED = 1.6  # units/sec -- slower than the player so it can be kited, but a real threat in tight corridors
BRUTE_SPEED = 1.0    # slower still -- the threat is its HP and hit strength, not speed
RUSHER_CHASE_RANGE = 8.0
PROJECTILE_SPEED = 3.2  # units/sec
PROJECTILE_HIT_RADIUS = 0.35
PROJECTILE_DAMAGE = 18
PROJECTILE_MAX_LIFETIME_MS = 4000
HIT_FLASH_MS = 200
MUZZLE_FLASH_MS = 70

SHAKE_DURATION_MS = 280
SHAKE_STRENGTH = 4.0  # pixels, at the moment of impact -- decays to 0 over SHAKE_DURATION_MS
SHAKE_STRENGTH_PER_DAMAGE = 0.12
MAX_SHAKE_STRENGTH = 9.0

DOOR_TYPE = 4
FRAME_TYPE = 5

# Sprites are anchored to the floor and capped well under full wall height so
# a close bug reads as "a creature standing in the hallway" instead of "a
# block filling the hallway".
ENEMY_HEIGHT_FRACTION = 0.86
ENEMY_WIDTH_FRACTION = 0.56  # narrower shoulder width -- a tall, skinny silhouette instead of a wide round one
MAX_ENEMY_HEIGHT = 90
MIN_ENEMY_HEIGHT = 12
MAX_BRUTE_HEIGHT = 105  # brutes are bigger (1.28x) but still capped well under filling the screen

PICKUP_HEIGHT_FRACTION = 0.32
MAX_PICKUP_HEIGHT = 32
MIN_PICKUP_HEIGHT = 8
PICKUP_RADIUS = 0.5
HEALTH_PICKUP_AMOUNT = 40
ARMOR_PICKUP_AMOUNT = 50
PICKUP_TOAST_MS = 1200
WAVE_BANNER_MS = 1400

# 0 = open, 1 = solid wall, 4 = closed door. Generated with a
# recursive-backtracker maze plus several carved-out multi-cell rooms (so
# rushers/brutes have room to actually close distance instead of only ever
# meeting you head-on in a 1-wide corridor). Verified fully solvable even
# with all three doors treated as solid walls; the doors are pure shortcuts.
MAP = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1],
    [1, 0, 4, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1],
    [1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 4, 1, 0, 1, 1, 1, 0, 1, 0, 1],
    [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1],
    [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 4, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]
MAP_W = len(MAP[0])
MAP_H = len(MAP)
DOOR_CELLS = [(x, y) for y in range(MAP_H) for x in range(MAP_W) if MAP[y][x] == DOOR_TYPE]


def _add_wall_variety(grid):
    # Purely cosmetic: recolor solid cells with a deterministic 3-color mix
    # (see WALL_COLORS) so the maze doesn't render as one flat mass. Leaves
    # 0 (open) and 4 (door) untouched, so collision/door logic never sees it.
    for y in range(len(grid)):
        for x in range(len(grid[0])):
            if grid[y][x] == 1:
                grid[y][x] = 1 + ((x * 5 + y * 3) % 3)
    return grid


MAP = _add_wall_variety(MAP)


def _add_door_frames(grid, doors):
    # Also purely cosmetic: the wall cells flanking a door get their own
    # gunmetal "frame" color so a doorway reads as a built portal instead of
    # just one oddly-colored cell in a wall of uniform color.
    h, w = len(grid), len(grid[0])
    for dx, dy in doors:
        for nx, ny in ((dx + 1, dy), (dx - 1, dy), (dx, dy + 1), (dx, dy - 1)):
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] in (1, 2, 3):
                grid[ny][nx] = FRAME_TYPE
    return grid


MAP = _add_door_frames(MAP, DOOR_CELLS)

# (x, y, type). Ordered so early waves only draw from the front of the list
# (see spawn_wave): shooters first (posted in corridors/room edges with a
# sightline), then rushers (seeded in the open rooms they need to close
# distance across), then brutes reserved for late waves.
ENEMY_SPAWNS = [
    (12, 1, "shooter"),
    (23, 9, "shooter"),
    (6, 17, "shooter"),
    (20, 4, "shooter"),
    (5, 3, "shooter"),
    (9, 3, "shooter"),
    (15, 3, "shooter"),
    (13, 12, "shooter"),
    (12, 5, "rusher"),
    (5, 12, "rusher"),
    (13, 14, "rusher"),
    (4, 4, "rusher"),
    (17, 17, "rusher"),
    (20, 3, "rusher"),
    (19, 12, "brute"),
    (21, 13, "brute"),
    (6, 11, "brute"),
    (9, 13, "brute"),
]

# (kind, x, y), spread across the rooms so relief is never more than a room
# or two away -- one health pack sits right off the start room since losing
# a big chunk of health to the first bug or two shouldn't mean limping the
# whole rest of the map.
PICKUP_SPAWNS = [
    ("health", 3, 3),
    ("armor", 22, 2),
    ("health", 3, 13),
    ("armor", 15, 14),
    ("health", 20, 15),
    ("armor", 9, 6),
    ("health", 18, 9),
    ("armor", 6, 10),
]

# A standing objective, not just an endless grind -- sits deep in the SE
# arena room (the toughest part of the map) so reaching it means fighting
# through the brutes stationed there. Reachable any time; you can also just
# keep clearing waves for score if you'd rather not head for it yet. Touching
# it doesn't end the run outright -- it bumps the level and throws a tougher
# fresh wave at you back at the start, so running straight for it early
# doesn't just cut a fight short. Only the MAX_LEVEL-th touch is the real win.
EXIT_POS = (21.5, 14.5)
EXIT_TRIGGER_DIST = 0.6
EXIT_BONUS_SCORE = 200
MAX_LEVEL = 5

WALL_COLORS = {
    1: (90, 90, 112),    # slate
    2: (35, 112, 60),    # github green
    3: (150, 65, 40),    # octocat orange
    4: (120, 96, 38),    # door panel (base -- the glowing center seam is added in wall_shade)
    5: (48, 52, 62),     # gunmetal door frame
}
DOOR_GLOW_COLOR = (255, 210, 90)
PANEL_SEAM_SHADE = 0.55  # darkens the mortar/seam line at each cell edge
GRID_LINE_COLOR = (90, 210, 200, 60)
GRID_LINE_DISTANCES = (1.2, 2.0, 3.2, 5.0, 7.5, 11.0)  # world-unit depths for the tron-style floor/ceiling lines
CEILING_COLOR = (16, 18, 26)
CEILING_HORIZON = (52, 56, 76)
FLOOR_HORIZON = (56, 48, 38)
FLOOR_COLOR = (26, 22, 18)
BAND_COUNT = 6
ENEMY_COLOR = (110, 45, 34)  # imp-brown, not a pink blob
ENEMY_HIT_COLOR = (255, 210, 110)
EYE_GLOW_COLOR = (255, 185, 40)
HORN_COLOR = (32, 28, 26)
PUPIL_COLOR = (15, 15, 15)
RUSHER_COLOR = (48, 82, 44)      # dark hunter-green, distinct silhouette from the shooters
RUSHER_EYE_COLOR = (255, 55, 45)  # angry red eyes -- reads as "this one's coming for you"
BRUTE_COLOR = (75, 68, 78)        # stony grey-purple -- a bullet sponge, reads heavier/tougher
BRUTE_EYE_COLOR = (150, 220, 255)  # cold pale-blue eyes, distinct from the warm shooter/rusher palette
PROJECTILE_COLOR = (80, 230, 255)
GUN_COLOR = (40, 40, 48)
GUN_ACCENT = (90, 200, 255)
MUZZLE_FLASH_COLOR = (255, 245, 180)
HEALTH_COLOR = (200, 40, 40)
HEALTH_CROSS_COLOR = (255, 255, 255)
ARMOR_COLOR = (70, 120, 190)
ARMOR_ACCENT = (180, 215, 255)
BELLY_SHADE = 0.75  # darkens the lower half of a bug's body for a hint of volume
EXIT_RING_COLOR = (255, 200, 90)  # warm amber ground-glow -- also used as the minimap blip color


def _lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


CEILING_BANDS = [_lerp_color(CEILING_COLOR, CEILING_HORIZON, i / (BAND_COUNT - 1)) for i in range(BAND_COUNT)]
FLOOR_BANDS = [_lerp_color(FLOOR_HORIZON, FLOOR_COLOR, i / (BAND_COUNT - 1)) for i in range(BAND_COUNT)]


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3
    WON = 4
    SHARE = 5


ENEMY_MAX_HP = {"shooter": 1, "rusher": 1, "brute": 2}
CONTACT_DAMAGE_MULT = {"shooter": 1.0, "rusher": 1.0, "brute": 1.8}


class Bug:
    """A target the player has to shoot down. "shooter" bugs hold position
    and fire back once they've had time to notice you; "rusher" bugs have no
    gun and instead close distance to maul you in melee; "brute" bugs are a
    slow, tougher rusher that takes two hits to put down and hits harder."""

    def __init__(self, x, y, enemy_type="shooter"):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type
        self.hp = ENEMY_MAX_HP.get(enemy_type, 1)
        self.alive = True
        self.flash_until = 0
        self.spotted_at = 0  # set the first time it's actually drawn on screen
        self.next_shot_at = io.ticks + random.randint(900, 2600)

    def hit(self, now):
        """Returns True if this hit killed it, False if it's wounded but standing."""
        self.hp -= 1
        self.flash_until = now + 150
        if self.hp <= 0:
            self.alive = False
            return True
        return False


class Projectile:
    def __init__(self, x, y, vx, vy, now):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.spawned_at = now


class Pickup:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.x = x
        self.y = y
        self.taken = False


state = GameState.INTRO
posX = posY = angle = 0.0
dirX = dirY = planeX = planeY = 0.0
health = 100
armor = 0
score = 0
wave = 1
level = 1
banner_text = ""
fire_ready_at = 0
enemies = []
projectiles = []
pickups = []
hit_flash_until = 0
muzzle_flash_until = 0
pickup_toast = ""
pickup_toast_until = 0
moving = False
zbuffer = [1e30] * SCREEN_W
high_score = 0
shake_until = 0
shake_strength = 0.0
shake_x = 0.0
shake_y = 0.0
wave_banner_until = 0
ammo = MAX_AMMO
next_regen_at = 0
empty_click_until = 0


def set_facing(new_angle):
    global angle, dirX, dirY, planeX, planeY
    angle = new_angle
    dirX = math.cos(angle)
    dirY = math.sin(angle)
    # Plane is always perpendicular to the view direction, scaled for FOV.
    planeX = -dirY * FOV_PLANE
    planeY = dirX * FOV_PLANE


def is_solid(x, y):
    mx = int(x)
    my = int(y)
    if mx < 0 or mx >= MAP_W or my < 0 or my >= MAP_H:
        return True
    return MAP[my][mx] != 0


def apply_damage(amount):
    """Armor absorbs damage before health does, Quake-style."""
    global health, armor, shake_until, shake_strength
    if armor > 0:
        absorbed = min(armor, amount)
        armor -= absorbed
        amount -= absorbed
    health -= amount

    shake_until = io.ticks + SHAKE_DURATION_MS
    shake_strength = min(MAX_SHAKE_STRENGTH, SHAKE_STRENGTH + amount * SHAKE_STRENGTH_PER_DAMAGE)


def update_shake():
    global shake_x, shake_y
    if io.ticks >= shake_until:
        shake_x = shake_y = 0.0
        return
    falloff = (shake_until - io.ticks) / SHAKE_DURATION_MS
    mag = shake_strength * falloff
    shake_x = random.uniform(-mag, mag)
    shake_y = random.uniform(-mag, mag) * 0.6


def has_los(x0, y0, x1, y1):
    """Cheap sampled line-of-sight check, only called a couple of times a
    second per enemy (when its shot timer elapses), so the O(distance) walk
    never shows up as a per-frame cost."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1e-6:
        return True
    steps = int(dist / LOS_SAMPLE_STEP) + 1
    step_x = dx / steps
    step_y = dy / steps
    x, y = x0, y0
    for _ in range(steps):
        x += step_x
        y += step_y
        if is_solid(x, y):
            return False
    return True


def spawn_wave():
    global enemies
    # A random sample instead of always the same fixed prefix of the list --
    # taking ENEMY_SPAWNS[:count] gave the exact same enemies in the exact
    # same spots every single time (and since shooters are listed first, it
    # meant every early wave was only ever the same few shooters lined up
    # along the same stretch of corridor). Sampling spreads both position
    # and enemy-type mix across the whole map on every spawn.
    count = min(len(ENEMY_SPAWNS), 6 + wave)
    picks = random.sample(ENEMY_SPAWNS, count)
    enemies = [Bug(gx + 0.5, gy + 0.5, etype) for gx, gy, etype in picks]


def reset_game():
    global posX, posY, health, armor, score, wave, level, banner_text, fire_ready_at, projectiles, pickups, hit_flash_until
    global ammo, next_regen_at, empty_click_until
    posX, posY = 1.5, 1.5
    set_facing(math.pi / 2)  # faces down the long corridor, not nose-first into the wall 0.5 units east
    health = 100
    armor = 0
    score = 0
    wave = 1
    level = 1
    banner_text = ""
    fire_ready_at = 0
    projectiles = []
    pickups = [Pickup(kind, gx + 0.5, gy + 0.5) for kind, gx, gy in PICKUP_SPAWNS]
    hit_flash_until = 0
    ammo = MAX_AMMO
    next_regen_at = 0
    empty_click_until = 0
    for gx, gy in DOOR_CELLS:
        MAP[gy][gx] = DOOR_TYPE
    spawn_wave()


def update_doors():
    for gx, gy in DOOR_CELLS:
        dist_sq = (posX - (gx + 0.5)) ** 2 + (posY - (gy + 0.5)) ** 2
        if dist_sq < DOOR_TRIGGER_DIST * DOOR_TRIGGER_DIST:
            MAP[gy][gx] = 0
        else:
            MAP[gy][gx] = DOOR_TYPE


def try_move(step_x, step_y):
    """Axis-separated collision so the player slides along walls instead of
    sticking dead when moving diagonally into a corner."""
    global posX, posY
    if step_x != 0:
        buffered = posX + step_x + (COLLISION_BUFFER if step_x > 0 else -COLLISION_BUFFER)
        if not is_solid(buffered, posY):
            posX += step_x
    if step_y != 0:
        buffered = posY + step_y + (COLLISION_BUFFER if step_y > 0 else -COLLISION_BUFFER)
        if not is_solid(posX, buffered):
            posY += step_y


def wall_shade(cell, side, dist, wall_x):
    r, g, b = WALL_COLORS.get(cell, (200, 200, 200))

    if cell == DOOR_TYPE and abs(wall_x - 0.5) < 0.07:
        # A bright seam down the middle of the panel -- reads as a
        # powered-up sliding door instead of a plain colored wall.
        r, g, b = DOOR_GLOW_COLOR
    elif min(wall_x, 1.0 - wall_x) < 0.04:
        # Darken right at each cell edge so walls read as built from
        # distinct panels instead of one continuous smear of color.
        r *= PANEL_SEAM_SHADE
        g *= PANEL_SEAM_SHADE
        b *= PANEL_SEAM_SHADE

    if side == 1:
        r *= 0.7
        g *= 0.7
        b *= 0.7
    # Cheap distance fog: darken far walls, floor never drops below 40%.
    fog = 1.0 - min(dist / 12.0, 0.6)
    return brushes.color(int(r * fog), int(g * fog), int(b * fog))


SHAKE_MARGIN = 10  # bigger than MAX_SHAKE_STRENGTH so a shaken frame never exposes a blank screen edge


def draw_world():
    sx = int(shake_x)
    sy = int(shake_y)

    for i in range(BAND_COUNT):
        y0 = int(i * HALF_H / BAND_COUNT) + sy
        y1 = int((i + 1) * HALF_H / BAND_COUNT) + sy
        screen.brush = brushes.color(*CEILING_BANDS[i])
        screen.draw(shapes.rectangle(-SHAKE_MARGIN, y0, SCREEN_W + 2 * SHAKE_MARGIN, y1 - y0))

        fy0 = HALF_H + int(i * (SCREEN_H - HALF_H) / BAND_COUNT) + sy
        fy1 = HALF_H + int((i + 1) * (SCREEN_H - HALF_H) / BAND_COUNT) + sy
        screen.brush = brushes.color(*FLOOR_BANDS[i])
        screen.draw(shapes.rectangle(-SHAKE_MARGIN, fy0, SCREEN_W + 2 * SHAKE_MARGIN, fy1 - fy0))

    # Tron-style convergent grid lines at fixed depths -- cheap (one line
    # each) and the wall columns drawn below will correctly paint over
    # whichever segments are behind a closer wall.
    for d in GRID_LINE_DISTANCES:
        lh = SCREEN_H / d
        fy = int(HALF_H + lh / 2) + sy
        cy = int(HALF_H - lh / 2) + sy
        screen.brush = brushes.color(*GRID_LINE_COLOR)
        if 0 <= fy < SCREEN_H:
            screen.draw(shapes.line(-SHAKE_MARGIN, fy, SCREEN_W + SHAKE_MARGIN, fy, 1))
        if 0 <= cy < SCREEN_H:
            screen.draw(shapes.line(-SHAKE_MARGIN, cy, SCREEN_W + SHAKE_MARGIN, cy, 1))

    for x in range(0, SCREEN_W, RAY_STEP):
        camera_x = 2 * x / SCREEN_W - 1
        ray_dir_x = dirX + planeX * camera_x
        ray_dir_y = dirY + planeY * camera_x

        # Guard against the axis-aligned rays that would otherwise divide by zero below.
        if ray_dir_x == 0:
            ray_dir_x = 1e-6
        if ray_dir_y == 0:
            ray_dir_y = 1e-6

        map_x = int(posX)
        map_y = int(posY)

        delta_dist_x = abs(1.0 / ray_dir_x)
        delta_dist_y = abs(1.0 / ray_dir_y)

        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (posX - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - posX) * delta_dist_x

        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (posY - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - posY) * delta_dist_y

        hit = 0
        side = 0
        for _ in range(MAX_DDA_STEPS):
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
            if map_x < 0 or map_x >= MAP_W or map_y < 0 or map_y >= MAP_H:
                break
            cell = MAP[map_y][map_x]
            if cell != 0:
                hit = cell
                break

        if hit == 0:
            for i in range(RAY_STEP):
                if x + i < SCREEN_W:
                    zbuffer[x + i] = 1e30
            continue

        if side == 0:
            perp_dist = (map_x - posX + (1 - step_x) / 2) / ray_dir_x
        else:
            perp_dist = (map_y - posY + (1 - step_y) / 2) / ray_dir_y
        # A near-zero perp distance would blow line_height up towards
        # infinity (and did, before this clamp, produce a ZeroDivisionError
        # right at a wall corner) so floor it to a small epsilon.
        if perp_dist < 0.05:
            perp_dist = 0.05

        for i in range(RAY_STEP):
            if x + i < SCREEN_W:
                zbuffer[x + i] = perp_dist

        # Where along the cell's face this ray landed (0..1), used to fake a
        # panel-seam/door-glow texture without ever loading a texture bitmap.
        if side == 0:
            wall_x = posY + perp_dist * ray_dir_y
        else:
            wall_x = posX + perp_dist * ray_dir_x
        wall_x -= math.floor(wall_x)

        line_height = int(SCREEN_H / perp_dist)
        draw_start = max(0, -line_height // 2 + HALF_H) + sy
        draw_end = min(SCREEN_H - 1, line_height // 2 + HALF_H) + sy

        screen.brush = wall_shade(hit, side, perp_dist, wall_x)
        screen.draw(shapes.rectangle(x + sx, draw_start, RAY_STEP, draw_end - draw_start + 1))

    draw_exit()
    draw_pickups()
    draw_enemies()
    draw_projectiles()


def _project(world_x, world_y):
    """Billboard-project a world point into (transform_y depth, screen_x)."""
    det = planeX * dirY - dirX * planeY
    if det == 0:
        return None
    inv_det = 1.0 / det
    sx = world_x - posX
    sy = world_y - posY
    transform_y = inv_det * (-planeY * sx + planeX * sy)
    if transform_y <= 0.1:
        return None
    transform_x = inv_det * (dirY * sx - dirX * sy)
    screen_x = int((SCREEN_W / 2) * (1 + transform_x / transform_y))
    return transform_y, screen_x


def _floor_anchored_size(transform_y, height_fraction, min_height, max_height):
    """Scale + position a billboard so its *feet* sit on the floor line at
    this depth (same floor_y a wall at this distance would have), instead of
    centering it on the horizon. That's what makes a close-up sprite read as
    a creature standing in the hallway instead of a slab filling it end to
    end."""
    line_height = SCREEN_H / transform_y
    floor_y = HALF_H + line_height / 2
    height = max(min_height, min(max_height, int(line_height * height_fraction)))
    top = int(floor_y) - height
    return top, height


def draw_enemies():
    visible = []
    for bug in enemies:
        if not bug.alive and io.ticks >= bug.flash_until:
            continue  # fully gone once its death flash has faded
        projected = _project(bug.x, bug.y)
        if projected is None:
            continue
        transform_y, screen_x = projected
        visible.append((transform_y, screen_x, bug))

    visible.sort(key=lambda v: -v[0])  # farthest first so nearer bugs draw on top

    for transform_y, screen_x, bug in visible:
        if screen_x < -20 or screen_x > SCREEN_W + 20:
            continue  # fully off-screen
        clamped_col = max(0, min(SCREEN_W - 1, screen_x))
        if transform_y >= zbuffer[clamped_col]:
            continue  # a wall is in front of it (coarse, center-column-only occlusion)

        # A bug counts as "spotted" the first time it actually gets drawn
        # (i.e. visible and unoccluded) -- enemy_ai() won't let it shoot
        # until a beat after that, so you get a moment to react instead of
        # taking a hit from something you never had a chance to see.
        if bug.spotted_at == 0:
            bug.spotted_at = io.ticks

        screen_x += int(shake_x)  # occlusion check above already used the un-shaken column

        size_mult = 1.28 if bug.enemy_type == "brute" else 1.0
        top, height = _floor_anchored_size(transform_y, ENEMY_HEIGHT_FRACTION, MIN_ENEMY_HEIGHT, MAX_ENEMY_HEIGHT)
        height = min(MAX_BRUTE_HEIGHT, int(height * size_mult))
        width = int(height * ENEMY_WIDTH_FRACTION)  # shoulder width -- the waist below tapers narrower
        waist_w = max(2, int(width * 0.5))
        bob = int(math.sin(io.ticks / 220.0 + bug.x * 3.0) * max(1, height // 20))
        top += bob + int(shake_y)
        radius = max(2, width // 4)

        recently_hit = io.ticks < bug.flash_until
        dying = not bug.alive and recently_hit  # wounded-but-alive also flashes, just doesn't burst/vanish
        if bug.enemy_type == "rusher":
            base_color, eye_color = RUSHER_COLOR, RUSHER_EYE_COLOR
        elif bug.enemy_type == "brute":
            base_color, eye_color = BRUTE_COLOR, BRUTE_EYE_COLOR
        else:
            base_color, eye_color = ENEMY_COLOR, EYE_GLOW_COLOR
        body_color = ENEMY_HIT_COLOR if recently_hit else base_color

        # Head sits above the torso so the silhouette reads as a creature
        # (head + horns + shoulders) instead of one blob filling the frame.
        head_r = max(2, int(width * 0.27))
        head_cy = top + head_r + 1
        torso_top = head_cy + int(head_r * 0.7)
        torso_h = max(2, top + height - torso_top)

        # Tapered torso -- wider shoulders narrowing to a waist. This is most
        # of what actually kills the "owl" read: a straight-sided rectangle
        # reads as a round bird body no matter what's drawn on the head.
        shoulder_h = max(1, int(torso_h * 0.3))
        waist_h = torso_h - shoulder_h
        screen.brush = brushes.color(*body_color)
        screen.draw(shapes.rectangle(screen_x - width // 2, torso_top, width, shoulder_h, radius))
        screen.draw(shapes.rectangle(screen_x - waist_w // 2, torso_top + shoulder_h, waist_w, waist_h, radius))
        screen.draw(shapes.squircle(screen_x, head_cy, head_r, 5))  # squarer than a circle -- less "owl", more "skull"

        if not dying:
            # A darker "belly" band on the lower half of the waist reads as
            # a hint of volume instead of a flat slab of color.
            belly_h = waist_h // 2
            screen.brush = brushes.color(*(int(c * BELLY_SHADE) for c in body_color))
            screen.draw(shapes.rectangle(screen_x - waist_w // 2, top + height - belly_h, waist_w, belly_h, radius))

        # legs planted on the floor line -- reinforces "standing here", not "floating block"
        leg_h = max(2, height // 4)
        leg_w = max(2, waist_w // 5)
        screen.brush = brushes.color(*(int(c * BELLY_SHADE) for c in body_color))
        screen.draw(shapes.rectangle(screen_x - waist_w // 3, top + height - leg_h, leg_w, leg_h))
        screen.draw(shapes.rectangle(screen_x + waist_w // 3 - leg_w, top + height - leg_h, leg_w, leg_h))

        if dying:
            # A quick 6-spoke burst instead of the face -- a satisfying
            # "pop" for the ~150ms the flash color is up.
            burst_r = width // 2 + 5
            cy = top + height // 2
            screen.brush = brushes.color(255, 255, 255, 210)
            for spoke in range(6):
                rad = math.radians(spoke * 60 + (io.ticks % 360))
                ex = screen_x + int(math.cos(rad) * burst_r)
                ey = cy + int(math.sin(rad) * burst_r)
                screen.draw(shapes.line(screen_x, cy, ex, ey, 2))
            continue  # skip the face on the death flash; reads better as a plain flash

        # Horns: the same unit triangle used for the shield, flipped upright
        # (negative y-scale) and planted either side of the head.
        horn_w = max(1, head_r * 0.4)
        horn_h = max(2, head_r * 0.9)
        for side in (-1, 1):
            hx = screen_x + side * head_r * 0.55
            hy = head_cy - head_r * 0.5
            _UNIT_TRIANGLE.transform = Matrix().translate(hx, hy).scale(horn_w, -horn_h)
            screen.brush = brushes.color(*HORN_COLOR)
            screen.draw(_UNIT_TRIANGLE)

        eye_r = max(1, int(head_r * 0.38))
        eye_dx = head_r * 0.45

        # Angry inward-down brows are what actually kill the "owl" read --
        # owls don't scowl. Drawn before the eyes so the eyes sit on top.
        brow_w = max(1, int(head_r * 0.24))
        brow_len = head_r * 0.5
        brow_y = head_cy - eye_r * 1.05  # sits right on top of the eye, well clear of the horns above it
        screen.brush = brushes.color(*HORN_COLOR)
        for side in (-1, 1):
            bx = screen_x + side * eye_dx
            screen.draw(shapes.line(
                bx + side * brow_len * 0.5, brow_y - brow_len * 0.2,
                bx - side * brow_len * 0.4, brow_y + brow_len * 0.4,
                brow_w,
            ))

        for ex in (screen_x - eye_dx, screen_x + eye_dx):
            screen.brush = brushes.color(*eye_color)
            screen.draw(shapes.circle(int(ex), head_cy, eye_r))
            screen.brush = brushes.color(*PUPIL_COLOR)
            screen.draw(shapes.circle(int(ex), head_cy, max(1, eye_r // 2)))

        # Snarling mouth with a couple of fangs -- reads as a predator, not a beak.
        mouth_y = head_cy + int(head_r * 0.5)
        mouth_w = head_r * 1.0
        mouth_h = max(1, int(head_r * 0.26))
        screen.brush = brushes.color(*HORN_COLOR)
        screen.draw(shapes.rectangle(screen_x - mouth_w / 2, mouth_y, mouth_w, mouth_h, mouth_h / 2))
        fang_w = max(1, head_r * 0.22)
        fang_h = max(2, head_r * 0.4)
        screen.brush = brushes.color(225, 220, 205)
        for side in (-1, 1):
            fx = screen_x + side * mouth_w * 0.26
            _UNIT_TRIANGLE.transform = Matrix().translate(fx, mouth_y + mouth_h * 0.3).scale(fang_w, fang_h)
            screen.draw(_UNIT_TRIANGLE)


_UNIT_TRIANGLE = shapes.regular_polygon(0, 0, 1.0, 3)  # flat edge at y=-0.5, apex at y=+1.0 -- built once, reshaped per draw via transform


def draw_shield(cx, top, size, body_color, accent_color):
    """A heater-shield silhouette: rounded top corners, square bottom
    corners, capped with a triangle scaled independently in x/y so its
    point depth doesn't have to match its width (a plain equilateral
    triangle can't do both at once)."""
    width = size
    body_h = max(2, int(size * 0.62))
    point_h = size - body_h
    corner_r = max(1, size // 5)
    left = cx - width // 2

    screen.brush = brushes.color(*body_color)
    screen.draw(shapes.rounded_rectangle(left, top, width, body_h, corner_r, corner_r, corner_r, 0, 0))

    sx = width / (2 * 0.866025)
    sy = point_h / 1.5
    join_y = top + body_h
    _UNIT_TRIANGLE.transform = Matrix().translate(cx, join_y + 0.5 * sy).scale(sx, sy)
    screen.draw(_UNIT_TRIANGLE)

    screen.brush = brushes.color(*accent_color)
    band_h = max(1, size // 7)
    screen.draw(shapes.rectangle(left + width // 6, top + size // 6, width - 2 * (width // 6), band_h))


def draw_pickups():
    visible = []
    for pickup in pickups:
        if pickup.taken:
            continue
        projected = _project(pickup.x, pickup.y)
        if projected is None:
            continue
        transform_y, screen_x = projected
        visible.append((transform_y, screen_x, pickup))

    visible.sort(key=lambda v: -v[0])

    for transform_y, screen_x, pickup in visible:
        if screen_x < -10 or screen_x > SCREEN_W + 10:
            continue
        clamped_col = max(0, min(SCREEN_W - 1, screen_x))
        if transform_y >= zbuffer[clamped_col]:
            continue

        screen_x += int(shake_x)  # occlusion check above already used the un-shaken column

        top, size = _floor_anchored_size(transform_y, PICKUP_HEIGHT_FRACTION, MIN_PICKUP_HEIGHT, MAX_PICKUP_HEIGHT)
        # Gentle bob + pulse so pickups read as "alive" items, not scenery.
        top += int(math.sin(io.ticks / 260.0 + pickup.x * 5.0) * max(1, size // 8)) + int(shake_y)
        left = screen_x - size // 2

        if pickup.kind == "health":
            screen.brush = brushes.color(*HEALTH_COLOR)
            screen.draw(shapes.rectangle(left, top, size, size, size // 4))
            screen.brush = brushes.color(*HEALTH_CROSS_COLOR)
            bar = max(1, size // 5)
            screen.draw(shapes.rectangle(screen_x - bar // 2, top + size // 5, bar, size - 2 * (size // 5)))
            screen.draw(shapes.rectangle(left + size // 5, top + size // 2 - bar // 2, size - 2 * (size // 5), bar))
        else:
            draw_shield(screen_x, top, size, ARMOR_COLOR, ARMOR_ACCENT)


def draw_projectiles():
    for p in projectiles:
        projected = _project(p.x, p.y)
        if projected is None:
            continue
        transform_y, screen_x = projected
        if screen_x < 0 or screen_x >= SCREEN_W:
            continue
        if transform_y >= zbuffer[screen_x]:
            continue
        radius = max(2, min(9, int(SCREEN_H / transform_y / 6)))
        screen.brush = brushes.color(*PROJECTILE_COLOR)
        screen.draw(shapes.circle(screen_x + int(shake_x), HALF_H + int(shake_y), radius))


def draw_exit():
    projected = _project(*EXIT_POS)
    if projected is None:
        return
    transform_y, screen_x = projected
    clamped_col = max(0, min(SCREEN_W - 1, screen_x))
    if screen_x < -12 or screen_x > SCREEN_W + 12 or transform_y >= zbuffer[clamped_col]:
        return

    # A checkered flag mounted flat on the wall, like a sign bolted up --
    # not a free-standing pole with a glowing ball at its base (which read as
    # exactly that: a ball on a stick, and got mistaken for a projectile).
    # Sized the same way a wall panel would be at this distance so it reads
    # as part of the wall, not a floating sprite.
    line_height = SCREEN_H / transform_y
    panel = max(6, min(64, int(line_height * 0.42)))
    cx = screen_x + int(shake_x)
    cy = HALF_H + int(shake_y)

    cols, rows = 4, 4
    cw = max(1, panel // cols)
    ch = max(1, panel // rows)
    left = cx - (cw * cols) // 2
    top = cy - (ch * rows) // 2

    frame_pad = max(1, panel // 16)
    screen.brush = brushes.color(60, 50, 34)
    screen.draw(shapes.rectangle(left - frame_pad, top - frame_pad, cw * cols + frame_pad * 2, ch * rows + frame_pad * 2, 2))

    for r in range(rows):
        for c in range(cols):
            dark = (r + c) % 2 == 0
            screen.brush = brushes.color(20, 20, 24) if dark else brushes.color(235, 235, 235)
            screen.draw(shapes.rectangle(left + c * cw, top + r * ch, cw, ch))


def update_ammo():
    global ammo, next_regen_at
    if ammo >= MAX_AMMO:
        next_regen_at = io.ticks + AMMO_REGEN_MS
        return
    if io.ticks >= next_regen_at:
        ammo += 1
        next_regen_at = io.ticks + AMMO_REGEN_MS


def fire_weapon():
    global fire_ready_at, score, muzzle_flash_until, ammo, empty_click_until
    now = io.ticks
    if now < fire_ready_at:
        return
    fire_ready_at = now + FIRE_COOLDOWN_MS

    if ammo <= 0:
        empty_click_until = now + EMPTY_CLICK_FLASH_MS
        return
    ammo -= 1
    muzzle_flash_until = now + MUZZLE_FLASH_MS

    det = planeX * dirY - dirX * planeY
    if det == 0:
        return
    inv_det = 1.0 / det

    best_dist = FIRE_RANGE
    best_bug = None
    center_col = SCREEN_W // 2
    for bug in enemies:
        if not bug.alive:
            continue
        sx = bug.x - posX
        sy = bug.y - posY
        transform_y = inv_det * (-planeY * sx + planeX * sy)
        if transform_y <= 0.1 or transform_y >= best_dist:
            continue
        transform_x = inv_det * (dirY * sx - dirX * sy)
        if abs(transform_x / transform_y) > FIRE_CONE:
            continue
        if transform_y >= zbuffer[center_col]:
            continue  # a wall is in the way
        best_dist = transform_y
        best_bug = bug

    if best_bug is not None:
        best_bug.hit(now)
        score += 10


def enemy_ai():
    now = io.ticks
    for bug in enemies:
        if bug.enemy_type != "shooter" or not bug.alive or now < bug.next_shot_at:
            continue
        # Give the player a beat to notice a bug before it can shoot back --
        # the grace window starts the first time it's actually been drawn on
        # screen (see draw_enemies), a one-time thing per bug so peeking
        # around a corner repeatedly can't be used to keep it disarmed.
        if bug.spotted_at == 0 or now - bug.spotted_at < SPOT_TO_FIRE_DELAY_MS:
            bug.next_shot_at = now + ENEMY_FIRE_RETRY_MS
            continue
        dx = posX - bug.x
        dy = posY - bug.y
        dist_sq = dx * dx + dy * dy
        if dist_sq > ENEMY_FIRE_RANGE * ENEMY_FIRE_RANGE or not has_los(bug.x, bug.y, posX, posY):
            bug.next_shot_at = now + ENEMY_FIRE_RETRY_MS
            continue
        dist = math.sqrt(dist_sq)
        vx = dx / dist * PROJECTILE_SPEED
        vy = dy / dist * PROJECTILE_SPEED
        projectiles.append(Projectile(bug.x, bug.y, vx, vy, now))
        bug.next_shot_at = now + random.randint(ENEMY_FIRE_COOLDOWN_MIN_MS, ENEMY_FIRE_COOLDOWN_MAX_MS)


MELEE_SPEEDS = {"rusher": RUSHER_SPEED, "brute": BRUTE_SPEED}


def update_melee_ai(dt):
    """Moves both melee types (rushers and brutes) toward the player once
    each has been spotted and has a clear line of sight -- same fairness
    rule as the shooters' grace window."""
    for bug in enemies:
        speed = MELEE_SPEEDS.get(bug.enemy_type)
        if speed is None or not bug.alive or bug.spotted_at == 0:
            continue
        dx = posX - bug.x
        dy = posY - bug.y
        dist_sq = dx * dx + dy * dy
        if dist_sq > RUSHER_CHASE_RANGE * RUSHER_CHASE_RANGE or dist_sq < 0.01:
            continue
        if not has_los(bug.x, bug.y, posX, posY):
            continue
        dist = math.sqrt(dist_sq)
        step = speed * dt
        step_x = dx / dist * step
        step_y = dy / dist * step
        # Axis-separated collision, same trick as the player's try_move, so
        # it slides along a wall instead of getting stuck at a corner.
        if not is_solid(bug.x + step_x, bug.y):
            bug.x += step_x
        if not is_solid(bug.x, bug.y + step_y):
            bug.y += step_y


def update_projectiles(dt):
    global hit_flash_until
    now = io.ticks
    for p in projectiles[:]:
        p.x += p.vx * dt
        p.y += p.vy * dt
        if now - p.spawned_at > PROJECTILE_MAX_LIFETIME_MS:
            projectiles.remove(p)
            continue
        if is_solid(p.x, p.y):
            projectiles.remove(p)
            continue
        dist_sq = (p.x - posX) ** 2 + (p.y - posY) ** 2
        if dist_sq < PROJECTILE_HIT_RADIUS * PROJECTILE_HIT_RADIUS:
            apply_damage(PROJECTILE_DAMAGE)
            hit_flash_until = now + HIT_FLASH_MS
            projectiles.remove(p)


def collect_pickups():
    global health, armor, pickup_toast, pickup_toast_until
    for pickup in pickups:
        if pickup.taken:
            continue
        dist_sq = (posX - pickup.x) ** 2 + (posY - pickup.y) ** 2
        if dist_sq >= PICKUP_RADIUS * PICKUP_RADIUS:
            continue
        pickup.taken = True
        if pickup.kind == "health":
            health = min(100, health + HEALTH_PICKUP_AMOUNT)
            pickup_toast = f"+{HEALTH_PICKUP_AMOUNT} HEALTH"
        else:
            armor = min(100, armor + ARMOR_PICKUP_AMOUNT)
            pickup_toast = f"+{ARMOR_PICKUP_AMOUNT} ARMOR"
        pickup_toast_until = io.ticks + PICKUP_TOAST_MS


def draw_gun():
    # Tucked mostly below the bottom edge -- just enough peeking up to read
    # as "you're holding a gun" without dominating the view like before.
    bob = math.sin(io.ticks / 120.0) * 1.5 if moving else 0
    gx = SCREEN_W // 2
    gy = SCREEN_H + 6 + bob
    screen.brush = brushes.color(*GUN_COLOR)
    screen.draw(shapes.rectangle(gx - 10, gy - 15, 20, 17, 4))
    screen.draw(shapes.rectangle(gx - 4, gy - 23, 8, 10, 2))

    empty_flash = io.ticks < empty_click_until
    screen.brush = brushes.color(220, 50, 40) if empty_flash else brushes.color(*GUN_ACCENT)
    screen.draw(shapes.rectangle(gx - 3, gy - 21, 6, 3))

    if io.ticks < muzzle_flash_until:
        screen.brush = brushes.color(*MUZZLE_FLASH_COLOR)
        screen.draw(shapes.circle(gx, gy - 23, 5))
        screen.brush = brushes.color(255, 255, 255)
        screen.draw(shapes.circle(gx, gy - 23, 2))

    # Ammo printed right on the gun body itself -- just the number, no
    # "/max" and no separate off-to-the-side readout eating screen space.
    ammo_text = str(ammo)
    tw, _ = screen.measure_text(ammo_text)
    screen.brush = brushes.color(255, 255, 255) if empty_flash else (
        brushes.color(220, 60, 50) if ammo <= 5 else brushes.color(230, 230, 230)
    )
    screen.text(ammo_text, gx - tw / 2, gy - 17)


MINIMAP_RADIUS = 3  # cells shown each direction -- a fixed window keeps the draw count bounded regardless of maze size
MINIMAP_CELL = 3
MINIMAP_MARGIN = 3


def draw_minimap():
    span = (MINIMAP_RADIUS * 2 + 1) * MINIMAP_CELL
    ox = SCREEN_W - span - MINIMAP_MARGIN
    oy = 14

    screen.brush = brushes.color(0, 0, 0, 130)
    screen.draw(shapes.rectangle(ox - 2, oy - 2, span + 4, span + 4, 3))

    cx = int(posX)
    cy = int(posY)
    for gy in range(cy - MINIMAP_RADIUS, cy + MINIMAP_RADIUS + 1):
        for gx in range(cx - MINIMAP_RADIUS, cx + MINIMAP_RADIUS + 1):
            cell = MAP[gy][gx] if 0 <= gx < MAP_W and 0 <= gy < MAP_H else 1
            if cell == 0:
                continue  # skip open floor -- just the backdrop shows through
            px = ox + (gx - (cx - MINIMAP_RADIUS)) * MINIMAP_CELL
            py = oy + (gy - (cy - MINIMAP_RADIUS)) * MINIMAP_CELL
            color = DOOR_GLOW_COLOR if cell == DOOR_TYPE else (150, 150, 160)
            screen.brush = brushes.color(*color)
            screen.draw(shapes.rectangle(px, py, MINIMAP_CELL, MINIMAP_CELL))

    # Enemy blips -- the minimap window is already bounded to a few cells
    # around the player, so "on the minimap at all" already means "close
    # by"; nothing shows up here until you're actually near it.
    enemy_colors = {"rusher": RUSHER_EYE_COLOR, "brute": BRUTE_EYE_COLOR}
    for bug in enemies:
        if not bug.alive:
            continue
        ex, ey = int(bug.x), int(bug.y)
        if abs(ex - cx) > MINIMAP_RADIUS or abs(ey - cy) > MINIMAP_RADIUS:
            continue
        px = ox + (ex - (cx - MINIMAP_RADIUS)) * MINIMAP_CELL + MINIMAP_CELL // 2
        py = oy + (ey - (cy - MINIMAP_RADIUS)) * MINIMAP_CELL + MINIMAP_CELL // 2
        screen.brush = brushes.color(*enemy_colors.get(bug.enemy_type, EYE_GLOW_COLOR))
        screen.draw(shapes.circle(px, py, 2))

    ex, ey = int(EXIT_POS[0]), int(EXIT_POS[1])
    if abs(ex - cx) <= MINIMAP_RADIUS and abs(ey - cy) <= MINIMAP_RADIUS:
        px = ox + (ex - (cx - MINIMAP_RADIUS)) * MINIMAP_CELL + MINIMAP_CELL // 2
        py = oy + (ey - (cy - MINIMAP_RADIUS)) * MINIMAP_CELL + MINIMAP_CELL // 2
        screen.brush = brushes.color(*EXIT_RING_COLOR)
        screen.draw(shapes.circle(px, py, 2))

    player_px = ox + MINIMAP_RADIUS * MINIMAP_CELL + MINIMAP_CELL // 2
    player_py = oy + MINIMAP_RADIUS * MINIMAP_CELL + MINIMAP_CELL // 2
    screen.brush = brushes.color(255, 255, 255)
    screen.draw(shapes.circle(player_px, player_py, 2))
    screen.draw(shapes.line(player_px, player_py, player_px + int(dirX * 5), player_py + int(dirY * 5), 1))


def draw_hud():
    screen.font = small_font

    if io.ticks < hit_flash_until:
        screen.brush = brushes.color(200, 30, 30, 90)
        screen.draw(shapes.rectangle(0, 0, SCREEN_W, SCREEN_H))

    draw_gun()
    draw_minimap()

    screen.brush = brushes.color(0, 0, 0, 140)
    screen.draw(shapes.rectangle(0, 0, SCREEN_W, 11))

    if health < 30:
        # Pulses brighter as a warning instead of sitting at one flat red --
        # contained to the HP text itself, not a full-screen effect.
        pulse = (math.sin(io.ticks / 150.0) + 1) / 2
        screen.brush = brushes.color(180 + int(75 * pulse), 40 + int(20 * pulse), 40 + int(20 * pulse))
    else:
        screen.brush = brushes.color(90, 220, 110)
    screen.text(f"HP{max(0, int(health))}", 3, 2)

    if armor > 0:
        screen.brush = brushes.color(*ARMOR_ACCENT)
        screen.text(f"AR{int(armor)}", 44, 2)

    screen.brush = brushes.color(255, 255, 255)
    screen.text(f"SC{score}", 86, 2)
    screen.text(f"L{level}", SCREEN_W - 20, 2)

    if io.ticks < pickup_toast_until:
        screen.brush = brushes.color(255, 230, 140)
        center_text(pickup_toast, HALF_H - 30)

    if io.ticks < wave_banner_until:
        screen.brush = brushes.color(255, 215, 90)
        center_text(banner_text, 46, large_font)

    # Crosshair. Drawn below screen-center: with no vertical look, the true
    # aim column (used in fire_weapon) is horizontal-only anyway, so nudging
    # this down is purely cosmetic and doesn't change what actually gets hit.
    screen.brush = brushes.color(255, 255, 255, 200)
    cx, cy = SCREEN_W // 2, HALF_H + CROSSHAIR_Y_OFFSET
    screen.draw(shapes.line(cx - 4, cy, cx + 4, cy, 1))
    screen.draw(shapes.line(cx, cy - 4, cx, cy + 4, 1))


def center_text(text, y, font=small_font):
    screen.font = font
    w, _ = screen.measure_text(text)
    screen.text(text, SCREEN_W // 2 - w // 2, y)


def update():
    if state == GameState.INTRO:
        intro()
    elif state == GameState.PLAYING:
        play()
    elif state == GameState.GAME_OVER:
        game_over()
    elif state == GameState.WON:
        won_screen()
    elif state == GameState.SHARE:
        share_screen()


LOGO_SIZE = 46
MENU_ITEMS = ("PLAY", "SHARE", "EXIT")
menu_selected = 0
exit_hint_until = 0


def intro():
    global state, menu_selected, exit_hint_until

    screen.brush = brushes.color(*CEILING_COLOR)
    screen.clear()

    screen.scale_blit(logo, SCREEN_W // 2 - LOGO_SIZE // 2, 1, LOGO_SIZE, LOGO_SIZE)

    line_h = small_font.height + 3
    y = LOGO_SIZE + 4

    screen.brush = brushes.color(150, 200, 255)
    center_text("Git Universe Edition", y)
    y += line_h + 2

    if io.BUTTON_UP in io.pressed:
        menu_selected = (menu_selected - 1) % len(MENU_ITEMS)
    if io.BUTTON_DOWN in io.pressed:
        menu_selected = (menu_selected + 1) % len(MENU_ITEMS)

    for i, label in enumerate(MENU_ITEMS):
        if i == menu_selected:
            screen.brush = brushes.color(255, 220, 100)
            center_text(f"> {label} <", y)
        else:
            screen.brush = brushes.color(165, 170, 180)
            center_text(label, y)
        y += line_h

    if high_score:
        screen.brush = brushes.color(255, 210, 100)
        center_text(f"High score: {high_score}", y)

    if io.ticks < exit_hint_until:
        screen.brush = brushes.color(255, 160, 120)
        center_text("Press HOME to exit to launcher", SCREEN_H - line_h)
    elif int(io.ticks / 500) % 2:
        screen.brush = brushes.color(255, 255, 255)
        center_text("SPACE/B to select", SCREEN_H - line_h)

    if io.BUTTON_B in io.pressed:
        choice = MENU_ITEMS[menu_selected]
        if choice == "PLAY":
            reset_game()
            state = GameState.PLAYING
        elif choice == "SHARE":
            state = GameState.SHARE
        elif choice == "EXIT":
            # Apps on this badge don't have a way to programmatically quit
            # themselves back to the launcher -- that's what the physical
            # HOME button is for. Point at the real mechanism instead of
            # faking one that might not do anything on real hardware.
            exit_hint_until = io.ticks + 2500


QR_SIZE = 80


def share_screen():
    global state

    screen.brush = brushes.color(12, 12, 16)
    screen.clear()

    screen.brush = brushes.color(220, 220, 220)
    center_text("SCAN FOR REPO", 2)

    qx = SCREEN_W // 2 - QR_SIZE // 2
    qy = 19
    screen.brush = brushes.color(255, 255, 255)
    screen.draw(shapes.rectangle(qx - 4, qy - 4, QR_SIZE + 8, QR_SIZE + 8))
    screen.scale_blit(repo_qr, qx, qy, QR_SIZE, QR_SIZE)

    if int(io.ticks / 500) % 2:
        screen.brush = brushes.color(255, 255, 255)
        center_text("SPACE/B: back", SCREEN_H - (small_font.height + 3))

    if io.BUTTON_B in io.pressed:
        state = GameState.INTRO


def play():
    global state, wave, level, moving, wave_banner_until, banner_text, score, health, armor, posX, posY

    dt = io.ticks_delta / 1000.0

    # A/C turn (flanking the fire button on B), B fires -- matches the
    # physical layout better than A/B turn + C fire: B sits in the middle of
    # the row so your thumb rests on the fire button by default and only
    # slides to a side to turn, instead of reaching to the end of the row.
    # On the desktop simulator, the arrow keys/space work as an equivalent
    # alternate scheme (see SIM_BUTTON_LEFT/RIGHT above) for easier keyboard
    # testing -- the badge itself only ever sends A/B/C/UP/DOWN.
    if io.BUTTON_A in io.held or SIM_BUTTON_LEFT in io.held:
        set_facing(angle - ROT_SPEED * dt)
    if io.BUTTON_C in io.held or SIM_BUTTON_RIGHT in io.held:
        set_facing(angle + ROT_SPEED * dt)

    move = 0.0
    if io.BUTTON_UP in io.held:
        move += MOVE_SPEED * dt
    if io.BUTTON_DOWN in io.held:
        move -= MOVE_SPEED * dt
    moving = move != 0
    if moving:
        try_move(dirX * move, dirY * move)

    update_doors()
    update_shake()
    update_ammo()

    # draw_world() must run before fire_weapon(): it's what fills the
    # z-buffer for the frame. Firing off the previous frame's z-buffer meant
    # a shot taken right after turning to face a target checked wall
    # distances from the angle you were *previously* looking at, and could
    # spuriously say "a wall is in the way" for a target now in the clear.
    draw_world()

    if io.BUTTON_B in io.pressed:
        fire_weapon()

    enemy_ai()
    update_melee_ai(dt)
    update_projectiles(dt)
    collect_pickups()

    contact_mult = 0.0
    for bug in enemies:
        if bug.alive:
            dist_sq = (posX - bug.x) ** 2 + (posY - bug.y) ** 2
            if dist_sq < CONTACT_RANGE * CONTACT_RANGE:
                contact_mult = max(contact_mult, CONTACT_DAMAGE_MULT.get(bug.enemy_type, 1.0))
    if contact_mult:
        apply_damage(CONTACT_DAMAGE_PER_SEC * contact_mult * dt)

    if all(not bug.alive for bug in enemies):
        wave += 1
        spawn_wave()
        banner_text = f"WAVE {wave}"
        wave_banner_until = io.ticks + WAVE_BANNER_MS
        # Full heal + armor refill on every new wave -- difficulty should
        # come from more/tougher enemies as waves climb, not from slowly
        # bleeding out with no way to recover once the map's limited
        # pickups are already spent.
        health = 100
        armor = 0

    draw_hud()

    if health <= 0:
        state = GameState.GAME_OVER
    elif (posX - EXIT_POS[0]) ** 2 + (posY - EXIT_POS[1]) ** 2 < EXIT_TRIGGER_DIST * EXIT_TRIGGER_DIST:
        score += EXIT_BONUS_SCORE
        if level >= MAX_LEVEL:
            state = GameState.WON
        else:
            # Not the end -- send the player back to the start with a
            # tougher wave waiting, so touching the flag is a progression
            # beat instead of a one-and-done "walked over, game ends" fizzle.
            level += 1
            wave += 2
            posX, posY = 1.5, 1.5
            set_facing(math.pi / 2)
            health = 100
            armor = 0
            projectiles.clear()
            pickups[:] = [Pickup(kind, gx + 0.5, gy + 0.5) for kind, gx, gy in PICKUP_SPAWNS]
            spawn_wave()
            banner_text = f"LEVEL {level} / {MAX_LEVEL}"
            wave_banner_until = io.ticks + WAVE_BANNER_MS


def game_over():
    global state, high_score

    screen.brush = brushes.color(10, 10, 12)
    screen.clear()

    screen.brush = brushes.color(220, 60, 60)
    center_text("GAME OVER", 30, large_font)

    is_new_high = score > high_score
    if is_new_high:
        high_score = score
        try:
            State.save("octodoom", {"high_score": high_score})
        except Exception:
            pass

    screen.brush = brushes.color(220, 220, 220)
    center_text(f"Score: {score}", 55)
    center_text(f"Level {level}/{MAX_LEVEL}  |  Wave {wave}", 66)
    if is_new_high:
        screen.brush = brushes.color(255, 210, 100)
        center_text("New high score!", 78)

    if int(io.ticks / 500) % 2:
        screen.brush = brushes.color(255, 255, 255)
        center_text("SPACE/B to continue", 100)

    if io.BUTTON_B in io.pressed:
        state = GameState.INTRO


def won_screen():
    global state, high_score

    screen.brush = brushes.color(8, 14, 10)
    screen.clear()

    screen.brush = brushes.color(120, 230, 140)
    center_text("YOU ESCAPED!", 30, large_font)

    is_new_high = score > high_score
    if is_new_high:
        high_score = score
        try:
            State.save("octodoom", {"high_score": high_score})
        except Exception:
            pass

    screen.brush = brushes.color(220, 220, 220)
    center_text(f"Score: {score}", 55)
    center_text(f"Level {level}/{MAX_LEVEL}  |  Wave {wave}", 66)
    if is_new_high:
        screen.brush = brushes.color(255, 210, 100)
        center_text("New high score!", 78)

    if int(io.ticks / 500) % 2:
        screen.brush = brushes.color(255, 255, 255)
        center_text("SPACE/B to continue", 100)

    if io.BUTTON_B in io.pressed:
        state = GameState.INTRO


def init():
    global high_score
    saved = {"high_score": 0}
    try:
        if State.load("octodoom", saved):
            high_score = saved.get("high_score", 0)
    except Exception:
        high_score = 0


def on_exit():
    try:
        State.save("octodoom", {"high_score": max(high_score, score)})
    except Exception:
        pass


if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)
