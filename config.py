"""config.py - every tunable number and data table in one place.

This module owns: screen size, timing, player stats, XP curve, drop table,
enemy stat table, wave composition, boss numbers, weapon catalog, upgrade
trees, shop slot items and game-feel timings. No logic lives here, only data,
so you can rebalance the game without touching any other file.
"""

import os
import sys


def resource_path(relative: str) -> str:
    """Resolve a bundled read-only asset, working both as a script and inside a PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


# ============================================================
# 1) SCREEN AND TIMING
# ============================================================
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
TARGET_FPS = 120
STEP = 1.0 / TARGET_FPS            # fixed simulation step (seconds)
GAME_TITLE = "ENEMY SURVIVAL"
WINDOW_TITLE = "Enemy Survival"
TILESHEET_FILE = "dejavu10x10_gs_tc.png"
HIGHSCORE_FILE = "highscore.txt"   # old format (one number); migrated into SAVE_FILE
SAVE_FILE = "save.json"            # {"highscore": N, "seen": [enemy kinds met so far]}

# The HUD uses rows 0-3. The player is kept below that so text stays readable.
HUD_ROWS = 4
ARENA_MARGIN = 4                   # pickups / enemies stay this far from the edges

# ============================================================
# 2) PLAYER
# ============================================================
PLAYER_START_X = SCREEN_WIDTH / 2
PLAYER_START_Y = SCREEN_HEIGHT / 2 + 5
PLAYER_ACCEL = 18.0                # tiles / second^2 while a key is held
PLAYER_FRICTION = 7.5              # tiles / second^2 when no key is held
IFRAME_SECONDS = 0.8               # invulnerability after taking damage
IFRAME_BLINK_HZ = 12               # ship blink speed while invulnerable
DEATH_ANIMATION_SECONDS = 1.2      # explosion before the game over screen

# These are the stats the level-up menu can raise.
PLAYER_START_STATS = {
    "walk_speed": 8.0,
    "sprint_speed": 12.0,
    "weapon_range": 30.0,
    "cooldown_multiplier": 1.0,    # lower = faster weapons (min 0.5)
    "max_health": 5,
    "pickup_value": 4,             # score/points per '*' pickup or points drop (was 5)
}

# ============================================================
# 3) XP CURVE AND LEVEL-UP CHOICES
# ============================================================
# XP comes only from kills, using ENEMY_XP (section 6) and BOSS_XP below.
# Level 2 needs 60 XP, each level after that needs 30% more.
# A typical run reaches level 3 around wave 2 and level 6 around wave 5.
XP_FIRST_LEVEL = 60
XP_GROWTH = 1.3
LEVEL_UP_CHOICE_COUNT = 3

GENERIC_UPGRADES = (
    {"id": "move_speed", "label": "Move speed +1", "kind": "player"},
    {"id": "weapon_range", "label": "Weapon range +8", "kind": "player"},
    {"id": "cooldown_rate", "label": "Cooldowns 10% faster", "kind": "player"},
    {"id": "max_health", "label": "Max health +1 and heal", "kind": "player"},
    {"id": "pickup_value", "label": "Pickup value +1", "kind": "player"},
)

WEAPON_UPGRADES = {
    "pulse": (
        {"id": "pulse_damage", "label": "Pulse damage +1", "stat": "damage_bonus", "amount": 1},
        {"id": "pulse_rate", "label": "Pulse fires 10% faster", "stat": "fire_rate_multiplier", "factor": 0.9},
    ),
    "laser": (
        {"id": "laser_damage", "label": "Laser damage +1", "stat": "damage_bonus", "amount": 1},
        {"id": "laser_duration", "label": "Laser burst +2 sec", "stat": "fire_duration_bonus", "amount": 2.0},
    ),
    "shotgun": (
        {"id": "shotgun_damage", "label": "Shotgun damage +1", "stat": "damage_bonus", "amount": 1},
        {"id": "shotgun_pellets", "label": "Shotgun +2 pellets", "stat": "pellet_bonus", "amount": 2},
    ),
    "gatling": (
        {"id": "gatling_damage", "label": "Gatling damage +1", "stat": "damage_bonus", "amount": 1},
        {"id": "gatling_rate", "label": "Gatling fires 10% faster", "stat": "fire_rate_multiplier", "factor": 0.9},
    ),
    "megabomb": (
        {"id": "megabomb_radius", "label": "Mega Bomb blast +1", "stat": "explosion_radius_bonus", "amount": 1.0},
        {"id": "megabomb_damage", "label": "Mega Bomb damage +1", "stat": "damage_bonus", "amount": 1},
    ),
    "mirror_shield": (
        {"id": "shield_duration", "label": "Shield duration +1 sec", "stat": "fire_duration_bonus", "amount": 1.0},
        {"id": "shield_speed", "label": "Reflected bullets +50% speed", "stat": "reflect_speed_bonus", "amount": 0.5},
    ),
    "chain_lightning": (
        {"id": "chain_jumps", "label": "Chain Lightning +1 jump", "stat": "chain_count_bonus", "amount": 1},
        {"id": "chain_range", "label": "Chain Lightning range +2", "stat": "chain_range_bonus", "amount": 2.0},
    ),
}

# ============================================================
# 4) WEAPONS
# ============================================================
# Rough average damage per second at base stats, single target:
#   pulse 2.9 | shotgun 3 (all pellets) | laser 6.7 | gatling 8.3
#   megabomb 1.7 per enemy in the blast | chain 1.3 per enemy hit
#   mirror shield: no damage, reflects enemy bullets for 5 of every 20 s
# Costs were raised ~20% (and kill rewards cut ~20%) to make the economy
# a little tighter: wave 1 income (~55 pts) no longer buys the Shotgun
# outright, wave 2 does; the expensive weapons arrive around wave 6-8.
STARTER_WEAPON = {
    "id": "pulse",
    "name": "Pulse",
    "short": "PLS",
    "cost": 0,
    "damage": 1,
    "speed": 14.5,
    "cooldown": 0.35,
    "spread": 0.0,
    "color": (120, 220, 255),
}

WEAPON_CATALOG = [
    {
        "id": "shotgun",
        "name": "Shotgun",
        "short": "SHG",
        "cost": 75,            # was 60
        "damage": 1,
        "speed": 12.0,
        "cooldown": 1.0,
        "spread": 0.8,
        "pellets": 3,
        "color": (255, 190, 90),
    },
    {
        "id": "laser",
        "name": "Laser",
        "short": "LSR",
        "cost": 110,           # was 90
        "damage": 1,
        "speed": 45.0,
        "cooldown": 5.0,
        "fire_duration": 10.0,
        "fire_rate": 0.1,
        "spread": 0.0,
        "color": (255, 35, 50),
    },
    {
        "id": "megabomb",
        "name": "Mega Bomb",
        "short": "MGB",
        "cost": 145,           # was 120
        "damage": 3,
        "speed": 5.5,
        "cooldown": 1.8,
        "spread": 0.0,
        "explosion_radius": 4.0,
        "projectile_char": "o",
        "color": (255, 135, 45),
    },
    {
        "id": "mirror_shield",
        "name": "Mirror Shield",
        "short": "MIR",
        "cost": 170,           # was 140
        "damage": 1,
        "speed": 0.0,
        "cooldown": 15.0,
        "fire_duration": 5.0,
        "active_ability": True,
        "spread": 0.0,
        "color": (120, 225, 255),
    },
    {
        "id": "gatling",
        "name": "Gatling",
        "short": "GAT",
        "cost": 180,           # was 150
        "damage": 1,
        "speed": 16.0,
        "cooldown": 10.0,
        "fire_duration": 20.0,
        "fire_rate": 0.08,
        "spread": 0.08,
        "color": (255, 100, 80),
    },
    {
        "id": "chain_lightning",
        "name": "Chain Lightning",
        "short": "CHN",
        "cost": 215,           # was 180
        "damage": 2,
        "speed": 35.0,
        "cooldown": 1.5,
        "spread": 0.0,
        "chain_count": 2,
        "chain_range": 8.0,
        "projectile_char": "*",
        "color": (255, 245, 95),
    },
]

SLOT_SHOP_ITEMS = (
    {"id": "slot_3", "type": "slot", "name": "Weapon Slot 3", "cost": 120, "required_level": 3},
    {"id": "slot_4", "type": "slot", "name": "Weapon Slot 4", "cost": 240, "required_level": 6},
)

# ============================================================
# 5) PICKUPS, DROPS AND BUFFS
# ============================================================
DROP_CHANCE = 0.35                 # chance a kill leaves a drop
DROP_WEIGHTS = {                   # which drop, once one is rolled
    "health": 25,
    "points": 50,
    "triple_shot": 8,
    "shield": 9,
    "cash_grab": 8,
}
DROP_LIFETIME = 7.0
DROP_FLASH_START = 5.0             # drop starts blinking this many seconds in
BUFF_DURATIONS = {
    "triple_shot": 10.0,
    "shield": 10.0,
    "cash_grab": 30.0,             # doubles POINTS income (score is unaffected)
}

# ============================================================
# 6) ENEMIES
# ============================================================
# Every kind has: hp, reward (score + points per kill), contact damage,
# the first wave it can appear in and a spawn weight (plus growth per wave).
# All kinds except splitlings gain +1 hp every ENEMY_HP_BONUS_EVERY_WAVES.
# Rewards were cut ~20% to tighten the economy; XP kept the old numbers
# (see ENEMY_XP below) so leveling pace did not change.
ENEMY_HP_BONUS_EVERY_WAVES = 3

ENEMY_TYPES = {
    "normal": {        # green crab: sits still and shoots
        "hp": 1, "reward": 8, "contact_damage": 0,        # reward was 10
        "min_wave": 1, "weight": 60, "weight_per_wave": 0,
        "shoot_cooldown": (1.8, 2.8), "bullet_speed": 8.5, "bullet_damage": 1,
    },
    "elite": {         # magenta squid: sits still, shoots harder and faster
        "hp": 2, "reward": 20, "contact_damage": 0,       # reward was 25
        "min_wave": 1, "weight": 6, "weight_per_wave": 4,
        "shoot_cooldown": (1.5, 2.2), "bullet_speed": 10.5, "bullet_damage": 2,
    },
    "dasher": {        # orange arrowhead: telegraphs, then charges in a straight line
        "hp": 2, "reward": 12, "contact_damage": 1,       # reward was 15
        "min_wave": 2, "weight": 14, "weight_per_wave": 2,
        "wait_seconds": (1.0, 1.6), "telegraph_seconds": 0.5,
        "drift_speed": 2.0, "charge_speed": 30.0, "charge_overshoot": 6.0,
    },
    "splitter": {      # yellow blob: creeps closer, splits into 2 splitlings on death
        "hp": 3, "reward": 12, "contact_damage": 1,       # reward was 15
        "min_wave": 3, "weight": 10, "weight_per_wave": 1,
        "move_speed": 2.5, "split_count": 2,
    },
    "splitling": {     # small yellow blob: fast chaser, never spawns on its own
        "hp": 1, "reward": 4, "contact_damage": 1,        # reward was 5
        "min_wave": 999, "weight": 0, "weight_per_wave": 0,
        "move_speed": 9.0,
    },
    "sniper": {        # thin purple: keeps its distance, aims, then fires a fast shot
        "hp": 2, "reward": 16, "contact_damage": 0,       # reward was 20
        "min_wave": 4, "weight": 10, "weight_per_wave": 1,
        "min_range": 15.0, "max_range": 20.0, "move_speed": 6.0,
        "aim_seconds": 1.0, "aim_lock_seconds": 0.3, "recover_seconds": 2.5,
        "bullet_speed": 24.0, "bullet_damage": 1,
    },
    "tank": {          # grey box: slow, tough, front shield blocks bullets
        "hp": 8, "reward": 32, "contact_damage": 1,       # reward was 40
        "min_wave": 6, "weight": 5, "weight_per_wave": 1,
        "move_speed": 1.5, "turn_rate": 1.2,          # radians per second
        "shield_half_angle_deg": 30.0,                # 60 degree frontal arc
        "shoot_cooldown": (2.8, 3.4), "bullet_speed": 7.0, "bullet_damage": 1,
    },
}

# XP per kill. These are the ORIGINAL reward numbers, kept separate so the
# reward cut above does not slow down leveling.
ENEMY_XP = {
    "normal": 10,
    "elite": 25,
    "dasher": 15,
    "splitter": 15,
    "splitling": 5,
    "sniper": 20,
    "tank": 40,
}

# Enemies are kept this far from the player when a wave spawns.
SPAWN_KEEPOUT = 12

# ============================================================
# 7) WAVES
# ============================================================
# Normal wave size: 6 on wave 1, 8 on wave 2 ... 24 on wave 10.
WAVE_BASE_ENEMIES = 4
WAVE_ENEMIES_PER_WAVE = 2
BOSS_WAVE_INTERVAL = 5             # waves 5, 10, 15 ... are boss waves

# ============================================================
# 8) BOSS
# ============================================================
# Wave 5 boss: 500 hp. Wave 10 boss: 700 hp. Measured headless (strafing
# pilot, every shot that can land does): pulse+1 / gatling / laser kills the
# wave 5 boss in ~15-25 s, pulse+1 / shotgun / laser in ~45-55 s, and a bare
# pulse / shotgun loadout grinds for 2+ minutes. Buy a gun before wave 5.
BOSS_BASE_HP = 300
BOSS_HP_PER_WAVE = 40
BOSS_REWARD_BASE = 250             # score + points on kill
BOSS_REWARD_PER_WAVE = 50
BOSS_XP = 150
BOSS_CONTACT_DAMAGE = 2
BOSS_BULLET_DAMAGE = 1
BOSS_PHASE_THRESHOLDS = (0.66, 0.33)    # hp fraction where phase 2 / 3 begin
BOSS_SPAWN_X = SCREEN_WIDTH / 2
BOSS_SPAWN_Y = 10.0
BOSS_PATTERNS = {
    # phase 1: slow drift, radial rings
    1: {"move_speed": 2.5, "ring_every": 1.5, "ring_count": 12, "ring_speed": 7.0},
    # phase 2: rotating spiral arms plus an occasional ring
    2: {"move_speed": 3.5, "spiral_every": 0.15, "spiral_arms": 3, "spiral_step": 0.3,
        "spiral_speed": 8.0, "ring_every": 3.0, "ring_count": 16, "ring_speed": 7.0},
    # phase 3: chases the player and fires aimed shotgun fans
    3: {"move_speed": 6.0, "fan_every": 0.9, "fan_count": 5, "fan_spread": 0.35,
        "fan_speed": 12.0, "spiral_every": 0.25, "spiral_arms": 2, "spiral_step": 0.35,
        "spiral_speed": 7.0},
}

# ============================================================
# 9) GAME FEEL
# ============================================================
HIT_FLASH_SECONDS = 0.08           # enemy turns white for this long when hit
SHAKE_SECONDS = 0.2                # screen shake decays over this long
SHAKE_PLAYER_HIT = 1.5             # shake strength in tiles
SHAKE_BOSS_HIT = 0.5
SHAKE_BOSS_DEATH = 3.0
DAMAGE_NUMBER_SECONDS = 0.6
