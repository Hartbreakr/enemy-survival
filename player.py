"""player.py - the ship: movement, taking damage, pickups, XP and level-ups.

Owns everything about the player's own body and progression. It does not know
about enemies or weapons; those modules call `damage_player`, `add_income`
and `gain_xp` from here.
"""
import math
import random

import config
from effects import add_shake, spawn_explosion
from sprites import facing_ship_index


def default_player_stats() -> dict[str, float | int]:
    return dict(config.PLAYER_START_STATS)


# ============================================================
# 1) MOVEMENT
# ============================================================
def approach(value: float, target: float, amount: float) -> float:
    """Move `value` toward `target` by at most `amount`."""
    if value < target:
        return min(value + amount, target)
    if value > target:
        return max(value - amount, target)
    return target


def update_player_movement(state, inputs, dt: float) -> None:
    """Accelerate toward the held direction, otherwise slow down with friction."""
    stats = state.stats
    max_speed = stats["sprint_speed"] if inputs.sprint else stats["walk_speed"]

    if inputs.move_x != 0 or inputs.move_y != 0:
        length = math.hypot(inputs.move_x, inputs.move_y)
        target_vx = inputs.move_x / length * max_speed
        target_vy = inputs.move_y / length * max_speed
        state.vx = approach(state.vx, target_vx, config.PLAYER_ACCEL * dt)
        state.vy = approach(state.vy, target_vy, config.PLAYER_ACCEL * dt)
    else:
        state.vx = approach(state.vx, 0.0, config.PLAYER_FRICTION * dt)
        state.vy = approach(state.vy, 0.0, config.PLAYER_FRICTION * dt)

    state.px = max(0.0, min(state.px + state.vx * dt, config.SCREEN_WIDTH - 1))
    state.py = max(float(config.HUD_ROWS), min(state.py + state.vy * dt, config.SCREEN_HEIGHT - 1))
    state.ship_index = facing_ship_index(state.vx, state.vy, state.ship_index)

    if state.iframes > 0.0:
        state.iframes = max(0.0, state.iframes - dt)


def player_cell(state) -> tuple[int, int]:
    return int(state.px), int(state.py)


def player_center(state) -> tuple[float, float]:
    """Middle of the ship's cell; enemies aim here so shots cannot slip past a corner."""
    return int(state.px) + 0.5, int(state.py) + 0.5


# ============================================================
# 2) DAMAGE AND DEATH
# ============================================================
def damage_player(state, amount: int) -> bool:
    """Hurt the player. Returns True if damage landed.

    Blocked by the shield buff and by invulnerability frames. On death the
    game switches to the 'dying' explosion; game.py finishes the hand-off.
    """
    if state.mode != "playing" or amount <= 0:
        return False
    if state.iframes > 0.0 or state.buffs.get("shield", 0.0) > 0.0:
        return False

    state.health -= amount
    state.iframes = config.IFRAME_SECONDS
    add_shake(state.effects, config.SHAKE_PLAYER_HIT)
    if state.health <= 0:
        state.health = 0
        state.mode = "dying"
        state.death_timer = 0.0
        state.projectiles.clear()
        state.player_bullets.clear()
        spawn_explosion(state.effects, state.px, state.py, count=24, scale=1.3)
    return True


def player_is_visible(state) -> bool:
    """Ship blinks while invulnerable."""
    if state.iframes <= 0.0:
        return True
    return int(state.iframes * config.IFRAME_BLINK_HZ) % 2 == 0


# ============================================================
# 3) SCORE, POINTS AND XP
# ============================================================
def add_income(state, amount: int) -> None:
    """Every source of money goes through here.

    Score is the cumulative total shown on the HUD and the game over screen.
    Points are the same income but spendable in the shop. The Cash Grab buff
    doubles points only, so the high score stays comparable between runs.
    """
    state.score += amount
    multiplier = 2 if state.buffs.get("cash_grab", 0.0) > 0.0 else 1
    state.points += amount * multiplier


def gain_xp(state, amount: int) -> None:
    """Add XP, level up as many times as needed, queue the level-up menu."""
    state.xp += amount
    while state.xp >= state.xp_needed:
        state.xp -= state.xp_needed
        state.level += 1
        state.pending_level_ups += 1
        state.xp_needed = int(state.xp_needed * config.XP_GROWTH)
    open_level_up_if_pending(state)


def open_level_up_if_pending(state) -> None:
    if state.pending_level_ups > 0 and not state.level_up_open:
        state.pending_level_ups -= 1
        state.level_up_choices = make_level_up_choices(state.weapon_slots)
        state.level_up_open = True


def make_level_up_choices(weapon_slots: list) -> list[dict]:
    available = list(config.GENERIC_UPGRADES)
    for weapon_id in set(weapon_slots):
        if weapon_id in config.WEAPON_UPGRADES:
            available.extend(
                {**upgrade, "kind": "weapon", "weapon_id": weapon_id}
                for upgrade in config.WEAPON_UPGRADES[weapon_id]
            )
    return random.sample(available, config.LEVEL_UP_CHOICE_COUNT)


def apply_level_upgrade(state, choice: dict) -> None:
    stats = state.stats
    if choice["kind"] == "player":
        upgrade_id = choice["id"]
        if upgrade_id == "move_speed":
            stats["walk_speed"] += 1.0
            stats["sprint_speed"] += 1.0
        elif upgrade_id == "weapon_range":
            stats["weapon_range"] += 8.0
        elif upgrade_id == "cooldown_rate":
            stats["cooldown_multiplier"] = max(0.5, stats["cooldown_multiplier"] * 0.9)
        elif upgrade_id == "max_health":
            stats["max_health"] += 1
            state.health += 1
        elif upgrade_id == "pickup_value":
            stats["pickup_value"] += 1
    else:
        modifiers = state.weapon_upgrades.setdefault(choice["weapon_id"], {})
        stat = choice["stat"]
        if "factor" in choice:
            modifiers[stat] = modifiers.get(stat, 1.0) * choice["factor"]
        else:
            modifiers[stat] = modifiers.get(stat, 0) + choice["amount"]
    state.health = min(state.health, stats["max_health"])


def choose_level_upgrade(state, index: int) -> None:
    """Called when the player presses 1-3 on the level-up menu."""
    if not state.level_up_open or index >= len(state.level_up_choices):
        return
    apply_level_upgrade(state, state.level_up_choices[index])
    state.level_up_open = False
    open_level_up_if_pending(state)


# ============================================================
# 4) PICKUPS, DROPS AND BUFFS
# ============================================================
def random_arena_cell() -> tuple[int, int]:
    margin = config.ARENA_MARGIN
    return (
        random.randint(margin, config.SCREEN_WIDTH - 1 - margin),
        random.randint(config.HUD_ROWS + margin, config.SCREEN_HEIGHT - 1 - margin),
    )


def create_drop(x: float, y: float) -> dict:
    kinds = list(config.DROP_WEIGHTS)
    weights = [config.DROP_WEIGHTS[kind] for kind in kinds]
    return {
        "x": float(x),
        "y": float(y),
        "type": random.choices(kinds, weights=weights, k=1)[0],
        "age": 0.0,
    }


def drop_is_flashing(drop: dict) -> bool:
    return drop["age"] >= config.DROP_FLASH_START


def collect_drop(state, drop: dict) -> None:
    if drop["type"] == "health":
        state.health = min(state.stats["max_health"], state.health + 1)
    elif drop["type"] in config.BUFF_DURATIONS:
        state.buffs[drop["type"]] = config.BUFF_DURATIONS[drop["type"]]
    else:
        add_income(state, state.stats["pickup_value"])


def update_pickups(state, dt: float) -> None:
    """Age drops, remove stale ones, collect anything the ship is standing on."""
    cell = player_cell(state)

    if cell == (state.pickup_x, state.pickup_y):
        add_income(state, state.stats["pickup_value"])
        state.pickup_x, state.pickup_y = random_arena_cell()

    for drop in list(state.drops):
        drop["age"] += dt
        if drop["age"] >= config.DROP_LIFETIME:
            state.drops.remove(drop)
        elif cell == (int(drop["x"]), int(drop["y"])):
            collect_drop(state, drop)
            state.drops.remove(drop)

    for buff_name in list(state.buffs):
        state.buffs[buff_name] -= dt
        if state.buffs[buff_name] <= 0.0:
            del state.buffs[buff_name]
