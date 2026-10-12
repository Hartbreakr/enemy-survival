"""save.py - reading and writing the save file.

This module owns the only data that survives between runs: the high score
and the set of enemy kinds the player has ever met (for the encyclopedia).

The file is a small JSON object:  {"highscore": 1234, "seen": ["normal", ...]}

Older versions kept just the high score as a bare number in highscore.txt.
If that file exists and save.json does not, it is read once and copied into
save.json (the old file is left alone).

Missing or corrupt files count as a fresh save.
"""
import json

import config

# Tests can point these at temporary files.
SAVE_FILE = config.SAVE_FILE
HIGHSCORE_FILE = config.HIGHSCORE_FILE


def fresh_save() -> dict:
    return {"highscore": 0, "seen": []}


def _read_old_highscore() -> int | None:
    """The pre-JSON format: one integer in highscore.txt. None if absent/bad."""
    try:
        with open(HIGHSCORE_FILE, encoding="utf-8") as file:
            return int(file.read().strip())
    except (OSError, ValueError):
        return None


def load_save() -> dict:
    """Return {"highscore": int, "seen": list[str]}, migrating the old file if needed."""
    try:
        with open(SAVE_FILE, encoding="utf-8") as file:
            raw = json.load(file)
    except (OSError, ValueError):
        raw = None

    if raw is None:
        data = fresh_save()
        old = _read_old_highscore()
        if old is not None:
            data["highscore"] = old
            write_save(data["highscore"], data["seen"])
        return data

    data = fresh_save()
    if isinstance(raw, dict):
        try:
            data["highscore"] = int(raw.get("highscore", 0))
        except (TypeError, ValueError):
            pass
        seen = raw.get("seen", [])
        if isinstance(seen, list):
            data["seen"] = [kind for kind in seen if isinstance(kind, str)]
    return data


def write_save(highscore: int, seen) -> None:
    """Write the whole save file. `seen` may be any iterable of kind names."""
    data = {"highscore": int(highscore), "seen": sorted(set(seen))}
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
    except OSError:
        pass


def load_highscore() -> int:
    """Shortcut used by tests: just the high score."""
    return load_save()["highscore"]
