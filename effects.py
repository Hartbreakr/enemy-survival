"""effects.py - juice: explosion particles, screen shake, damage numbers,
line drawing for telegraphs.

Nothing in here changes gameplay. Everything lives in one Effects object that
the game state carries around, so the simulation can run with no window.
"""
import math
import random
from dataclasses import dataclass, field

import config


@dataclass
class Effects:
    particles: list = field(default_factory=list)
    damage_numbers: list = field(default_factory=list)
    shake_time: float = 0.0        # seconds of shake left
    shake_strength: float = 0.0    # max jitter in tiles


# ============================================================
# 1) EXPLOSIONS
# ============================================================
def spawn_explosion(effects: Effects, x: float, y: float, count: int = 16, scale: float = 1.0) -> None:
    """Burst of flying debris. scale > 1 makes it bigger and longer (boss death)."""
    for _ in range(count):
        angle = random.uniform(0.0, math.tau)
        speed = random.uniform(5.0, 15.0) * scale
        lifetime = random.uniform(0.35, 0.85) * scale
        effects.particles.append(
            {
                "x": x,
                "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": lifetime,
                "max_life": lifetime,
                "char": random.choice(("*", "+", "o", "x")),
            }
        )
    effects.particles.append(
        {"x": x, "y": y, "vx": 0.0, "vy": 0.0, "life": 0.4 * scale, "max_life": 0.4 * scale, "char": "#"}
    )


def spawn_spark(effects: Effects, x: float, y: float) -> None:
    """Tiny puff used when a tank shield blocks a bullet."""
    spawn_explosion(effects, x, y, count=3, scale=0.5)


# ============================================================
# 2) SCREEN SHAKE AND DAMAGE NUMBERS
# ============================================================
def add_shake(effects: Effects, strength: float) -> None:
    effects.shake_time = config.SHAKE_SECONDS
    effects.shake_strength = max(effects.shake_strength, strength)


def shake_offset(effects: Effects) -> tuple[int, int]:
    """Whole-console jitter for this frame, in tiles. Decays to zero."""
    if effects.shake_time <= 0.0:
        return 0, 0
    strength = effects.shake_strength * effects.shake_time / config.SHAKE_SECONDS
    return round(random.uniform(-strength, strength)), round(random.uniform(-strength, strength))


def spawn_damage_number(effects: Effects, x: float, y: float, amount: int) -> None:
    effects.damage_numbers.append(
        {"x": x, "y": y - 1, "text": str(amount), "life": config.DAMAGE_NUMBER_SECONDS}
    )


# ============================================================
# 3) PER-STEP UPDATE
# ============================================================
def update_effects(effects: Effects, dt: float) -> None:
    for particle in list(effects.particles):
        particle["x"] += particle["vx"] * dt
        particle["y"] += particle["vy"] * dt
        particle["life"] -= dt
        if particle["life"] <= 0:
            effects.particles.remove(particle)

    for number in list(effects.damage_numbers):
        number["y"] -= 2.0 * dt
        number["life"] -= dt
        if number["life"] <= 0:
            effects.damage_numbers.remove(number)

    if effects.shake_time > 0.0:
        effects.shake_time = max(0.0, effects.shake_time - dt)
        if effects.shake_time == 0.0:
            effects.shake_strength = 0.0


# ============================================================
# 4) LINE HELPER (laser beam, dasher and sniper telegraphs)
# ============================================================
def line_cells(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Bresenham line from (x0, y0) to (x1, y1), both ends included."""
    cells = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x_step = 1 if x0 < x1 else -1
    y_step = 1 if y0 < y1 else -1
    error = dx - dy
    x, y = x0, y0
    while True:
        cells.append((x, y))
        if x == x1 and y == y1:
            return cells
        doubled = 2 * error
        if doubled > -dy:
            error -= dy
            x += x_step
        if doubled < dx:
            error += dx
            y += y_step


def line_glyph(x0: int, y0: int, x1: int, y1: int) -> str:
    """Pick -, |, / or \\ to match the slope of a line."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    if dx >= 2 * dy:
        return "-"
    if dy >= 2 * dx:
        return "|"
    return "\\" if (x1 - x0) * (y1 - y0) > 0 else "/"


# ============================================================
# 5) DRAWING
# ============================================================
def particle_color(remaining: float) -> tuple[int, int, int]:
    if remaining > 0.7:
        return (255, 255, 255)
    if remaining > 0.4:
        return (255, 220, 80)
    if remaining > 0.2:
        return (255, 140, 50)
    return (200, 60, 40)


def draw_effects(console, effects: Effects) -> None:
    for particle in effects.particles:
        x, y = int(particle["x"]), int(particle["y"])
        if 0 <= x < console.width and 0 <= y < console.height:
            remaining = particle["life"] / particle["max_life"]
            console.print(x=x, y=y, string=particle["char"], fg=particle_color(remaining))
    for number in effects.damage_numbers:
        x, y = int(number["x"]), int(number["y"])
        if 0 <= x < console.width - len(number["text"]) and 0 <= y < console.height:
            console.print(x=x, y=y, string=number["text"], fg=(255, 240, 160))
