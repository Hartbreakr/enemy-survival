"""weapons.py - the player's guns: auto-fire, cooldowns, bullets and what they hit.

Weapon data lives in config (STARTER_WEAPON, WEAPON_CATALOG). Each equipped
slot has a small state dict: {"cooldown", "firing", "shot_timer"}.
    cooldown    seconds until the weapon can fire again
    firing      seconds left in a burst (laser, gatling) or an active shield
    shot_timer  seconds until the next shot inside a burst
"""
import math

import config
from boss import boss_cells, boss_near, damage_boss
from effects import spawn_spark
from enemies import damage_enemies, tank_blocks


def get_weapon(weapon_id: str) -> dict:
    if weapon_id == config.STARTER_WEAPON["id"]:
        return config.STARTER_WEAPON
    for weapon in config.WEAPON_CATALOG:
        if weapon["id"] == weapon_id:
            return weapon
    raise KeyError(f"unknown weapon {weapon_id!r}")


def new_weapon_state() -> dict:
    return {"cooldown": 0.0, "firing": 0.0, "shot_timer": 0.0}


def weapon_readiness(weapon_id: str, weapon_state: dict, cooldown_multiplier: float) -> float:
    """0.0 (just fired) .. 1.0 (ready). Used by the HUD cooldown indicator."""
    if weapon_state["firing"] > 0:
        return 1.0
    full = get_weapon(weapon_id)["cooldown"] * cooldown_multiplier
    if full <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - weapon_state["cooldown"] / full))


# ============================================================
# 1) TARGETING
# ============================================================
def nearest_target(state, max_range: float):
    """Closest enemy (or the boss) within range, or None."""
    target = None
    best = max_range
    candidates = list(state.enemies)
    if state.boss is not None:
        candidates.append(state.boss)
    for candidate in candidates:
        distance = math.hypot(candidate.x - state.px, candidate.y - state.py)
        if distance < best:
            target = candidate
            best = distance
    return target


# ============================================================
# 2) FIRING
# ============================================================
def fire_weapon(state, weapon_id: str, target) -> None:
    weapon = get_weapon(weapon_id)
    upgrades = state.weapon_upgrades.get(weapon_id, {})
    # Aim at the middle of the target's cell: aiming at its exact corner lets a
    # fast bullet step over the cell without ever landing inside it.
    base_angle = math.atan2(int(target.y) + 0.5 - state.py, int(target.x) + 0.5 - state.px)
    triple_shot = state.buffs.get("triple_shot", 0.0) > 0

    if weapon.get("pellets"):
        pellet_count = weapon["pellets"] + upgrades.get("pellet_bonus", 0)
        if triple_shot:
            pellet_count += 2
        if pellet_count == 1:
            angles = [base_angle]
        else:
            angles = [
                base_angle - weapon["spread"] + 2 * weapon["spread"] * index / (pellet_count - 1)
                for index in range(pellet_count)
            ]
    elif weapon["spread"] == 0.0:
        angles = [base_angle - 0.18, base_angle, base_angle + 0.18] if triple_shot else [base_angle]
    else:
        angles = [base_angle - weapon["spread"], base_angle, base_angle + weapon["spread"]]
        if triple_shot:
            angles = [base_angle - 0.28, base_angle, base_angle + 0.28]

    for angle in angles:
        state.player_bullets.append(
            {
                "x": state.px,
                "y": state.py,
                "vx": math.cos(angle) * weapon["speed"],
                "vy": math.sin(angle) * weapon["speed"],
                "damage": weapon["damage"] + upgrades.get("damage_bonus", 0),
                "color": weapon["color"],
                "char": weapon.get("projectile_char", "."),
                "weapon_id": weapon_id,
                "explosion_radius": weapon.get("explosion_radius", 0) + upgrades.get("explosion_radius_bonus", 0),
                "chain_count": weapon.get("chain_count", 0) + upgrades.get("chain_count_bonus", 0),
                "chain_range": weapon.get("chain_range", 0) + upgrades.get("chain_range_bonus", 0),
            }
        )


def update_weapons(state, dt: float) -> None:
    """Tick every slot's timers and auto-fire at the nearest target in range."""
    multiplier = state.stats["cooldown_multiplier"]
    for slot, weapon_id in enumerate(state.weapon_slots):
        if weapon_id is None:
            continue
        weapon = get_weapon(weapon_id)
        weapon_state = state.weapon_states[slot]
        upgrades = state.weapon_upgrades.get(weapon_id, {})
        burst_length = weapon.get("fire_duration", 0.0) + upgrades.get("fire_duration_bonus", 0.0)

        # Mirror Shield: an on/off ability with no bullets.
        if weapon_id == "mirror_shield":
            if weapon_state["firing"] > 0:
                weapon_state["firing"] = max(0.0, weapon_state["firing"] - dt)
                if weapon_state["firing"] == 0:
                    weapon_state["cooldown"] = weapon["cooldown"] * multiplier
            else:
                weapon_state["cooldown"] = max(0.0, weapon_state["cooldown"] - dt)
                if weapon_state["cooldown"] == 0:
                    weapon_state["firing"] = burst_length
            continue

        if weapon_state["firing"] > 0:
            weapon_state["firing"] -= dt
            weapon_state["shot_timer"] -= dt
            if weapon_state["firing"] <= 0:
                weapon_state["firing"] = 0.0
                weapon_state["cooldown"] = weapon["cooldown"] * multiplier
                should_fire = False
            else:
                should_fire = weapon_state["shot_timer"] <= 0
        else:
            weapon_state["cooldown"] = max(0.0, weapon_state["cooldown"] - dt)
            should_fire = weapon_state["cooldown"] <= 0

        if not should_fire:
            continue
        target = nearest_target(state, state.stats["weapon_range"])
        if target is None:
            continue
        fire_weapon(state, weapon_id, target)
        rate_multiplier = upgrades.get("fire_rate_multiplier", 1.0)
        if weapon.get("fire_duration"):
            if weapon_state["firing"] <= 0:
                weapon_state["firing"] = burst_length
            weapon_state["shot_timer"] = weapon["fire_rate"] * multiplier * rate_multiplier
        else:
            weapon_state["cooldown"] = weapon["cooldown"] * multiplier * rate_multiplier


def shield_is_active(state) -> bool:
    return any(
        weapon_id == "mirror_shield" and state.weapon_states[slot]["firing"] > 0
        for slot, weapon_id in enumerate(state.weapon_slots)
    )


def reflect_enemy_bullets(state) -> None:
    """While the Mirror Shield is up, turn every incoming bullet back at its shooter."""
    if not shield_is_active(state):
        return
    bonus = state.weapon_upgrades.get("mirror_shield", {}).get("reflect_speed_bonus", 0.0)
    multiplier = 2.0 + bonus
    for projectile in state.projectiles:
        source = projectile.get("source")
        if projectile["reflected"] or source is None:
            continue
        dx = source.x - projectile["x"]
        dy = source.y - projectile["y"]
        distance = math.hypot(dx, dy) or 1.0
        speed = math.hypot(projectile["vx"], projectile["vy"]) * multiplier
        projectile["vx"] = dx / distance * speed
        projectile["vy"] = dy / distance * speed
        projectile["reflected"] = True
        projectile["color"] = (120, 225, 255)
        projectile["char"] = "*"


# ============================================================
# 3) BULLET TRAVEL AND HITS
# ============================================================
def chain_targets(state, first, bullet: dict) -> list:
    """Enemies hit by one bullet: a blast radius, or a chain of nearest neighbours."""
    radius = bullet.get("explosion_radius", 0.0)
    if radius > 0:
        return [e for e in state.enemies if math.hypot(e.x - bullet["x"], e.y - bullet["y"]) <= radius]

    targets = [first]
    for _ in range(bullet.get("chain_count", 0)):
        candidates = [e for e in state.enemies if e not in targets]
        if not candidates:
            break
        last = targets[-1]
        nearest = min(candidates, key=lambda e: math.hypot(e.x - last.x, e.y - last.y))
        if math.hypot(nearest.x - last.x, nearest.y - last.y) > bullet.get("chain_range", 0.0):
            break
        targets.append(nearest)
    return targets


def out_of_bounds(x: float, y: float) -> bool:
    return x < 0 or y < 0 or x >= config.SCREEN_WIDTH or y >= config.SCREEN_HEIGHT


def update_player_bullets(state, dt: float) -> None:
    for bullet in list(state.player_bullets):
        bullet["x"] += bullet["vx"] * dt
        bullet["y"] += bullet["vy"] * dt
        cell = (int(bullet["x"]), int(bullet["y"]))

        if out_of_bounds(*cell):
            state.player_bullets.remove(bullet)
            continue

        # Light enemy bullets are shot down; heavy (tank / boss) ones are not.
        cancelled = next(
            (p for p in state.projectiles
             if not p["heavy"] and not p["reflected"] and (int(p["x"]), int(p["y"])) == cell),
            None,
        )
        if cancelled is not None:
            state.projectiles.remove(cancelled)
            state.player_bullets.remove(bullet)
            continue

        hit = next((e for e in state.enemies if e.cell() == cell), None)
        if hit is not None:
            state.player_bullets.remove(bullet)
            if tank_blocks(hit, bullet["vx"], bullet["vy"]) and bullet.get("explosion_radius", 0) <= 0:
                spawn_spark(state.effects, bullet["x"], bullet["y"])
                continue
            damage_enemies(state, chain_targets(state, hit, bullet), bullet["damage"])
            if state.boss is not None and bullet.get("explosion_radius", 0) > 0 \
                    and boss_near(state.boss, bullet["x"], bullet["y"], bullet["explosion_radius"]):
                damage_boss(state, bullet["damage"])
            continue

        if state.boss is not None and cell in boss_cells(state.boss):
            state.player_bullets.remove(bullet)
            damage_boss(state, bullet["damage"])
            if bullet.get("explosion_radius", 0) > 0:
                damage_enemies(state, chain_targets(state, None, bullet), bullet["damage"])
