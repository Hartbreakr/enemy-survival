"""game.py - the whole game state in one object, plus the two functions that
drive it: `handle_action` (a key press) and `update` (one fixed time step).

main.py owns the window and translates tcod events into these calls; nothing
in here touches tcod, so test_headless.py can run thousands of steps with no
window at all.

Modes: menu -> playing -> dying -> gameover (-> playing or menu)
       menu <-> encyclopedia
"""
from dataclasses import dataclass, field

import config
import save
from boss import update_boss
from encyclopedia import ENTRY_ORDER
from effects import Effects, update_effects
from enemies import start_wave, update_enemies, update_enemy_projectiles, wave_is_cleared
from player import (
    choose_level_upgrade,
    default_player_stats,
    random_arena_cell,
    update_pickups,
    update_player_movement,
)
from shop import open_shop, shop_action
from weapons import new_weapon_state, reflect_enemy_bullets, update_player_bullets, update_weapons


@dataclass
class Inputs:
    """What the player is holding right now."""
    move_x: int = 0        # -1, 0, 1
    move_y: int = 0
    sprint: bool = False


@dataclass
class GameState:
    # flow
    mode: str = "menu"
    death_timer: float = 0.0
    highscore: int = 0
    new_highscore: bool = False
    menu_index: int = 0                # 0 = START, 1 = ENCYCLOPEDIA
    codex_index: int = 0               # highlighted row in the encyclopedia
    seen_kinds: set = field(default_factory=set)   # enemy kinds met in any run (saved)
    # player body
    px: float = config.PLAYER_START_X
    py: float = config.PLAYER_START_Y
    vx: float = 0.0
    vy: float = 0.0
    ship_index: int = 6
    health: int = config.PLAYER_START_STATS["max_health"]
    iframes: float = 0.0
    stats: dict = field(default_factory=default_player_stats)
    buffs: dict = field(default_factory=dict)
    # progression
    score: int = 0                     # cumulative, shown on HUD / game over / high score
    points: int = 0                    # spendable in the shop
    xp: int = 0
    level: int = 1
    xp_needed: int = config.XP_FIRST_LEVEL
    pending_level_ups: int = 0
    level_up_open: bool = False
    level_up_choices: list = field(default_factory=list)
    # weapons
    weapon_slots: list = field(default_factory=lambda: [config.STARTER_WEAPON["id"], None])
    weapon_states: list = field(default_factory=lambda: [new_weapon_state(), new_weapon_state()])
    weapon_upgrades: dict = field(default_factory=dict)
    # arena
    wave: int = 1
    kills_this_wave: int = 0
    wave_total: int = 0
    enemies: list = field(default_factory=list)
    boss: object = None
    projectiles: list = field(default_factory=list)       # enemy bullets
    player_bullets: list = field(default_factory=list)
    drops: list = field(default_factory=list)
    pickup_x: int = 0
    pickup_y: int = 0
    # shop
    shop_open: bool = False
    shop_index: int = 0
    shop_slot: int = 0
    shop_message: str | None = None
    # juice
    effects: Effects = field(default_factory=Effects)
    boss_just_died: bool = False


def new_game(highscore: int | None = None, seen_kinds=None) -> GameState:
    """A fresh state sitting on the main menu.

    With no arguments the save file is read. Tests pass both values in so
    they never touch the real save.
    """
    state = GameState()
    if highscore is None:
        data = save.load_save()
        state.highscore = data["highscore"]
        state.seen_kinds = set(data["seen"])
    else:
        state.highscore = highscore
        state.seen_kinds = set(seen_kinds or ())
    return state


def start_run(state: GameState) -> GameState:
    """Reset everything except the saved data (high score, seen kinds) and begin wave 1."""
    fresh = new_game(state.highscore, state.seen_kinds)
    fresh.mode = "playing"
    fresh.pickup_x, fresh.pickup_y = random_arena_cell()
    start_wave(fresh)
    return fresh


# ============================================================
# 1) KEY PRESSES
# ============================================================
def handle_action(state: GameState, action: str) -> GameState:
    """Apply one discrete key action. Returns the (possibly replaced) state.

    Actions: confirm, back, space, up, down, num1..num4.
    """
    if state.mode == "menu":
        if action == "space":
            return start_run(state)
        if action in ("up", "down"):
            state.menu_index = 1 - state.menu_index          # only two rows, so just flip
        elif action == "confirm":
            if state.menu_index == 0:
                return start_run(state)
            state.mode = "encyclopedia"
            state.codex_index = 0
    elif state.mode == "encyclopedia":
        if action == "up":
            state.codex_index = (state.codex_index - 1) % len(ENTRY_ORDER)
        elif action == "down":
            state.codex_index = (state.codex_index + 1) % len(ENTRY_ORDER)
        elif action == "back":
            state.mode = "menu"
    elif state.mode == "gameover":
        if action in ("confirm", "space"):
            return start_run(state)
        if action == "back":
            state.mode = "menu"
    elif state.mode == "playing":
        if state.level_up_open:
            if action in ("num1", "num2", "num3"):
                choose_level_upgrade(state, int(action[3:]) - 1)
        elif state.shop_open:
            shop_action(state, action)
    return state


# ============================================================
# 2) ONE FIXED STEP
# ============================================================
def update(state: GameState, inputs: Inputs, dt: float) -> None:
    update_effects(state.effects, dt)

    if state.mode == "dying":
        state.death_timer += dt
        if state.death_timer >= config.DEATH_ANIMATION_SECONDS:
            finish_run(state)
        return

    if state.mode != "playing" or state.shop_open or state.level_up_open:
        return

    update_player_movement(state, inputs, dt)
    update_pickups(state, dt)
    update_weapons(state, dt)
    reflect_enemy_bullets(state)
    update_enemies(state, dt)
    had_boss = state.boss is not None
    update_boss(state, dt)
    update_enemy_projectiles(state, dt)
    update_player_bullets(state, dt)
    if had_boss and state.boss is None:
        state.boss_just_died = True

    if state.mode == "playing" and not state.level_up_open and wave_is_cleared(state):
        open_shop(state, "boss_down" if state.boss_just_died else "greeting")
        state.boss_just_died = False


def finish_run(state: GameState) -> None:
    """Death animation is over: record the score and show game over."""
    if state.score > state.highscore:
        state.highscore = state.score
        state.new_highscore = True
    save.write_save(state.highscore, state.seen_kinds)
    state.mode = "gameover"
