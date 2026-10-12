"""ui.py - everything that draws: HUD, menu, encyclopedia, game over, shop,
level-up menu and the arena itself.

Only this module and main.py know about the console. Every function takes
the console and the GameState and prints; nothing in here changes the state.
"""
import math

import config
from boss import boss_cells, boss_phase
from effects import draw_effects, line_cells, line_glyph
from encyclopedia import BLURBS, ENTRY_ORDER, discovered_count, entry_name, entry_stats
from player import drop_is_flashing, player_is_visible
from shop import get_shop_items, slot_number
from sprites import (
    ALIEN_ELITE_CODEPOINT,
    ALIEN_NORMAL_CODEPOINT,
    BOSS_CODEPOINTS,
    DASHER_CODEPOINT,
    ENEMY_CODEPOINTS,
    HEART_EMPTY_CODEPOINT,
    HEART_FULL_CODEPOINT,
    SHIP_CODEPOINTS,
    TANK_CODEPOINT,
    flash_codepoint,
)
from weapons import get_weapon, nearest_target, shield_is_active, weapon_readiness

WHITE = (255, 255, 255)
GREY = (180, 180, 180)
DIM = (90, 100, 110)
GOLD = (255, 215, 0)
CYAN = (120, 220, 255)
SKY = (150, 220, 255)
GREEN = (90, 225, 145)
RED = (255, 80, 80)
# Sprites are printed with a white foreground: tcod multiplies a colored tile
# by the print color, so anything else would tint the pixel art.
SHIP_TINT = WHITE
PANEL_BG = (15, 20, 30)

DROP_LOOKS = {
    "health": ("+", (80, 255, 140)),
    "points": ("*", GOLD),
    "triple_shot": ("3", (180, 120, 255)),
    "shield": ("S", (120, 225, 255)),
    "cash_grab": ("$", (255, 140, 70)),
}


def on_screen(x: int, y: int) -> bool:
    return 0 <= x < config.SCREEN_WIDTH and 0 <= y < config.SCREEN_HEIGHT


def put(console, x: int, y: int, text: str, fg=WHITE) -> None:
    if on_screen(x, y):
        console.print(x=x, y=y, string=text, fg=fg)


def put_centered(console, y: int, text: str, fg=WHITE) -> None:
    put(console, config.SCREEN_WIDTH // 2 - len(text) // 2, y, text, fg)


def draw_line(console, x0: int, y0: int, x1: int, y1: int, fg, skip_first: bool = True) -> None:
    glyph = line_glyph(x0, y0, x1, y1)
    for index, (x, y) in enumerate(line_cells(x0, y0, x1, y1)):
        if skip_first and index == 0:
            continue
        put(console, x, y, glyph, fg)


# ============================================================
# 1) TOP-LEVEL DISPATCH
# ============================================================
def draw_frame(console, state) -> None:
    if state.mode == "menu":
        draw_menu(console, state)
    elif state.mode == "encyclopedia":
        draw_encyclopedia(console, state)
    elif state.mode == "gameover":
        draw_gameover(console, state)
    elif state.mode == "dying":
        draw_arena(console, state, draw_player=False)
        put(console, 1, 1, f"SCORE {state.score}", WHITE)
    elif state.shop_open:
        draw_shop(console, state)
    else:
        draw_arena(console, state)
        draw_hud(console, state)
        if state.level_up_open:
            draw_level_up(console, state)


# ============================================================
# 2) MENU, ENCYCLOPEDIA AND GAME OVER
# ============================================================
def draw_menu(console, state) -> None:
    cx = config.SCREEN_WIDTH // 2
    put_centered(console, 8, config.GAME_TITLE, CYAN)
    put_centered(console, 10, "a retro arena shooter", GREY)
    # ship flanked by aliens
    put(console, cx - 12, 13, chr(ALIEN_NORMAL_CODEPOINT))
    put(console, cx - 7, 13, chr(DASHER_CODEPOINT))
    put(console, cx - 1, 13, chr(SHIP_CODEPOINTS[6]), SHIP_TINT)
    put(console, cx + 5, 13, chr(ALIEN_ELITE_CODEPOINT))
    put(console, cx + 10, 13, chr(TANK_CODEPOINT))

    found = discovered_count(state.seen_kinds)
    options = ("START", f"ENCYCLOPEDIA  {found}/{len(ENTRY_ORDER)}")
    for index, label in enumerate(options):
        selected = index == state.menu_index
        cursor = "> " if selected else "  "
        put(console, cx - 10, 17 + index * 2, cursor + label, GOLD if selected else GREY)
    put_centered(console, 21, "Up/Down choose   Enter pick   (Space also starts)", DIM)

    put_centered(console, 24, f"HIGH SCORE  {state.highscore}", WHITE)
    put_centered(console, 28, "WASD / Arrows : move      Shift : sprint", SKY)
    put_centered(console, 29, "Weapons auto-fire. Clear the wave to open the shop.", SKY)
    put_centered(console, 30, "Shop: Up/Down pick item   1-4 pick slot   Enter buy   Esc next wave", SKY)
    put_centered(console, 32, "Every 5th wave is a boss. Watch the red lines.", GREY)


def draw_encyclopedia(console, state) -> None:
    """Left: the list of kinds. Right: a detail panel for the highlighted one."""
    put_centered(console, 3, "- ENEMY ENCYCLOPEDIA -", GOLD)
    found = discovered_count(state.seen_kinds)
    put_centered(console, 5, f"{found}/{len(ENTRY_ORDER)} discovered", GREY)

    # list on the left
    list_x, list_y = 6, 9
    put(console, list_x, list_y - 2, "ENEMIES", GOLD)
    for index, kind in enumerate(ENTRY_ORDER):
        unlocked = kind in state.seen_kinds
        selected = index == state.codex_index
        cursor = ">" if selected else " "
        label = f"{cursor} {entry_name(kind, unlocked)}"
        color = GOLD if selected else (WHITE if unlocked else DIM)
        put(console, list_x, list_y + index * 2, label, color)

    # detail panel on the right
    kind = ENTRY_ORDER[state.codex_index]
    unlocked = kind in state.seen_kinds
    panel_x, panel_y, panel_w, panel_h = 24, 7, 50, 30
    console.draw_frame(x=panel_x, y=panel_y, width=panel_w, height=panel_h, fg=DIM, bg=PANEL_BG)
    text_x = panel_x + 8
    draw_codex_sprite(console, kind, panel_x + 2, panel_y + 2, unlocked)
    put(console, text_x, panel_y + 2, entry_name(kind, unlocked).upper(), GOLD if unlocked else DIM)

    if not unlocked:
        put(console, text_x, panel_y + 4, "Not yet encountered", DIM)
        put(console, text_x, panel_y + 6, "Meet one in a run to unlock this page.", DIM)
    else:
        stats = entry_stats(kind)
        rows = (
            ("HP", stats["hp"]),
            ("SPEED", stats["speed"]),
            ("REWARD", stats["reward"]),
            ("FIRST WAVE", stats["first_wave"]),
        )
        for row, (label, value) in enumerate(rows):
            y = panel_y + 7 + row
            put(console, text_x, y, f"{label:<11}", SKY)
            put(console, text_x + 12, y, value, WHITE)
        for row, line in enumerate(BLURBS[kind]):
            put(console, panel_x + 3, panel_y + 14 + row, line, GREY)

    put_centered(console, 42, "Up/Down browse   Esc back to menu", SKY)


def draw_codex_sprite(console, kind: str, x: int, y: int, unlocked: bool) -> None:
    """The enemy's sprite (boss as its 3x3 block), or '?' when locked."""
    if kind == "boss":
        for index, codepoint in enumerate(BOSS_CODEPOINTS):
            glyph = chr(codepoint) if unlocked else "?"
            put(console, x + index % 3, y + index // 3, glyph, WHITE if unlocked else DIM)
        return
    if unlocked:
        put(console, x + 1, y + 1, chr(ENEMY_CODEPOINTS[kind]), WHITE)
    else:
        put(console, x + 1, y + 1, "?", DIM)


def draw_gameover(console, state) -> None:
    put_centered(console, 10, "GAME OVER", RED)
    put_centered(console, 14, f"SCORE  {state.score}", WHITE)
    if state.new_highscore:
        put_centered(console, 16, "NEW HIGH SCORE!", GOLD)
    put_centered(console, 18, f"HIGH SCORE  {state.highscore}", GREY)
    put_centered(console, 20, f"Reached wave {state.wave} at level {state.level}", GREY)
    put_centered(console, 24, "ENTER  -  play again", WHITE)
    put_centered(console, 26, "ESC    -  main menu", GREY)


# ============================================================
# 3) THE ARENA
# ============================================================
def draw_arena(console, state, draw_player: bool = True) -> None:
    put(console, state.pickup_x, state.pickup_y, "*", (0, 255, 0))

    for drop in state.drops:
        if drop_is_flashing(drop) and int(drop["age"] * 8) % 2 == 0:
            continue
        char, color = DROP_LOOKS.get(drop["type"], ("?", WHITE))
        x, y = int(drop["x"]), int(drop["y"])
        put(console, x, y, char, color)
        if drop["type"] == "health":
            put(console, x + 1, y, str(max(0, int(config.DROP_LIFETIME - drop["age"]))), (150, 255, 180))

    for enemy in state.enemies:
        draw_telegraph(console, enemy)
    for enemy in state.enemies:
        codepoint = ENEMY_CODEPOINTS[enemy.kind]
        if enemy.flash > 0:
            codepoint = flash_codepoint(codepoint)
        put(console, *enemy.cell(), chr(codepoint), WHITE)
        if enemy.kind == "tank":
            draw_tank_shield(console, enemy)

    if state.boss is not None:
        draw_boss(console, state.boss)

    for projectile in state.projectiles:
        put(console, int(projectile["x"]), int(projectile["y"]), projectile["char"], projectile["color"])

    draw_laser_beams(console, state)
    if shield_is_active(state):
        px, py = int(state.px), int(state.py)
        for dx, dy, glyph in ((-1, 0, "("), (1, 0, ")"), (0, -1, "-"), (0, 1, "-")):
            put(console, px + dx, py + dy, glyph, (120, 225, 255))

    for bullet in state.player_bullets:
        if bullet["weapon_id"] != "laser":
            put(console, int(bullet["x"]), int(bullet["y"]), bullet["char"], bullet["color"])

    if draw_player and player_is_visible(state):
        put(console, int(state.px), int(state.py), chr(SHIP_CODEPOINTS[state.ship_index]), SHIP_TINT)

    draw_effects(console, state.effects)


def draw_telegraph(console, enemy) -> None:
    """Dasher charge line (orange) and sniper aim line (purple, red when locked)."""
    x, y = enemy.cell()
    if enemy.kind == "dasher" and enemy.state == "telegraph":
        draw_line(console, x, y, int(enemy.aim_x), int(enemy.aim_y), (255, 140, 30))
    elif enemy.kind == "sniper" and enemy.state == "aim":
        locked = enemy.timer <= enemy.stats["aim_lock_seconds"]
        color = (255, 60, 60) if locked else (140, 90, 200)
        draw_line(console, x, y, int(enemy.aim_x), int(enemy.aim_y), color)


def draw_tank_shield(console, enemy) -> None:
    """A bar on the side of the tank that faces the player."""
    dx = round(math.cos(enemy.facing))
    dy = round(math.sin(enemy.facing))
    if dx == 0 and dy == 0:
        return
    if dx == 0:
        glyph = "="
    elif dy == 0:
        glyph = "|"
    else:
        glyph = "\\" if dx * dy > 0 else "/"
    x, y = enemy.cell()
    put(console, x + dx, y + dy, glyph, (120, 190, 255))


def draw_boss(console, boss) -> None:
    for codepoint, (x, y) in zip(BOSS_CODEPOINTS, boss_cells(boss)):
        if boss.flash > 0:
            codepoint = flash_codepoint(codepoint)
        put(console, x, y, chr(codepoint), WHITE)


def draw_laser_beams(console, state) -> None:
    for slot, weapon_id in enumerate(state.weapon_slots):
        if weapon_id != "laser" or state.weapon_states[slot]["firing"] <= 0:
            continue
        target = nearest_target(state, state.stats["weapon_range"])
        if target is not None:
            draw_line(console, int(state.px), int(state.py), int(target.x), int(target.y), (255, 35, 50))


# ============================================================
# 4) HUD
# ============================================================
def draw_hud(console, state) -> None:
    draw_xp_bar(console, state)

    # row 1: score, hearts, wave, kills, points
    x = 1
    text = f"SCORE {state.score}"
    put(console, x, 1, text, WHITE)
    x += len(text) + 2
    for index in range(state.stats["max_health"]):
        heart = HEART_FULL_CODEPOINT if index < state.health else HEART_EMPTY_CODEPOINT
        put(console, x + index, 1, chr(heart), WHITE)
    x += state.stats["max_health"] + 2
    wave_text = f"WAVE {state.wave}"
    put(console, x, 1, wave_text, (255, 255, 0))
    x += len(wave_text) + 1
    if state.boss is not None:
        put(console, x, 1, "BOSS", RED)
        x += 5
    kills_text = f"KILLS {state.kills_this_wave}/{state.wave_total}"
    put(console, x, 1, kills_text, SKY)
    x += len(kills_text) + 2
    put(console, x, 1, f"PTS {state.points}", GOLD)

    # row 2: weapon slots with cooldown bars, then buffs
    x = 1
    for slot, weapon_id in enumerate(state.weapon_slots):
        if weapon_id is None:
            text = f"{slot + 1}:---"
            color = DIM
        else:
            weapon = get_weapon(weapon_id)
            weapon_state = state.weapon_states[slot]
            if weapon_state["firing"] > 0:
                bar = "ON "
            else:
                ready = weapon_readiness(weapon_id, weapon_state, state.stats["cooldown_multiplier"])
                filled = round(ready * 3)
                bar = "#" * filled + "." * (3 - filled)
            text = f"{slot + 1}:{weapon['short']} {bar}"
            color = weapon["color"] if (weapon_state["firing"] > 0 or bar == "###") else GREY
        put(console, x, 2, text, color)
        x += len(text) + 2
    for index in range(len(state.weapon_slots), 4):
        put(console, x, 2, f"{index + 1}:lock", DIM)
        x += 8
    if state.buffs:
        buff_text = "  ".join(f"{name.replace('_', ' ')} {left:.0f}s" for name, left in sorted(state.buffs.items()))
        put(console, x + 1, 2, buff_text, (200, 200, 255))

    if state.boss is not None:
        draw_boss_bar(console, state.boss)


def draw_xp_bar(console, state) -> None:
    bar_x = 12
    bar_width = config.SCREEN_WIDTH - bar_x - 2
    filled = min(bar_width, int(bar_width * state.xp / state.xp_needed))
    put(console, 1, 0, f"LVL {state.level}", GOLD)
    put(console, 8, 0, "XP", SKY)
    put(console, bar_x, 0, "-" * bar_width, (55, 65, 75))
    if filled:
        put(console, bar_x, 0, "#" * filled, GREEN)


def draw_boss_bar(console, boss) -> None:
    label = f"BOSS P{boss_phase(boss)} "
    bar_x = 1 + len(label)
    bar_width = config.SCREEN_WIDTH - bar_x - 8
    filled = int(bar_width * boss.hp / boss.max_hp)
    color = {1: (170, 60, 200), 2: (240, 80, 130), 3: (255, 70, 70)}[boss_phase(boss)]
    put(console, 1, 3, label, color)
    put(console, bar_x, 3, "-" * bar_width, (55, 65, 75))
    if filled:
        put(console, bar_x, 3, "#" * filled, color)
    put(console, bar_x + bar_width + 1, 3, f"{boss.hp:>5}", WHITE)


# ============================================================
# 5) LEVEL-UP MENU AND SHOP
# ============================================================
def draw_level_up(console, state) -> None:
    x, y = 22, 12
    width = 36
    console.draw_rect(x=x, y=y, width=width, height=11, ch=ord(" "), bg=(15, 20, 30))
    put(console, x + 2, y + 1, "LEVEL UP", GREEN)
    for index, option in enumerate(state.level_up_choices):
        put(console, x + 2, y + 3 + index * 2, f"{index + 1}. {option['label']}", WHITE)
    put(console, x + 2, y + 9, "Press 1-3 (keypad works too)", GREY)


def draw_shop(console, state) -> None:
    items = get_shop_items()
    put_centered(console, 2, "- SHOP -", GOLD)
    # the shopkeeper's line in a framed speech box
    box_w = config.SCREEN_WIDTH - 8
    console.draw_frame(x=4, y=4, width=box_w, height=3, fg=(150, 110, 40), bg=PANEL_BG)
    put(console, 6, 4, " SHOPKEEPER ", (255, 200, 120))
    if state.shop_message:
        put_centered(console, 5, state.shop_message, (255, 200, 120))

    put(console, 4, 10, "GEAR", GOLD)
    put(console, 4, 11, "Up/Down to browse, Enter to buy", GREY)
    for index, item in enumerate(items):
        y = 13 + index * 2
        selected = index == state.shop_index
        cursor = ">" if selected else " "
        if item["type"] == "slot":
            owned = len(state.weapon_slots) >= slot_number(item)
            label = f"{cursor} {item['name']:<16} {item['cost']:>4} pts   Lv {item['required_level']}"
            if owned:
                label += "  owned"
        else:
            label = f"{cursor} {item['name']:<16} {item['cost']:>4} pts"
        affordable = state.points >= item["cost"]
        color = GOLD if selected else (WHITE if affordable else DIM)
        put(console, 4, y, label, color)

    put(console, 50, 10, "LOADOUT", GOLD)
    put(console, 50, 11, "1-4 picks the slot to fill", GREY)
    for slot, weapon_id in enumerate(state.weapon_slots):
        name = get_weapon(weapon_id)["name"] if weapon_id else "Empty"
        marker = ">" if slot == state.shop_slot else " "
        put(console, 50, 13 + slot * 2, f"{marker} Slot {slot + 1}: {name}", GOLD if slot == state.shop_slot else GREY)
    for slot in range(len(state.weapon_slots), 4):
        put(console, 50, 13 + slot * 2, f"  Slot {slot + 1}: locked", DIM)

    put(console, 50, 23, f"POINTS  {state.points}", WHITE)
    put(console, 50, 24, f"LEVEL   {state.level}", WHITE)
    put(console, 50, 25, f"NEXT    wave {state.wave + 1}" + ("  (BOSS)" if (state.wave + 1) % config.BOSS_WAVE_INTERVAL == 0 else ""), WHITE)
    put_centered(console, 40, "ESC or SPACE : launch next wave", SKY)
