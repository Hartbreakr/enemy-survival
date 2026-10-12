"""sprites.py - hand-drawn pixel art, stamped into the tcod tileset.

Each sprite is a grid of strings (10 wide for a normal tile, 30 wide for the
boss); '.' is transparent and every other character looks up a color in that
sprite's palette. `register_sprites(tileset)` writes them all into private-use
codepoints so the game can draw a sprite with console.print(chr(codepoint)).

Codepoint map (private use area, never collides with the ASCII charmap):
    \ue000-\ue007  ship, 8 rotations (right, down-right, down, ... up-right)
    \ue010 normal alien   \ue011 elite   (\ue012 unused)
    \ue013 dasher  \ue014 sniper  \ue015 splitter  \ue016 splitling  \ue017 tank
    \ue018 full heart     \ue019 empty heart
    \ue020-\ue028  boss, 9 tiles that assemble into one 3x3 picture
    + 0x40        white "hit flash" copy of every enemy/boss tile
"""
import math

import numpy as np
from PIL import Image

# ============================================================
# 1) CODEPOINTS
# ============================================================
SHIP_CODEPOINTS = [ord("\ue000") + i for i in range(8)]
ALIEN_NORMAL_CODEPOINT = ord("\ue010")
ALIEN_ELITE_CODEPOINT = ord("\ue011")
DASHER_CODEPOINT = ord("\ue013")
SNIPER_CODEPOINT = ord("\ue014")
SPLITTER_CODEPOINT = ord("\ue015")
SPLITLING_CODEPOINT = ord("\ue016")
TANK_CODEPOINT = ord("\ue017")
HEART_FULL_CODEPOINT = ord("\ue018")
HEART_EMPTY_CODEPOINT = ord("\ue019")
BOSS_CODEPOINTS = [ord("\ue020") + i for i in range(9)]   # row-major, top-left first
FLASH_OFFSET = 0x40                                        # codepoint + 0x40 = white copy

# Enemy kind (see config.ENEMY_TYPES) -> codepoint.
ENEMY_CODEPOINTS = {
    "normal": ALIEN_NORMAL_CODEPOINT,
    "elite": ALIEN_ELITE_CODEPOINT,
    "dasher": DASHER_CODEPOINT,
    "sniper": SNIPER_CODEPOINT,
    "splitter": SPLITTER_CODEPOINT,
    "splitling": SPLITLING_CODEPOINT,
    "tank": TANK_CODEPOINT,
}


def flash_codepoint(codepoint: int) -> int:
    """The all-white version of a sprite, used for the hit flash."""
    return codepoint + FLASH_OFFSET


# ============================================================
# 2) PALETTES
# ============================================================
# The ship is drawn with a WHITE foreground so these colors show as-is
# (tcod multiplies a colored tile by the print color).
SHIP_PALETTE = {
    "W": (235, 240, 248),   # white hull
    "S": (165, 175, 195),   # silver shading on the wings
    "R": (210, 30, 45),     # deep red stripes and wing tips
    "D": (28, 32, 48),      # near-black outline
    "C": (130, 240, 255),   # bright cyan cockpit
    "E": (110, 190, 255),   # blue engine glow
}

ALIEN_NORMAL_PALETTE = {
    "G": (90, 255, 90),     # green body
    "D": (20, 120, 40),     # dark green outline
    "W": (255, 255, 255),   # eye white
    "K": (0, 0, 0),         # pupil
}

ALIEN_ELITE_PALETTE = {
    "R": (240, 80, 130),    # magenta body
    "D": (120, 20, 60),     # dark magenta outline
    "W": (255, 255, 255),   # eye
    "K": (0, 0, 0),         # pupil
}

DASHER_PALETTE = {
    "O": (255, 140, 30),    # orange hull
    "D": (150, 60, 10),     # dark orange tail
    "Y": (255, 235, 110),   # bright nose stripe
}

SNIPER_PALETTE = {
    "P": (175, 110, 255),   # purple body
    "D": (80, 30, 140),     # dark purple scope housing
    "W": (255, 255, 255),   # scope glass
    "R": (255, 60, 60),     # scope dot
}

SPLITTER_PALETTE = {
    "Y": (255, 225, 60),    # yellow blob
    "D": (160, 120, 0),     # dark yellow mouth
    "K": (0, 0, 0),         # eyes
}

TANK_PALETTE = {
    "S": (150, 160, 175),   # steel plates
    "D": (60, 70, 85),      # dark seams
    "B": (90, 150, 230),    # blue lights
    "L": (205, 215, 225),   # light trim
}

HEART_PALETTE = {
    "R": (255, 80, 90),     # full heart
    "P": (255, 170, 180),   # highlight
    "D": (70, 30, 40),      # empty heart outline
}

BOSS_PALETTE = {
    "P": (170, 60, 200),    # purple hull
    "D": (60, 15, 85),      # dark outline
    "G": (90, 255, 90),     # green lights (same green as the crabs it commands)
    "W": (255, 255, 255),   # eye white
    "K": (0, 0, 0),         # pupil
    "R": (255, 70, 70),     # red core
    "M": (240, 80, 130),    # magenta tentacle tips (elite color)
}

# ============================================================
# 3) SPRITE ART (10x10 unless noted)
# ============================================================
# Fighter facing up: pointed white nose, cyan cockpit, swept wings with red
# stripes and red tips, twin blue engines. Symmetric about the middle.
SHIP_UP = (
    "....DD....",
    "...DWWD...",
    "...DWWD...",
    "..DWCCWD..",
    "..DWCCWD..",
    ".DWRWWRWD.",
    "DWRRWWRRWD",
    "DRRSWWSRRD",
    ".DDDWWDDD.",
    "..EE..EE..",
)

ALIEN_NORMAL = (
    ".G......G.",
    "..GGGGGG..",
    ".GGGGGGGG.",
    "GGGWGGWGGG",
    "GGGGGGGGGG",
    "GGGGGGGGGG",
    ".GG.GG.GG.",
    ".D..GG..D.",
    "..G....G..",
    "..........",
)

ALIEN_ELITE = (
    "..R....R..",
    "..RR..RR..",
    "...RRRR...",
    "..RRRRRR..",
    ".RRRWWRRR.",
    "RRRRWWRRRR",
    "RRRRRRRRRR",
    ".DRRRRRRD.",
    "..R.RR.R..",
    "..........",
)

# Arrowhead pointing right (dashers charge in any direction; the sprite is
# a fixed silhouette, the telegraph line shows the real direction).
DASHER = (
    "OO........",
    "DOOO......",
    "DOOOOO....",
    "DOYOOOOO..",
    "DOYYOOOOOO",
    "DOYYOOOOOO",
    "DOYOOOOO..",
    "DOOOOO....",
    "DOOO......",
    "OO........",
)

# Thin stalk with a scope at the top.
SNIPER = (
    "....PP....",
    "...PDDP...",
    "...DWRD...",
    "...PDDP...",
    "....PP....",
    "....PP....",
    "..PPPPPP..",
    ".P..PP..P.",
    "....PP....",
    "...P..P...",
)

SPLITTER = (
    "...YYYY...",
    ".YYYYYYYY.",
    "YYYKYYYKYY",
    "YYYYYYYYYY",
    "YYYYYYYYYY",
    "YYDYYYYDYY",
    "YYYDDDDYYY",
    ".YYYYYYYY.",
    "..YY..YY..",
    "..........",
)

SPLITLING = (
    "..........",
    "..........",
    "...YYYY...",
    "..YYKYKY..",
    "..YYYYYY..",
    "..YDYYDY..",
    "...YDDY...",
    "....YY....",
    "..........",
    "..........",
)

# Boxy hull with blue lights. The shield itself is drawn by the game as a
# bar on whichever side faces the player.
TANK = (
    "DDDDDDDDDD",
    "DSSSSSSSSD",
    "DSBBSSBBSD",
    "DSBBSSBBSD",
    "DSSSSSSSSD",
    "DSSLLLLSSD",
    "DSSLBBLSSD",
    "DSSSSSSSSD",
    "DDDDDDDDDD",
    "D.D.DD.D.D",
)

HEART_FULL = (
    "..........",
    ".RR...RR..",
    "RPRR.RRRR.",
    "RPRRRRRRR.",
    "RRRRRRRRR.",
    ".RRRRRRR..",
    "..RRRRR...",
    "...RRR....",
    "....R.....",
    "..........",
)

HEART_EMPTY = (
    "..........",
    ".DD...DD..",
    "D..D.D..D.",
    "D...D...D.",
    "D.......D.",
    ".D.....D..",
    "..D...D...",
    "...D.D....",
    "....D.....",
    "..........",
)

# The boss overlord: a 30x30 picture split into a 3x3 grid of tiles.
# Dome head with two eyes and a red core, a wide saucer with green lights,
# and five tentacles hanging below.
BOSS = (
    "............DDDDDD............",
    "..........DDPPPPPPDD..........",
    ".........DPPPPPPPPPPD.........",
    "........DPPPPPPPPPPPPD........",
    ".......DPPPPWWPPWWPPPPD.......",
    ".......DPPPPWKPPWKPPPPD.......",
    "......DPPPPPPPPPPPPPPPPD......",
    "......DPPPPPPPPPPPPPPPPD......",
    ".....DPPPPPPPPRRPPPPPPPPD.....",
    ".....DPPPPPPPRRRRPPPPPPPD.....",
    "....DDPPPPPPPRRRRPPPPPPPDD....",
    "...DPPDPPPPPPPRRPPPPPPPDPPD...",
    "..DPPPPDPPPPPPPPPPPPPPDPPPPD..",
    ".DPPPPPPDDPPPPPPPPPPDDPPPPPPD.",
    ".DPPWPPPPPDDDDDDDDDDPPPPPWPPD.",
    ".DPPWPPPPPPPPPPPPPPPPPPPPWPPD.",
    "DPPPPPPPPPPPPPPPPPPPPPPPPPPPPD",
    "DPPPPGGPPPPGGPPPPGGPPPPGGPPPPD",
    "DPPPPGGPPPPGGPPPPGGPPPPGGPPPPD",
    ".DPPPPPPPPPPPPPPPPPPPPPPPPPPD.",
    ".DDPPPPPPPPPPPPPPPPPPPPPPPPDD.",
    "..DDPPDDPPDDPPDDPPDDPPDDPPDD..",
    "...DPPD.DPPD.DPPD.DPPD.DPPD...",
    "...DPPD.DPPD.DPPD.DPPD.DPPD...",
    "...DPMD.DPMD.DPMD.DPMD.DPMD...",
    "....DMD.DMD...DMD...DMD.DMD...",
    "....DMD..DMD..DMD..DMD..DMD...",
    "....DMD...DMD.DMD.DMD...DMD...",
    ".....D.....D...D...D.....D....",
    "..............................",
)

TILE_SIZE = 10


# ============================================================
# 4) GRID -> IMAGE DATA
# ============================================================
def _grid_layer(grid, palette, white: bool = False) -> np.ndarray:
    """Return an HxWx4 uint8 RGBA array for a char grid.

    white=True keeps the silhouette but paints every pixel white; those copies
    are what the hit flash shows.
    """
    rows = [row for row in grid if row != ""]
    height = len(rows)
    width = len(rows[0])
    for row in rows:
        assert len(row) == width, f"sprite row has wrong width: {row!r}"
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                color = (255, 255, 255) if white else palette[ch]
                arr[y, x] = (*color, 255)
    return arr


def _boss_tiles(white: bool = False) -> list[np.ndarray]:
    """Slice the 30x30 boss picture into 9 tiles, row-major."""
    full = _grid_layer(BOSS, BOSS_PALETTE, white)
    assert full.shape[:2] == (3 * TILE_SIZE, 3 * TILE_SIZE), "boss art must be 30x30"
    tiles = []
    for row in range(3):
        for col in range(3):
            y0, x0 = row * TILE_SIZE, col * TILE_SIZE
            tiles.append(full[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE].copy())
    return tiles


def _center_crop(img: Image.Image, size: int) -> Image.Image:
    w, h = img.size
    left = (w - size) // 2
    top = (h - size) // 2
    return img.crop((left, top, left + size, top + size))


def _rotated(base: Image.Image, degrees: float) -> np.ndarray:
    """Rotate a sprite (nearest-neighbor) and center-crop back to tile size."""
    rot = base.rotate(degrees, resample=Image.NEAREST, expand=True)
    return np.asarray(_center_crop(rot, TILE_SIZE))


# Direction index -> rotation degrees (PIL rotate, positive = counterclockwise).
# Base art faces up (index 6).
SHIP_ROTATIONS = [270, 225, 180, 135, 90, 45, 0, 315]

# Single-tile sprites that get a normal and a white flash copy.
ENEMY_ART = {
    ALIEN_NORMAL_CODEPOINT: (ALIEN_NORMAL, ALIEN_NORMAL_PALETTE),
    ALIEN_ELITE_CODEPOINT: (ALIEN_ELITE, ALIEN_ELITE_PALETTE),
    DASHER_CODEPOINT: (DASHER, DASHER_PALETTE),
    SNIPER_CODEPOINT: (SNIPER, SNIPER_PALETTE),
    SPLITTER_CODEPOINT: (SPLITTER, SPLITTER_PALETTE),
    SPLITLING_CODEPOINT: (SPLITLING, SPLITTER_PALETTE),
    TANK_CODEPOINT: (TANK, TANK_PALETTE),
}


# ============================================================
# 5) TILESET REGISTRATION
# ============================================================
def register_sprites(tileset) -> int:
    """Stamp every sprite into the tileset. Returns how many tiles were written."""
    count = 0
    base = Image.fromarray(_grid_layer(SHIP_UP, SHIP_PALETTE), mode="RGBA")
    for index, degrees in enumerate(SHIP_ROTATIONS):
        tileset[SHIP_CODEPOINTS[index]] = _rotated(base, degrees)
        count += 1

    for codepoint, (grid, palette) in ENEMY_ART.items():
        tileset[codepoint] = _grid_layer(grid, palette)
        tileset[flash_codepoint(codepoint)] = _grid_layer(grid, palette, white=True)
        count += 2

    tileset[HEART_FULL_CODEPOINT] = _grid_layer(HEART_FULL, HEART_PALETTE)
    tileset[HEART_EMPTY_CODEPOINT] = _grid_layer(HEART_EMPTY, HEART_PALETTE)
    count += 2

    for codepoint, tile, white_tile in zip(BOSS_CODEPOINTS, _boss_tiles(), _boss_tiles(white=True)):
        tileset[codepoint] = tile
        tileset[flash_codepoint(codepoint)] = white_tile
        count += 2
    return count


# ============================================================
# 6) SHIP FACING
# ============================================================
def facing_ship_index(vx: float, vy: float, current: int) -> int:
    """Pick a ship orientation from velocity; keep the old one when nearly still."""
    if math.hypot(vx, vy) < 0.1:
        return current
    return round(math.atan2(vy, vx) / (math.pi / 4)) % 8


# ============================================================
# 7) PREVIEW EXPORT: `python sprites.py` writes sprite_preview.png
# ============================================================
def _preview() -> None:
    base = Image.fromarray(_grid_layer(SHIP_UP, SHIP_PALETTE), mode="RGBA")
    items = [Image.fromarray(_rotated(base, deg), "RGBA") for deg in SHIP_ROTATIONS]
    for grid, palette in ENEMY_ART.values():
        items.append(Image.fromarray(_grid_layer(grid, palette), "RGBA"))
    items.append(Image.fromarray(_grid_layer(HEART_FULL, HEART_PALETTE), "RGBA"))
    items.append(Image.fromarray(_grid_layer(HEART_EMPTY, HEART_PALETTE), "RGBA"))

    scale = 12
    pad = scale
    cell = TILE_SIZE * scale
    boss_cell = 3 * cell
    width = len(items) * (cell + pad) + pad
    height = cell + 2 * pad + boss_cell + pad
    sheet = Image.new("RGBA", (max(width, boss_cell + 2 * pad), height), (15, 15, 25, 255))
    for i, img in enumerate(items):
        big = img.resize((cell, cell), Image.NEAREST)
        sheet.paste(big, (pad + i * (cell + pad), pad), big)

    boss = Image.fromarray(_grid_layer(BOSS, BOSS_PALETTE), "RGBA").resize((boss_cell, boss_cell), Image.NEAREST)
    sheet.paste(boss, (pad, cell + 2 * pad), boss)
    sheet.convert("RGB").save("sprite_preview.png")
    tile_count = len(items) + 9
    print(f"wrote sprite_preview.png with {tile_count} sprite tiles "
          f"({len(items)} single tiles + 9 boss tiles)")


if __name__ == "__main__":
    _preview()
