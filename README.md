# Enemy Survival

A small wave-based arena shooter I built for fun. Survive waves of aliens, buy weapons between waves, fight a boss every fifth wave.

Made with Python + [tcod](https://python-tcod.readthedocs.io/).

## Play

Grab a build from [Releases](../../releases):

- `EnemySurvival-x64.exe` — any 64-bit Windows PC
- `EnemySurvival.exe` — Windows on ARM (Snapdragon)

Your antivirus may warn about the `.exe`. It's a false positive that's common with Python games bundled into a single file — it's just the game, nothing else.

## Run from source

```
pip install tcod numpy Pillow
python main.py
```

## Controls

- WASD / arrows — move, Shift — sprint
- Space — open the shop (between waves)
- Up/Down — pick a shop item, 1-4 — pick the slot, Enter — buy
- 1-3 — pick a level-up

## Tests

```
python test_headless.py
```
