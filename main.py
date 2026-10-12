"""main.py - entry point: opens the window, runs the fixed-timestep loop and
translates keyboard events into game actions.

    python main.py

All rules live in game.py and the modules it imports; all drawing lives in
ui.py. This file only owns the window, the clock and the key mapping.
"""
import time

import tcod

import config
from effects import shake_offset
from game import Inputs, handle_action, new_game, update
from sprites import register_sprites
from ui import draw_frame

KeySym = tcod.event.KeySym

# Discrete key presses -> action names understood by game.handle_action.
KEY_ACTIONS = {
    KeySym.RETURN: "confirm",
    KeySym.KP_ENTER: "confirm",
    KeySym.ESCAPE: "back",
    KeySym.SPACE: "space",
    KeySym.UP: "up",
    KeySym.DOWN: "down",
    KeySym.W: "up",          # menus only; movement reads held keys separately
    KeySym.S: "down",
    KeySym.N1: "num1", KeySym.KP_1: "num1",
    KeySym.N2: "num2", KeySym.KP_2: "num2",
    KeySym.N3: "num3", KeySym.KP_3: "num3",
    KeySym.N4: "num4", KeySym.KP_4: "num4",
}


def read_inputs(held: set) -> Inputs:
    """Held movement keys -> an Inputs record for this step."""
    inputs = Inputs()
    if KeySym.W in held or KeySym.UP in held:
        inputs.move_y -= 1
    if KeySym.S in held or KeySym.DOWN in held:
        inputs.move_y += 1
    if KeySym.A in held or KeySym.LEFT in held:
        inputs.move_x -= 1
    if KeySym.D in held or KeySym.RIGHT in held:
        inputs.move_x += 1
    inputs.sprint = KeySym.LSHIFT in held or KeySym.RSHIFT in held
    return inputs


def main() -> None:
    tileset = tcod.tileset.load_tilesheet(config.resource_path(config.TILESHEET_FILE), 32, 8, tcod.tileset.CHARMAP_TCOD)
    register_sprites(tileset)

    state = new_game()
    held: set = set()

    with tcod.context.new(
        columns=config.SCREEN_WIDTH,
        rows=config.SCREEN_HEIGHT,
        tileset=tileset,
        title=config.WINDOW_TITLE,
        vsync=True,
    ) as context:
        root_console = tcod.console.Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, order="F")
        frame = tcod.console.Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT, order="F")

        last_time = time.perf_counter()
        accumulator = 0.0

        while True:
            now = time.perf_counter()
            accumulator += min(now - last_time, 0.25)
            last_time = now

            for event in tcod.event.get():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()
                if isinstance(event, tcod.event.KeyUp):
                    held.discard(event.sym)
                elif isinstance(event, tcod.event.KeyDown):
                    held.add(event.sym)
                    action = KEY_ACTIONS.get(event.sym)
                    if action is not None:
                        before = state.mode
                        state = handle_action(state, action)
                        if state.mode != before:
                            held.clear()

            inputs = read_inputs(held)
            while accumulator >= config.STEP:
                update(state, inputs, config.STEP)
                accumulator -= config.STEP

            frame.clear()
            draw_frame(frame, state)
            root_console.clear()
            shake_x, shake_y = shake_offset(state.effects)
            frame.blit(root_console, dest_x=shake_x, dest_y=shake_y)
            context.present(root_console)


if __name__ == "__main__":
    main()
