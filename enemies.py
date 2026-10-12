"""enemies.py - every regular enemy: spawning waves, per-kind behavior,
enemy bullets, taking damage and dying.

Kinds (stats in config.ENEMY_TYPES):
    normal    green crab, stands still and shoots
    elite     magenta squid, stands still and shoots harder
    dasher    waits, telegraphs a line, then charges along it
    sniper    keeps 15-20 tiles away, draws an aim line, fires a fast shot
    splitter  slow creeper that splits into two splitlings on death
    splitling small fast chaser spawned by a splitter
    tank      slow brute with a front shield that blocks bullets

Boss waves are handled in boss.py; this module only decides *when* a wave is
a boss wave (start_wave) and hands off.
"""
import math
import random
from dataclasses import dataclass

import config
import save
from effects import spawn_damage_number, spawn_explosion
from player import add_income, create_drop, damage_player, gain_xp, player_center


@dataclass
class Enemy:
    kind: str
    x: float
    y: float
    hp: int
    max_hp: int
    cooldown: float = 0.0       # seconds until the next shot / action
    state: str = "idle"         # dasher: wait/telegraph/charge  sniper: move/aim/recover
    timer: float = 0.0          # seconds left in the current state
    vx: float = 0.0             # dasher charge velocity
    vy: float = 0.0
    facing: float = 0.0         # tank shield direction (radians)
    aim_x: float = 0.0          # telegraph end point (dasher / sniper)
    aim_y: float = 0.0
    charge_left: float = 0.0    # dasher: distance still to travel
    flash: float = 0.0          # hit flash seconds left

    @property
    def stats(self) -> dict:
        return config.ENEMY_TYPES[self.kind]

    def cell(self) -> tuple[int, int]:
        return int(self.x), int(self.y)


# ============================================================
# 1) SPAWNING
# ============================================================
def wave_enemy_count(wave: int) -> int:
    return config.WAVE_BASE_ENEMIES + config.WAVE_ENEMIES_PER_WAVE * wave


def is_boss_wave(wave: int) -> bool:
    return wave % config.BOSS_WAVE_INTERVAL == 0


def enemy_hp(kind: str, wave: int) -> int:
    base = config.ENEMY_TYPES[kind]["hp"]
    if kind == "splitling":
        return base
    return base + (wave - 1) // config.ENEMY_HP_BONUS_EVERY_WAVES


def make_enemy(kind: str, x: float, y: float, wave: int) -> Enemy:
    stats = config.ENEMY_TYPES[kind]
    hp = enemy_hp(kind, wave)
    enemy = Enemy(kind=kind, x=float(x), y=float(y), hp=hp, max_hp=hp)
    if kind in ("normal", "elite", "tank"):
        enemy.cooldown = random.uniform(*stats["shoot_cooldown"])
    elif kind == "dasher":
        enemy.state = "wait"
        enemy.timer = random.uniform(*stats["wait_seconds"])
    elif kind == "sniper":
        enemy.state = "move"
        enemy.timer = stats["recover_seconds"] * 0.5
    return enemy


def pick_enemy_kind(wave: int) -> str:
    kinds, weights = [], []
    for kind, stats in config.ENEMY_TYPES.items():
        if wave < stats["min_wave"]:
            continue
        weight = stats["weight"] + stats["weight_per_wave"] * (wave - stats["min_wave"])
        if weight > 0:
            kinds.append(kind)
            weights.append(weight)
    return random.choices(kinds, weights=weights, k=1)[0]


def random_spawn_cell(player_x: float, player_y: float) -> tuple[int, int]:
    """A cell inside the arena, not too close to the player. Gives up after 50 tries."""
    margin = config.ARENA_MARGIN
    best = None
    for _ in range(50):
        x = random.randint(margin, config.SCREEN_WIDTH - 1 - margin)
        y = random.randint(config.HUD_ROWS + margin, config.SCREEN_HEIGHT - 1 - margin)
        if abs(x - player_x) > config.SPAWN_KEEPOUT and abs(y - player_y) > config.SPAWN_KEEPOUT:
            return x, y
        best = (x, y)
    return best


def note_seen(state, kind: str) -> None:
    """Unlock `kind` in the encyclopedia. Saves right away the first time."""
    if kind in state.seen_kinds:
        return
    state.seen_kinds.add(kind)
    save.write_save(state.highscore, state.seen_kinds)


def start_wave(state) -> None:
    """Fill the arena for state.wave. Boss waves spawn a boss and nothing else."""
    import boss as boss_module  # imported here to keep the module graph one-way

    state.enemies.clear()
    state.projectiles.clear()
    state.player_bullets.clear()
    state.kills_this_wave = 0
    state.boss = None
    if is_boss_wave(state.wave):
        state.boss = boss_module.spawn_boss(state.wave)
        state.wave_total = 1
        note_seen(state, "boss")
        return
    count = wave_enemy_count(state.wave)
    for _ in range(count):
        x, y = random_spawn_cell(state.px, state.py)
        kind = pick_enemy_kind(state.wave)
        state.enemies.append(make_enemy(kind, x, y, state.wave))
        note_seen(state, kind)
    state.wave_total = count


def wave_is_cleared(state) -> bool:
    """The single definition of 'wave over': nothing left alive."""
    return not state.enemies and state.boss is None


# ============================================================
# 2) ENEMY BULLETS
# ============================================================
def fire_at(state, source, target_x: float, target_y: float, speed: float, damage: int,
            char: str = "o", color=(255, 230, 80), heavy: bool = False) -> dict:
    """Spawn an enemy bullet from `source` (an Enemy or Boss) toward a point."""
    dx = target_x - source.x
    dy = target_y - source.y
    dist = math.hypot(dx, dy) or 1.0
    projectile = {
        "x": source.x,
        "y": source.y,
        "vx": dx / dist * speed,
        "vy": dy / dist * speed,
        "damage": damage,
        "source": source,
        "char": char,
        "color": color,
        "heavy": heavy,          # heavy bullets are not cancelled by player bullets
        "reflected": False,
    }
    state.projectiles.append(projectile)
    return projectile


def out_of_bounds(x: float, y: float) -> bool:
    return x < 0 or y < 0 or x >= config.SCREEN_WIDTH or y >= config.SCREEN_HEIGHT


def update_enemy_projectiles(state, dt: float) -> None:
    """Move enemy bullets; hit the player, or if reflected, hit enemies/boss."""
    import boss as boss_module

    player = (int(state.px), int(state.py))
    for projectile in list(state.projectiles):
        projectile["x"] += projectile["vx"] * dt
        projectile["y"] += projectile["vy"] * dt
        cell = (int(projectile["x"]), int(projectile["y"]))

        if out_of_bounds(*cell):
            state.projectiles.remove(projectile)
            continue

        if projectile["reflected"]:
            hit = next((enemy for enemy in state.enemies if enemy.cell() == cell), None)
            if hit is not None:
                state.projectiles.remove(projectile)
                damage_enemies(state, [hit], projectile["damage"])
            elif state.boss is not None and cell in boss_module.boss_cells(state.boss):
                state.projectiles.remove(projectile)
                boss_module.damage_boss(state, projectile["damage"])
            continue

        if cell == player:
            state.projectiles.remove(projectile)
            damage_player(state, projectile["damage"])
            if state.mode != "playing":
                return


# ============================================================
# 3) PER-KIND BEHAVIOR
# ============================================================
def move_toward(enemy: Enemy, target_x: float, target_y: float, speed: float, dt: float) -> None:
    dx = target_x - enemy.x
    dy = target_y - enemy.y
    dist = math.hypot(dx, dy)
    if dist < 0.01:
        return
    step = min(speed * dt, dist)
    enemy.x += dx / dist * step
    enemy.y += dy / dist * step


def clamp_to_arena(enemy: Enemy) -> None:
    enemy.x = max(0.0, min(enemy.x, config.SCREEN_WIDTH - 1))
    enemy.y = max(float(config.HUD_ROWS), min(enemy.y, config.SCREEN_HEIGHT - 1))


def update_shooter(state, enemy: Enemy, dt: float) -> None:
    """normal / elite: stand still, fire at the player on a timer."""
    enemy.cooldown -= dt
    if enemy.cooldown <= 0:
        stats = enemy.stats
        color = (240, 80, 130) if enemy.kind == "elite" else (255, 230, 80)
        fire_at(state, enemy, *player_center(state), stats["bullet_speed"], stats["bullet_damage"], color=color)
        enemy.cooldown = random.uniform(*stats["shoot_cooldown"])


def update_dasher(state, enemy: Enemy, dt: float) -> None:
    """wait (drift closer) -> telegraph (line locked on the player) -> charge."""
    stats = enemy.stats
    enemy.timer -= dt
    if enemy.state == "wait":
        move_toward(enemy, state.px, state.py, stats["drift_speed"], dt)
        if enemy.timer <= 0:
            enemy.state = "telegraph"
            enemy.timer = stats["telegraph_seconds"]
            dx = state.px - enemy.x
            dy = state.py - enemy.y
            dist = math.hypot(dx, dy) or 1.0
            overshoot = dist + stats["charge_overshoot"]
            enemy.aim_x = enemy.x + dx / dist * overshoot
            enemy.aim_y = enemy.y + dy / dist * overshoot
            enemy.vx = dx / dist * stats["charge_speed"]
            enemy.vy = dy / dist * stats["charge_speed"]
            enemy.charge_left = overshoot
    elif enemy.state == "telegraph":
        if enemy.timer <= 0:
            enemy.state = "charge"
    elif enemy.state == "charge":
        step = min(stats["charge_speed"] * dt, enemy.charge_left)
        enemy.x += enemy.vx / stats["charge_speed"] * step
        enemy.y += enemy.vy / stats["charge_speed"] * step
        enemy.charge_left -= step
        before = (enemy.x, enemy.y)
        clamp_to_arena(enemy)
        hit_wall = before != (enemy.x, enemy.y)
        if enemy.charge_left <= 0 or hit_wall:
            enemy.state = "wait"
            enemy.timer = random.uniform(*stats["wait_seconds"])


def update_sniper(state, enemy: Enemy, dt: float) -> None:
    """Keep 15-20 tiles away. Aim for 1 s (line tracks the player, then locks), fire, recover."""
    stats = enemy.stats
    dist = math.hypot(state.px - enemy.x, state.py - enemy.y)
    enemy.timer -= dt

    if enemy.state == "move":
        if dist < stats["min_range"]:
            # back away from the player
            move_toward(enemy, 2 * enemy.x - state.px, 2 * enemy.y - state.py, stats["move_speed"], dt)
            clamp_to_arena(enemy)
        elif dist > stats["max_range"]:
            move_toward(enemy, state.px, state.py, stats["move_speed"], dt)
        if enemy.timer <= 0 and stats["min_range"] <= dist <= stats["max_range"] + 2:
            enemy.state = "aim"
            enemy.timer = stats["aim_seconds"]
    elif enemy.state == "aim":
        if enemy.timer > stats["aim_lock_seconds"]:
            enemy.aim_x, enemy.aim_y = player_center(state)
        if enemy.timer <= 0:
            fire_at(state, enemy, enemy.aim_x, enemy.aim_y, stats["bullet_speed"], stats["bullet_damage"],
                    char="-", color=(200, 150, 255))
            enemy.state = "recover"
            enemy.timer = stats["recover_seconds"]
    elif enemy.state == "recover":
        if enemy.timer <= 0:
            enemy.state = "move"
            enemy.timer = 0.3


def update_chaser(state, enemy: Enemy, dt: float) -> None:
    """splitter / splitling: walk straight at the player."""
    move_toward(enemy, state.px, state.py, enemy.stats["move_speed"], dt)


def update_tank(state, enemy: Enemy, dt: float) -> None:
    """Crawl forward, turn the shield toward the player, lob a heavy shot now and then."""
    stats = enemy.stats
    move_toward(enemy, state.px, state.py, stats["move_speed"], dt)

    wanted = math.atan2(state.py - enemy.y, state.px - enemy.x)
    diff = (wanted - enemy.facing + math.pi) % math.tau - math.pi
    max_turn = stats["turn_rate"] * dt
    enemy.facing += max(-max_turn, min(max_turn, diff))

    enemy.cooldown -= dt
    if enemy.cooldown <= 0:
        fire_at(state, enemy, *player_center(state), stats["bullet_speed"], stats["bullet_damage"],
                char="O", color=(150, 190, 255), heavy=True)
        enemy.cooldown = random.uniform(*stats["shoot_cooldown"])


def tank_blocks(enemy: Enemy, bullet_vx: float, bullet_vy: float) -> bool:
    """True if a bullet travelling (vx, vy) arrives inside the tank's shield arc."""
    if enemy.kind != "tank":
        return False
    incoming = math.atan2(-bullet_vy, -bullet_vx)       # direction the bullet came from
    diff = abs((incoming - enemy.facing + math.pi) % math.tau - math.pi)
    return diff <= math.radians(enemy.stats["shield_half_angle_deg"])


UPDATERS = {
    "normal": update_shooter,
    "elite": update_shooter,
    "dasher": update_dasher,
    "sniper": update_sniper,
    "splitter": update_chaser,
    "splitling": update_chaser,
    "tank": update_tank,
}


def update_enemies(state, dt: float) -> None:
    player = (int(state.px), int(state.py))
    for enemy in list(state.enemies):
        if enemy.flash > 0.0:
            enemy.flash = max(0.0, enemy.flash - dt)
        UPDATERS[enemy.kind](state, enemy, dt)
        contact = enemy.stats["contact_damage"]
        if contact and enemy.cell() == player:
            damage_player(state, contact)
            if state.mode != "playing":
                return


# ============================================================
# 4) TAKING DAMAGE AND DYING
# ============================================================
def damage_enemies(state, targets: list[Enemy], damage: int) -> list[Enemy]:
    """Apply damage, flash, remove the dead, pay out rewards. Returns the killed list."""
    killed = []
    for enemy in targets:
        if enemy not in state.enemies:
            continue
        enemy.hp -= damage
        enemy.flash = config.HIT_FLASH_SECONDS
        spawn_damage_number(state.effects, enemy.x, enemy.y, damage)
        if enemy.hp <= 0:
            killed.append(enemy)
    for enemy in killed:
        kill_enemy(state, enemy)
    return killed


def kill_enemy(state, enemy: Enemy) -> None:
    """The one place a kill is paid out: score, points, XP, drops, splits."""
    state.enemies.remove(enemy)
    state.kills_this_wave += 1
    add_income(state, enemy.stats["reward"])
    gain_xp(state, config.ENEMY_XP[enemy.kind])
    spawn_explosion(state.effects, enemy.x, enemy.y, count=6, scale=0.6)

    if random.random() < config.DROP_CHANCE:
        state.drops.append(create_drop(enemy.x, enemy.y))

    if enemy.kind == "splitter":
        count = enemy.stats["split_count"]
        for index in range(count):
            offset = -1.0 + 2.0 * index / max(1, count - 1)      # spread -1 .. +1
            child = make_enemy("splitling", enemy.x + offset, enemy.y, state.wave)
            clamp_to_arena(child)
            state.enemies.append(child)
            state.wave_total += 1
        note_seen(state, "splitling")
