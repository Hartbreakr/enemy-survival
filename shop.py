"""shop.py - the between-wave shop and the shopkeeper's mouth.

Owns: the shopkeeper's lines, the item list (weapons + weapon slots), buying
rules (points, slot ownership, level gates) and the hand-off to the next wave.
The shop opens automatically when a wave is cleared (see game.py).
"""
import random

import config
from enemies import start_wave
from weapons import new_weapon_state

SHOPKEEPER_LINES = {
    "greeting": (
        "Back again, ace. Rack's full and waiting.",
        "Take a look, pilot. Everything's for sale but the airlock.",
        "What'll it be? Credits talk out here, hotshot.",
        "Don't just float there, kid. Buy something or go kill something.",
    ),
    "no_funds": (
        "Pilot, your wallet is emptier than your aim.",
        "Not enough credits, ace. Go find some points.",
        "Your budget has crash-landed, pilot.",
        "That weapon costs more than you can afford, hotshot.",
        "Denied. Maybe try collecting points before shopping.",
        "I don't run a charity for broke pilots, kid.",
        "Come back when your pockets aren't showing daylight.",
        "Scrap and salvage, ace. You're short on scrap and salvage.",
    ),
    "bought": (
        "Solid choice, ace. {name} is yours.",
        "Good eye, pilot. {name}, loaded and ready.",
        "{name} strapped into slot {slot}. Go make me proud.",
        "Done. Treat her right and she'll keep you breathing.",
    ),
    "slot_unlocked": (
        "New hardpoint online, pilot. {name} is live.",
        "Opening the {name} bay now. Spend it well, ace.",
        "{name}, huh? More firepower than most flyboys ever earn.",
    ),
    "slot_owned": (
        "That rack's already yours, hotshot. Buy something new.",
        "Already unlocked that bay, ace. Memory's short out there?",
        "You own that slot, pilot. Don't get greedy.",
    ),
    "level_gate": (
        "Come back when you've bled a little, rookie. That's Level {level} kit.",
        "Level {level} gear, ace. Not for green recruits off the pad.",
        "You'll grow into it, flyboy. Slice it 'til you're Level {level}.",
    ),
    # New category: said when the shop opens right after a boss kill.
    "boss_down": (
        "You dropped the big one, ace. Drinks are still not free.",
        "That mothership's scrap now, hotshot. Spend the bounty.",
        "Overlord down. Didn't think you had it in you, kid.",
    ),
}


def shopkeeper_say(category: str, previous: str | None = None, **fmt) -> str:
    """Pick a line from a category, avoiding the line that was just shown."""
    lines = SHOPKEEPER_LINES[category]
    available = [line for line in lines if line != previous] or list(lines)
    return random.choice(available).format(**fmt)


def get_shop_items() -> list[dict]:
    return [
        *({"type": "weapon", **weapon} for weapon in config.WEAPON_CATALOG),
        *config.SLOT_SHOP_ITEMS,
    ]


def slot_number(item: dict) -> int:
    """'slot_3' -> 3"""
    return int(item["id"][-1])


# ============================================================
# 1) OPEN / CLOSE
# ============================================================
def open_shop(state, category: str = "greeting") -> None:
    state.shop_open = True
    state.shop_index = 0
    state.shop_slot = min(state.shop_slot, len(state.weapon_slots) - 1)
    state.shop_message = shopkeeper_say(category, state.shop_message)
    state.projectiles.clear()
    state.player_bullets.clear()


def leave_shop(state) -> None:
    """Close the shop and start the next wave."""
    state.shop_open = False
    state.shop_message = None
    state.wave += 1
    start_wave(state)


# ============================================================
# 2) INPUT
# ============================================================
def shop_action(state, action: str) -> None:
    """Actions: up, down, num1..num4 (pick slot), confirm (buy), back / space (next wave)."""
    items = get_shop_items()
    if action == "up":
        state.shop_index = (state.shop_index - 1) % len(items)
    elif action == "down":
        state.shop_index = (state.shop_index + 1) % len(items)
    elif action.startswith("num"):
        slot = int(action[3:]) - 1
        if 0 <= slot < len(state.weapon_slots):
            state.shop_slot = slot
    elif action == "confirm":
        buy_item(state, items[state.shop_index])
    elif action in ("back", "space"):
        leave_shop(state)


def buy_item(state, item: dict) -> bool:
    """Try to buy. Always leaves a shopkeeper line explaining what happened."""
    previous = state.shop_message
    if item["type"] == "slot":
        if len(state.weapon_slots) >= slot_number(item):
            state.shop_message = shopkeeper_say("slot_owned", previous)
            return False
        if state.level < item["required_level"]:
            state.shop_message = shopkeeper_say("level_gate", previous, level=item["required_level"])
            return False
    if state.points < item["cost"]:
        state.shop_message = shopkeeper_say("no_funds", previous)
        return False

    state.points -= item["cost"]
    if item["type"] == "slot":
        state.weapon_slots.append(None)
        state.weapon_states.append(new_weapon_state())
        state.shop_message = shopkeeper_say("slot_unlocked", previous, name=item["name"])
    else:
        slot = state.shop_slot
        state.weapon_slots[slot] = item["id"]
        state.weapon_states[slot] = new_weapon_state()
        state.shop_message = shopkeeper_say("bought", previous, name=item["name"], slot=slot + 1)
    return True
