"""encyclopedia.py - the enemy encyclopedia, reachable from the main menu.

Owns the entry order, display names and the short tactics blurbs. Every
number shown (hp, speed, reward, first wave) is read from config.py at call
time so the screen can never go stale when the balance tables change.

An entry is locked until the player has met that kind in any run; game.py
keeps the set in `state.seen_kinds` and save.py persists it.
"""
import config

# Order the list is shown in. "boss" is not in config.ENEMY_TYPES; its
# numbers come from the BOSS_* constants.
ENTRY_ORDER = ("normal", "elite", "dasher", "sniper", "splitter", "splitling", "tank", "boss")

NAMES = {
    "normal": "Crab",
    "elite": "Squid",
    "dasher": "Dasher",
    "sniper": "Sniper",
    "splitter": "Splitter",
    "splitling": "Splitling",
    "tank": "Tank",
    "boss": "Overlord",
}

# 2-3 short lines each. Keep every line under 44 characters so it fits the panel.
BLURBS = {
    "normal": (
        "Sits still and lobs slow shots.",
        "Free points. Thin them out first",
        "so the arena stops raining.",
    ),
    "elite": (
        "Shoots faster and hits for 2.",
        "Kill it before the crabs. Its pink",
        "bullets can be cancelled by yours.",
    ),
    "dasher": (
        "Drifts in, draws an orange line,",
        "then charges along it. Step off the",
        "line and shoot it as it flies past.",
    ),
    "sniper": (
        "Hangs back 15-20 tiles. Its aim line",
        "turns red when it locks. Move after",
        "the lock, then close in and finish it.",
    ),
    "splitter": (
        "Slow blob. Splits into 2 splitlings",
        "when it dies. Kill it at range, never",
        "point blank.",
    ),
    "splitling": (
        "Fast, fragile chaser. Only spawns",
        "from a dead splitter. Keep moving",
        "and let auto-fire clean them up.",
    ),
    "tank": (
        "Front shield eats bullets. Strafe",
        "around it or drop a Mega Bomb. Its",
        "heavy shots cannot be cancelled.",
    ),
    "boss": (
        "Rings, then spirals, then aimed fans",
        "as its hp drops. Buy a real gun before",
        "wave 5. Mirror Shield bounces it all.",
    ),
}


def entry_stats(kind: str) -> dict:
    """Display strings for one entry, built from config.py."""
    if kind == "boss":
        first_boss_hp = config.BOSS_BASE_HP + config.BOSS_HP_PER_WAVE * config.BOSS_WAVE_INTERVAL
        speeds = [config.BOSS_PATTERNS[phase]["move_speed"] for phase in (1, 2, 3)]
        return {
            "hp": f"{first_boss_hp} (+{config.BOSS_HP_PER_WAVE} per wave)",
            "speed": " / ".join(f"{speed:g}" for speed in speeds) + " by phase",
            "reward": f"{config.BOSS_REWARD_BASE} +{config.BOSS_REWARD_PER_WAVE} per wave",
            "first_wave": f"{config.BOSS_WAVE_INTERVAL} (every {config.BOSS_WAVE_INTERVAL}th wave)",
        }

    stats = config.ENEMY_TYPES[kind]
    if kind == "splitling":
        hp = f"{stats['hp']}"
        first_wave = f"{config.ENEMY_TYPES['splitter']['min_wave']} (from splitters)"
    else:
        hp = f"{stats['hp']} (+1 every {config.ENEMY_HP_BONUS_EVERY_WAVES} waves)"
        first_wave = f"{stats['min_wave']}"

    if kind == "dasher":
        speed = f"{stats['drift_speed']:g} drift, {stats['charge_speed']:g} charge"
    elif "move_speed" in stats:
        speed = f"{stats['move_speed']:g}"
    else:
        speed = "0 (stationary)"

    return {"hp": hp, "speed": speed, "reward": f"{stats['reward']}", "first_wave": first_wave}


def entry_name(kind: str, unlocked: bool) -> str:
    return NAMES[kind] if unlocked else "???"


def discovered_count(seen_kinds) -> int:
    return sum(1 for kind in ENTRY_ORDER if kind in seen_kinds)
