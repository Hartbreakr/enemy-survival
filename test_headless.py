"""test_headless.py - drives the game with no window.

    python test_headless.py

Runs thousands of fixed steps with scripted inputs and prints what actually
happened. Also renders every screen into an off-screen tcod Console so the
drawing code is exercised (no tcod.context is ever created).
"""
import math
import os
import tempfile

import tcod

import boss as boss_module
import config
import encyclopedia
import enemies
import game
import player
import save
import shop
import sprites
import ui
import weapons
from game import Inputs, handle_action, new_game, start_run, update
from ui import draw_frame

STEP = config.STEP
PASSES = []

# Never touch the real save files: everything below writes into a temp dir.
TEST_DIR = tempfile.mkdtemp(prefix="enemy_survival_test_")
save.SAVE_FILE = os.path.join(TEST_DIR, "save.json")
save.HIGHSCORE_FILE = os.path.join(TEST_DIR, "highscore.txt")


def check(label: str, condition: bool, detail: str = "") -> None:
    PASSES.append(condition)
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))


def run(state, steps: int, inputs: Inputs = Inputs(), until=None) -> int:
    """Step the game; stop early when `until(state)` is true. Returns steps taken."""
    for index in range(steps):
        update(state, inputs, STEP)
        if until is not None and until(state):
            return index + 1
    return steps


def hunt_inputs(state) -> Inputs:
    """Scripted pilot: walk toward the nearest enemy until it is in comfortable range."""
    target = weapons.nearest_target(state, 999.0)
    if target is None:
        return Inputs()
    dx = target.x - state.px
    dy = target.y - state.py
    if math.hypot(dx, dy) < 12.0:
        return Inputs()
    return Inputs(move_x=(dx > 0) - (dx < 0), move_y=(dy > 0) - (dy < 0))


def run_hunting(state, steps: int, until) -> int:
    for index in range(steps):
        if state.level_up_open:
            handle_action(state, "num1")
        update(state, hunt_inputs(state), STEP)
        if until(state):
            return index + 1
    return steps


def god_mode(state) -> None:
    """Keep the test pilot alive while we measure other things."""
    state.stats["max_health"] = 999
    state.health = 999


def fresh_arena(wave: int = 1):
    state = start_run(new_game(0))
    state.wave = wave
    state.enemies.clear()
    state.boss = None
    state.projectiles.clear()
    state.player_bullets.clear()
    state.px, state.py = 40.0, 30.0
    return state


# ============================================================
print("1) wave clear -> shop opens automatically")
state = start_run(new_game(0))
god_mode(state)
check("wave 1 spawns 6 enemies", len(state.enemies) == 6, f"{len(state.enemies)}")
steps = run_hunting(state, 120 * 90, until=lambda s: s.shop_open)
check("shop opened after wave cleared", state.shop_open, f"{steps} steps = {steps / 120:.1f}s, kills {state.kills_this_wave}/{state.wave_total}")
check("kill counter matches total", state.kills_this_wave == state.wave_total)
check("score == points (nothing bought yet, no cash grab)", state.score == state.points, f"score {state.score} points {state.points}")
check("shopkeeper greeted", state.shop_message in shop.SHOPKEEPER_LINES["greeting"], repr(state.shop_message))
check("no stray bullets carried into the shop", not state.projectiles and not state.player_bullets)

# ============================================================
print("2) shop: buying, gating, slot unlock")
shotgun_cost = config.WEAPON_CATALOG[0]["cost"]
check("shotgun costs 75 now (was 60)", shotgun_cost == 75, f"{shotgun_cost}")
state.points = 60                                 # the OLD price
handle_action(state, "num2")                      # fill slot 2
handle_action(state, "confirm")                   # item 0 = Shotgun
check("buying shotgun at the old price (60 pts) fails", state.weapon_slots[1] is None
      and state.shop_message in shop.SHOPKEEPER_LINES["no_funds"], repr(state.shop_message))
state.points = 500
points_before = state.points
handle_action(state, "confirm")
check("bought shotgun into slot 2", state.weapon_slots[1] == "shotgun", str(state.weapon_slots))
check("points deducted by the new price, score untouched",
      state.points == points_before - shotgun_cost and state.score != state.points,
      f"points {state.points} score {state.score}")
check("'bought' line shown", any(state.shop_message.startswith(line.split('{')[0]) for line in shop.SHOPKEEPER_LINES["bought"]), repr(state.shop_message))
items = shop.get_shop_items()
slot3_index = next(i for i, item in enumerate(items) if item["id"] == "slot_3")
for _ in range(slot3_index):
    handle_action(state, "down")
state.level = 1
handle_action(state, "confirm")
check("slot 3 level-gated at level 1", len(state.weapon_slots) == 2 and "Level 3" in state.shop_message, repr(state.shop_message))
state.level = 3
handle_action(state, "confirm")
check("slot 3 unlocked at level 3", len(state.weapon_slots) == 3 and len(state.weapon_states) == 3)
handle_action(state, "confirm")
check("re-buying slot 3 says owned", state.shop_message in shop.SHOPKEEPER_LINES["slot_owned"], repr(state.shop_message))
state.points = 0
handle_action(state, "up"); handle_action(state, "up")   # back onto a weapon
handle_action(state, "confirm")
check("no funds line when broke", state.shop_message in shop.SHOPKEEPER_LINES["no_funds"], repr(state.shop_message))
handle_action(state, "back")
check("ESC leaves shop and starts wave 2", not state.shop_open and state.wave == 2 and len(state.enemies) == 8,
      f"wave {state.wave}, {len(state.enemies)} enemies")

# ============================================================
print("3) boss wave: spawn -> 3 phases -> death -> shop")
state = fresh_arena(wave=4)
god_mode(state)
state.weapon_slots = ["pulse", "gatling", "laser"]
state.weapon_states = [weapons.new_weapon_state() for _ in range(3)]
state.weapon_upgrades = {"pulse": {"damage_bonus": 1}}
state.shop_open = True
handle_action(state, "space")                     # leave shop -> wave 5
check("wave 5 is a boss wave with no regular enemies", state.boss is not None and not state.enemies)
check("boss hp scales with wave", state.boss.max_hp == config.BOSS_BASE_HP + config.BOSS_HP_PER_WAVE * 5, f"{state.boss.max_hp} hp")
phases_seen = set()
boss_bullets = {1: 0, 2: 0, 3: 0}
score_before = state.score
steps = 0
boss_steps = None
# strafe left/right under the boss so bullets have something to aim at
for index in range(120 * 180):
    inputs = Inputs(move_x=1 if (index // 240) % 2 == 0 else -1)
    if state.level_up_open:
        handle_action(state, "num1")
    if state.boss is None and boss_steps is None:
        boss_steps = index
    if state.boss is not None:
        phase = boss_module.boss_phase(state.boss)
        phases_seen.add(phase)
        boss_bullets[phase] = max(boss_bullets[phase], len(state.projectiles))
    update(state, inputs, STEP)
    steps += 1
    if state.shop_open:
        break
check("boss died and shop opened", state.boss is None and state.shop_open, f"boss down after {(boss_steps or steps) / 120:.1f}s")
check("all three phases happened", phases_seen == {1, 2, 3}, f"phases {sorted(phases_seen)}")
check("every phase shot bullets", all(count > 0 for count in boss_bullets.values()), f"peak bullets on screen per phase {boss_bullets}")
check("boss reward paid", state.score - score_before >= boss_module.boss_reward(5), f"+{state.score - score_before} score")
check("shopkeeper used the boss_down line", state.shop_message in shop.SHOPKEEPER_LINES["boss_down"], repr(state.shop_message))
boss_seconds = (boss_steps or steps) / 120

# ============================================================
print("4) enemy behaviors")
# dasher
state = fresh_arena()
god_mode(state)
state.weapon_slots = [None, None]
dasher = enemies.make_enemy("dasher", 40, 10, 2)
state.enemies.append(dasher)
start_y = dasher.y
states_seen = []
def note(s):
    if not states_seen or states_seen[-1] != dasher.state:
        states_seen.append(dasher.state)
    return False
for _ in range(120 * 4):
    update(state, Inputs(), STEP)
    note(state)
check("dasher cycles wait -> telegraph -> charge", states_seen[:3] == ["wait", "telegraph", "charge"], f"{states_seen}")
check("dasher moved toward and past the player", dasher.y > start_y + 10, f"y {start_y:.0f} -> {dasher.y:.1f}")

# sniper
state = fresh_arena()
god_mode(state)
state.weapon_slots = [None, None]
sniper = enemies.make_enemy("sniper", 40, 12, 4)       # 18 tiles away: inside its band
state.enemies.append(sniper)
aimed = False
shot = None
for _ in range(120 * 5):
    update(state, Inputs(), STEP)
    if sniper.state == "aim":
        aimed = True
    if shot is None:
        shot = next((p for p in state.projectiles if p["source"] is sniper), None)
    if shot is not None:
        break
check("sniper entered aim (telegraph) state", aimed)
check("sniper fired an aimed shot", shot is not None and abs(math.hypot(shot["vx"], shot["vy"]) - 24.0) < 0.01,
      f"bullet speed {math.hypot(shot['vx'], shot['vy']):.1f}" if shot else "no shot")
dist = math.hypot(sniper.x - state.px, sniper.y - state.py)
check("sniper kept its distance", 14.0 <= dist <= 22.0, f"{dist:.1f} tiles")

# splitter
state = fresh_arena()
state.weapon_slots = [None, None]
splitter = enemies.make_enemy("splitter", 40, 20, 3)
state.enemies.append(splitter)
state.wave_total = 1
enemies.damage_enemies(state, [splitter], 99)
kinds = sorted(e.kind for e in state.enemies)
check("splitter died into 2 splitlings", kinds == ["splitling", "splitling"], f"{kinds}")
check("wave total grew to count the splitlings", state.wave_total == 3 and state.kills_this_wave == 1)

# tank
state = fresh_arena()
state.weapon_slots = [None, None]
state.px, state.py = 20.0, 25.0
tank = enemies.make_enemy("tank", 40, 25, 6)
tank.facing = math.pi                                  # shield faces the player on the left
state.enemies.append(tank)
hp_before = tank.hp
state.player_bullets.append({"x": 39.0, "y": 25.0, "vx": 14.5, "vy": 0.0, "damage": 1, "color": (0, 0, 0),
                             "char": ".", "weapon_id": "pulse", "explosion_radius": 0, "chain_count": 0, "chain_range": 0})
for _ in range(20):
    weapons.update_player_bullets(state, STEP)
check("frontal bullet blocked by tank shield", tank.hp == hp_before and not state.player_bullets, f"hp {tank.hp}")
state.player_bullets.append({"x": 40.0, "y": 24.0, "vx": 0.0, "vy": 14.5, "damage": 1, "color": (0, 0, 0),
                             "char": ".", "weapon_id": "pulse", "explosion_radius": 0, "chain_count": 0, "chain_range": 0})
for _ in range(20):
    weapons.update_player_bullets(state, STEP)
check("flank bullet (from above) damages tank", tank.hp == hp_before - 1, f"hp {tank.hp}")
check("tank is tougher at wave 6 (+1 hp bonus)", tank.max_hp == config.ENEMY_TYPES["tank"]["hp"] + 1, f"max {tank.max_hp}")

# ============================================================
print("5) damage -> i-frames -> death -> game over -> high score")
for path in (save.SAVE_FILE, save.HIGHSCORE_FILE):
    if os.path.exists(path):
        os.remove(path)
state = fresh_arena()
state.weapon_slots = [None, None]
state.score = 777
shooter = enemies.make_enemy("normal", 60, 30, 1)
shooter.cooldown = 999.0                               # keeps the wave alive without shooting
state.enemies.append(shooter)
hp = state.health
state.projectiles.append({"x": state.px, "y": state.py, "vx": 0.0, "vy": 0.0, "damage": 1, "source": shooter,
                          "char": "o", "color": (0, 0, 0), "heavy": False, "reflected": False})
enemies.update_enemy_projectiles(state, STEP)
check("bullet took 1 hp and started i-frames", state.health == hp - 1 and state.iframes > 0, f"iframes {state.iframes:.2f}s")
check("screen shake triggered", state.effects.shake_time > 0)
state.projectiles.append({"x": state.px, "y": state.py, "vx": 0.0, "vy": 0.0, "damage": 1, "source": shooter,
                          "char": "o", "color": (0, 0, 0), "heavy": False, "reflected": False})
enemies.update_enemy_projectiles(state, STEP)
check("second bullet during i-frames did nothing", state.health == hp - 1)
run(state, int(config.IFRAME_SECONDS * 120) + 2)
check("i-frames expired", state.iframes == 0.0)
state.health = 1
state.projectiles.append({"x": state.px, "y": state.py, "vx": 0.0, "vy": 0.0, "damage": 1, "source": shooter,
                          "char": "o", "color": (0, 0, 0), "heavy": False, "reflected": False})
enemies.update_enemy_projectiles(state, STEP)
check("lethal hit -> dying with explosion", state.mode == "dying" and len(state.effects.particles) > 0)
run(state, int(config.DEATH_ANIMATION_SECONDS * 120) + 2)
check("game over after the death animation", state.mode == "gameover")
check("high score saved to disk (save.json)", save.load_highscore() == 777 and state.new_highscore, f"file says {save.load_highscore()}")
check("seen kinds saved alongside the high score", "normal" in save.load_save()["seen"], f"{save.load_save()['seen']}")
state = handle_action(state, "back")
check("ESC on game over returns to menu", state.mode == "menu")
state = handle_action(state, "confirm")
check("ENTER on menu starts a new run, high score kept", state.mode == "playing" and state.highscore == 777 and state.score == 0)

# ============================================================
print("6) level up menu")
state = fresh_arena()
state.enemies.append(enemies.make_enemy("normal", 60, 30, 1))
player.gain_xp(state, config.XP_FIRST_LEVEL)
check("level-up menu opened with 3 choices", state.level_up_open and len(state.level_up_choices) == 3 and state.level == 2)
px = state.px
run(state, 60, Inputs(move_x=1))
check("game is paused while the menu is open", state.px == px)
handle_action(state, "num1")
check("choice 1 applied and menu closed", not state.level_up_open)

# ============================================================
print("7) long survival run with a scripted strafing pilot (no god mode)")
state = start_run(new_game(0))
steps = 0
for index in range(120 * 600):
    inputs = hunt_inputs(state)
    if inputs.move_x == 0 and inputs.move_y == 0:      # in range: strafe instead of standing still
        inputs = Inputs(move_x=1 if (index // 90) % 2 == 0 else -1)
    if state.level_up_open:
        handle_action(state, "num1")
    if state.shop_open:
        state.shop_index = 0
        handle_action(state, "num2")
        handle_action(state, "confirm")
        handle_action(state, "space")
    update(state, inputs, STEP)
    steps += 1
    if state.mode == "gameover":
        break
print(f"  bot reached wave {state.wave}, level {state.level}, score {state.score} in {steps / 120:.0f}s; ended in mode '{state.mode}'")
bot_wave, bot_level, bot_score, bot_seconds = state.wave, state.level, state.score, steps / 120
check("no crash over a long run", True, f"{steps} steps")

# ============================================================
print("8) off-screen render of every screen (no window)")
console = tcod.console.Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, order="F")
for mode_name, builder in (
    ("menu", lambda: new_game(0)),
    ("encyclopedia", lambda: (lambda s: (setattr(s, "mode", "encyclopedia"), s)[-1])(new_game(0))),
    ("encyclopedia-unlocked-boss", lambda: (lambda s: (setattr(s, "mode", "encyclopedia"), setattr(s, "codex_index", 7), s)[-1])(new_game(0, set(encyclopedia.ENTRY_ORDER)))),
    ("playing", lambda: start_run(new_game(0))),
    ("boss", lambda: (lambda s: (setattr(s, "wave", 5), enemies.start_wave(s), s)[-1])(start_run(new_game(0)))),
    ("shop", lambda: (lambda s: (shop.open_shop(s), s)[-1])(start_run(new_game(0)))),
    ("levelup", lambda: (lambda s: (player.gain_xp(s, 60), s)[-1])(start_run(new_game(0)))),
    ("dying", lambda: (lambda s: (setattr(s, "mode", "dying"), s)[-1])(start_run(new_game(0)))),
    ("gameover", lambda: (lambda s: (setattr(s, "mode", "gameover"), s)[-1])(start_run(new_game(0)))),
):
    s = builder()
    if mode_name == "playing":
        for e in s.enemies:
            e.flash = 0.05
        s.enemies.append(enemies.make_enemy("tank", 50, 40, 6))
        d = enemies.make_enemy("dasher", 60, 40, 2); d.state = "telegraph"; d.aim_x, d.aim_y = s.px, s.py
        s.enemies.append(d)
        n = enemies.make_enemy("sniper", 20, 40, 4); n.state = "aim"; n.aim_x, n.aim_y = s.px, s.py; n.timer = 0.1
        s.enemies.append(n)
        s.iframes = 0.5
    console.clear()
    draw_frame(console, s)
    check(f"drew '{mode_name}' screen", True)
    if mode_name == "shop":
        glyphs = set(int(v) for v in console.ch.flatten())
        check("shop screen has no shopkeeper portrait tile", 0xE012 not in glyphs and not hasattr(sprites, "SHOPKEEPER_CODEPOINT"))
        check("shop screen still shows a shopkeeper line", s.shop_message in shop.SHOPKEEPER_LINES["greeting"])

# ============================================================
print("9) main menu cursor and the encyclopedia screen")
state = new_game(0)
check("menu starts on START", state.menu_index == 0)
handle_action(state, "down")
check("DOWN moves the cursor to ENCYCLOPEDIA", state.menu_index == 1)
handle_action(state, "up")
check("UP moves it back to START", state.menu_index == 0)
handle_action(state, "down")
state = handle_action(state, "confirm")
check("ENTER on ENCYCLOPEDIA opens it", state.mode == "encyclopedia" and state.codex_index == 0)
handle_action(state, "down"); handle_action(state, "down")
check("DOWN scrolls the list", state.codex_index == 2)
handle_action(state, "up"); handle_action(state, "up"); handle_action(state, "up")
check("UP wraps around to the last entry", state.codex_index == len(encyclopedia.ENTRY_ORDER) - 1)
handle_action(state, "back")
check("ESC returns to the menu", state.mode == "menu")
state.menu_index = 1
state = handle_action(state, "space")
check("SPACE on the menu always starts a run", state.mode == "playing")
state = new_game(0)
state = handle_action(state, "confirm")
check("ENTER on START starts a run", state.mode == "playing")
check("encyclopedia has all 8 kinds", list(encyclopedia.ENTRY_ORDER) == ["normal", "elite", "dasher", "sniper", "splitter", "splitling", "tank", "boss"])
for kind in encyclopedia.ENTRY_ORDER:
    stats = encyclopedia.entry_stats(kind)
    assert all(stats[key] for key in ("hp", "speed", "reward", "first_wave")), kind
    assert 2 <= len(encyclopedia.BLURBS[kind]) <= 3 and all(len(line) <= 44 for line in encyclopedia.BLURBS[kind]), kind
check("every entry has stats and a 2-3 line blurb", True)
check("tank reward in the encyclopedia comes from config", encyclopedia.entry_stats("tank")["reward"] == str(config.ENEMY_TYPES["tank"]["reward"]))
check("locked entry shows ???", encyclopedia.entry_name("tank", False) == "???" and encyclopedia.entry_name("tank", True) == "Tank")

# ============================================================
print("10) encyclopedia unlocks persist")
for path in (save.SAVE_FILE, save.HIGHSCORE_FILE):
    if os.path.exists(path):
        os.remove(path)
state = fresh_arena(wave=6)
state.seen_kinds = set()
check("tank starts locked", "tank" not in state.seen_kinds)
state.enemies.append(enemies.make_enemy("tank", 60, 30, 6))
enemies.note_seen(state, "tank")                    # what start_wave does for every spawn
check("tank unlocked when one spawns", "tank" in state.seen_kinds)
check("unlock was saved to disk immediately", "tank" in save.load_save()["seen"], f"{save.load_save()}")
state.wave = 4
state.shop_open = True
handle_action(state, "space")                       # -> wave 5, boss
check("boss unlocked when it spawns", "boss" in state.seen_kinds and "boss" in save.load_save()["seen"])
state = fresh_arena()
state.seen_kinds = set()
splitter = enemies.make_enemy("splitter", 40, 20, 3)
state.enemies.append(splitter)
enemies.damage_enemies(state, [splitter], 99)
check("splitling unlocked when a splitter splits", "splitling" in state.seen_kinds)
state = start_run(new_game(0))
check("a real wave 1 unlocks something and the count shows it", encyclopedia.discovered_count(state.seen_kinds) >= 1,
      f"{encyclopedia.discovered_count(state.seen_kinds)}/8 after wave 1 spawn")
loaded = new_game()                                  # reads the temp save.json
check("new_game() loads seen kinds back from disk", loaded.seen_kinds == set(save.load_save()["seen"]) and "normal" in loaded.seen_kinds)

print("11) save.json round-trip and migration from highscore.txt")
for path in (save.SAVE_FILE, save.HIGHSCORE_FILE):
    if os.path.exists(path):
        os.remove(path)
save.write_save(4321, {"dasher", "normal", "dasher"})
data = save.load_save()
check("round-trip keeps highscore and de-duplicated sorted seen list", data == {"highscore": 4321, "seen": ["dasher", "normal"]}, f"{data}")
with open(save.SAVE_FILE, "w", encoding="utf-8") as f:
    f.write("{ this is not json")
check("corrupt save.json counts as fresh", save.load_save() == {"highscore": 0, "seen": []})
os.remove(save.SAVE_FILE)
with open(save.HIGHSCORE_FILE, "w", encoding="utf-8") as f:
    f.write("1685")
data = save.load_save()
check("old highscore.txt migrated into save.json", data["highscore"] == 1685 and os.path.exists(save.SAVE_FILE), f"{data}")
check("highscore.txt left in place after migration", os.path.exists(save.HIGHSCORE_FILE))
save.write_save(2000, ["normal"])
with open(save.HIGHSCORE_FILE, "w", encoding="utf-8") as f:
    f.write("9999")
check("once save.json exists, highscore.txt is ignored", save.load_save()["highscore"] == 2000)

print("12) point system numbers")
expected_rewards = {"normal": 8, "elite": 20, "dasher": 12, "splitter": 12, "splitling": 4, "sniper": 16, "tank": 32}
check("kill rewards cut ~20%", {k: config.ENEMY_TYPES[k]["reward"] for k in expected_rewards} == expected_rewards)
expected_xp = {"normal": 10, "elite": 25, "dasher": 15, "splitter": 15, "splitling": 5, "sniper": 20, "tank": 40}
check("XP table keeps the old values", config.ENEMY_XP == expected_xp)
check("pickup value 5 -> 4", config.PLAYER_START_STATS["pickup_value"] == 4)
expected_costs = {"shotgun": 75, "laser": 110, "megabomb": 145, "mirror_shield": 170, "gatling": 180, "chain_lightning": 215}
check("weapon prices raised ~20%", {w["id"]: w["cost"] for w in config.WEAPON_CATALOG} == expected_costs)
check("slot prices 120 / 240", [s["cost"] for s in config.SLOT_SHOP_ITEMS] == [120, 240])
check("boss reward unchanged", boss_module.boss_reward(5) == 500)
state = fresh_arena()
state.enemies.append(enemies.make_enemy("normal", 60, 30, 1))
victim = enemies.make_enemy("tank", 50, 30, 1)
state.enemies.append(victim)
enemies.damage_enemies(state, [victim], 99)
check("tank kill pays 32 score/points but 40 XP", state.score == 32 and state.points == 32 and state.xp == 40,
      f"score {state.score} points {state.points} xp {state.xp}")

print("13) ship sprite sanity")
ship_counts = []
for degrees in sprites.SHIP_ROTATIONS:
    base = sprites.Image.fromarray(sprites._grid_layer(sprites.SHIP_UP, sprites.SHIP_PALETTE), mode="RGBA")
    tile = sprites._rotated(base, degrees)
    ship_counts.append(int((tile[:, :, 3] > 0).sum()))
base_rows = sprites.SHIP_UP
check("base ship art is left-right symmetric", all(row == row[::-1] for row in base_rows))
check("every rotation keeps most of the ship's pixels", min(ship_counts) >= 0.8 * max(ship_counts), f"solid pixels per rotation {ship_counts}")
check("ship uses white / red / dark outline / cyan cockpit / engine glow", set("WRDCE") <= set("".join(base_rows)))

print()
print(f"RESULT: {sum(PASSES)}/{len(PASSES)} checks passed; wave-5 boss fight took {boss_seconds:.1f}s with pulse+1/gatling/laser")
print(f"long-run bot: wave {bot_wave}, level {bot_level}, score {bot_score} in {bot_seconds:.0f}s")
raise SystemExit(0 if all(PASSES) else 1)
