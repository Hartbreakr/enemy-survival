"""boss.py - the overlord that shows up every 5th wave.

Owns the Boss object, its movement, the three bullet patterns, its 3x3 tile
collision footprint and its death payout. It fires through enemies.fire_at so
boss bullets are ordinary enemy projectiles (the Mirror Shield can reflect them).

Phases by remaining hp:
    phase 1 (100-66%)  slow drift, radial rings
    phase 2 (66-33%)   rotating spiral arms plus a bigger ring now and then
    phase 3 (<33%)     chases the player, aimed shotgun fans, loose spiral
"""
import math
import random
from dataclasses import dataclass

import config
from effects import add_shake, spawn_damage_number, spawn_explosion
from enemies import fire_at
from player import add_income, damage_player, gain_xp, player_center


@dataclass
class Boss:
    x: float                    # center tile of the 3x3 footprint
    y: float
    hp: int
    max_hp: int
    target_x: float
    target_y: float
    ring_timer: float = 0.0
    spiral_timer: float = 0.0
    fan_timer: float = 1.0
    retarget_timer: float = 0.0
    ring_angle: float = 0.0
    spiral_angle: float = 0.0
    flash: float = 0.0


def spawn_boss(wave: int) -> Boss:
    hp = config.BOSS_BASE_HP + config.BOSS_HP_PER_WAVE * wave
    return Boss(
        x=config.BOSS_SPAWN_X, y=config.BOSS_SPAWN_Y, hp=hp, max_hp=hp,
        target_x=config.BOSS_SPAWN_X, target_y=config.BOSS_SPAWN_Y,
    )


def boss_reward(wave: int) -> int:
    return config.BOSS_REWARD_BASE + config.BOSS_REWARD_PER_WAVE * wave


# ============================================================
# 1) FOOTPRINT AND PHASE
# ============================================================
def boss_cells(boss: Boss) -> list[tuple[int, int]]:
    """The 9 tiles the boss covers, row-major (matches sprites.BOSS_CODEPOINTS)."""
    cx, cy = int(boss.x), int(boss.y)
    return [(cx + dx, cy + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]


def boss_phase(boss: Boss) -> int:
    fraction = boss.hp / boss.max_hp
    if fraction > config.BOSS_PHASE_THRESHOLDS[0]:
        return 1
    if fraction > config.BOSS_PHASE_THRESHOLDS[1]:
        return 2
    return 3


def boss_near(boss: Boss, x: float, y: float, radius: float) -> bool:
    """True if a blast centered on (x, y) reaches any part of the footprint."""
    return math.hypot(boss.x - x, boss.y - y) <= radius + 1.5


# ============================================================
# 2) MOVEMENT AND PATTERNS
# ============================================================
def pick_target(state, boss: Boss, phase: int) -> None:
    """Phase 1-2 wander the upper arena; phase 3 heads for the player."""
    if phase == 3:
        boss.target_x, boss.target_y = state.px, state.py
        boss.retarget_timer = 0.5
    else:
        boss.target_x = random.uniform(10, config.SCREEN_WIDTH - 11)
        boss.target_y = random.uniform(config.HUD_ROWS + 3, config.SCREEN_HEIGHT * 0.45)
        boss.retarget_timer = random.uniform(2.0, 3.5)


def move_boss(state, boss: Boss, speed: float, dt: float) -> None:
    dx = boss.target_x - boss.x
    dy = boss.target_y - boss.y
    dist = math.hypot(dx, dy)
    if dist > 0.5:
        step = min(speed * dt, dist)
        boss.x += dx / dist * step
        boss.y += dy / dist * step
    boss.x = max(1.0, min(boss.x, config.SCREEN_WIDTH - 2))
    boss.y = max(float(config.HUD_ROWS + 1), min(boss.y, config.SCREEN_HEIGHT - 2))


def fire_ring(state, boss: Boss, count: int, speed: float) -> None:
    for index in range(count):
        angle = boss.ring_angle + math.tau * index / count
        fire_at(state, boss, boss.x + math.cos(angle), boss.y + math.sin(angle), speed,
                config.BOSS_BULLET_DAMAGE, char="o", color=(240, 80, 130), heavy=True)
    boss.ring_angle += math.radians(15)


def fire_spiral(state, boss: Boss, arms: int, step: float, speed: float) -> None:
    for index in range(arms):
        angle = boss.spiral_angle + math.tau * index / arms
        fire_at(state, boss, boss.x + math.cos(angle), boss.y + math.sin(angle), speed,
                config.BOSS_BULLET_DAMAGE, char=".", color=(170, 60, 200), heavy=True)
    boss.spiral_angle += step


def fire_fan(state, boss: Boss, count: int, spread: float, speed: float) -> None:
    target_x, target_y = player_center(state)
    base = math.atan2(target_y - boss.y, target_x - boss.x)
    for index in range(count):
        angle = base - spread + 2 * spread * index / max(1, count - 1)
        fire_at(state, boss, boss.x + math.cos(angle), boss.y + math.sin(angle), speed,
                config.BOSS_BULLET_DAMAGE, char="*", color=(255, 70, 70), heavy=True)


def update_boss(state, dt: float) -> None:
    boss = state.boss
    if boss is None:
        return
    phase = boss_phase(boss)
    pattern = config.BOSS_PATTERNS[phase]

    if boss.flash > 0.0:
        boss.flash = max(0.0, boss.flash - dt)

    boss.retarget_timer -= dt
    if boss.retarget_timer <= 0:
        pick_target(state, boss, phase)
    move_boss(state, boss, pattern["move_speed"], dt)

    if "ring_every" in pattern:
        boss.ring_timer -= dt
        if boss.ring_timer <= 0:
            fire_ring(state, boss, pattern["ring_count"], pattern["ring_speed"])
            boss.ring_timer = pattern["ring_every"]
    if "spiral_every" in pattern:
        boss.spiral_timer -= dt
        if boss.spiral_timer <= 0:
            fire_spiral(state, boss, pattern["spiral_arms"], pattern["spiral_step"], pattern["spiral_speed"])
            boss.spiral_timer = pattern["spiral_every"]
    if "fan_every" in pattern:
        boss.fan_timer -= dt
        if boss.fan_timer <= 0:
            fire_fan(state, boss, pattern["fan_count"], pattern["fan_spread"], pattern["fan_speed"])
            boss.fan_timer = pattern["fan_every"]

    if (int(state.px), int(state.py)) in boss_cells(boss):
        damage_player(state, config.BOSS_CONTACT_DAMAGE)


# ============================================================
# 3) TAKING DAMAGE AND DYING
# ============================================================
def damage_boss(state, damage: int) -> bool:
    """Hurt the boss. Returns True if this hit killed it."""
    boss = state.boss
    if boss is None:
        return False
    boss.hp -= damage
    boss.flash = config.HIT_FLASH_SECONDS
    add_shake(state.effects, config.SHAKE_BOSS_HIT)
    spawn_damage_number(state.effects, boss.x, boss.y - 1, damage)
    if boss.hp > 0:
        return False

    boss.hp = 0
    state.boss = None
    state.kills_this_wave += 1
    state.projectiles.clear()
    add_income(state, boss_reward(state.wave))
    gain_xp(state, config.BOSS_XP)
    add_shake(state.effects, config.SHAKE_BOSS_DEATH)
    for cx, cy in boss_cells(boss):
        spawn_explosion(state.effects, cx + 0.5, cy + 0.5, count=10, scale=1.6)
    return True
