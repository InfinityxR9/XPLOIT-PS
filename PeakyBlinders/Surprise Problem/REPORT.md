# XPLOIT Dungeon -- Reverse Engineering Report
### Team: PeakyBlinders

---

## Overview

**Binary:** `xploit.exe` (13.4 MB, PE32+ x86-64)
**Framework:** Python 3.10 + Pygame 2.x, packaged with PyInstaller
**Structure:** 6 stages (`_S1`-`_S6`), each with a deliberate bug preventing completion

### Reverse Engineering Methodology

1. **Identification:** Used `file` and `strings` to identify PyInstaller magic (`MEI\x0c\x0b\x0a\x0b\x0e`) and Python 3.10 runtime (`python310.dll`).
2. **Extraction:** Used `pyinstxtractor.py` to unpack the PyInstaller archive, extracting `xploit.pyc` (the main game bytecode).
3. **Disassembly:** Used `xdis` (Python bytecode disassembler supporting 3.10) via `python -m xdis.disasm xploit.pyc` to generate a full 8,950-line disassembly.
4. **Reconstruction:** Manually translated every bytecode instruction back to readable Python source, mapping all classes, methods, constants, and control flow.
5. **Bug Analysis:** Identified the deliberate sabotage in each stage by analyzing game logic, physics constants, comparison operators, and unreachable code paths.

---

## Stage 1: "Collect & Exit" (`_S1`)

### What was broken
The door exit (`_Ox`) requires the player to collect coins to unlock. The `_Ox._c()` method checks `if p.cn >= 9999`, but only **3 collectible coins** (`_Rx` objects) exist in the stage. The threshold of 9999 is impossible to reach, so the door stays **permanently locked**.

### How I found it
Disassembled `_Ox._c()` (line 4050 of disassembly):
```
LOAD_FAST (p)
LOAD_ATTR (cn)
LOAD_CONST (9999)
COMPARE_OP (>=)
```
Cross-referenced with `_S1.__init__` which creates exactly 3 `_Rx` coins at positions `(240,400)`, `(400,330)`, `(560,260)`.

### The exact change
Changed the threshold in `_Ox._c()` from `9999` to `3`:
```python
# Before: if p.cn >= 9999:
if p.cn >= 3:
    self.op = True
```

### How I confirmed it works
After collecting all 3 coins, the door turns green ("OPEN") and the player can walk through it to complete the stage.

---

## Stage 2: "Timed Obstacle Course" (`_S2`)

### What was broken
The class attribute `_SP = 2` overrides the player's movement speed to 2 (normal is 5). With a 5-second timer, the player must traverse ~900 pixels of obstacles. At speed 2 (120 px/sec), this takes ~7.5 seconds -- **physically impossible** in the 5-second window.

### How I found it
Disassembled `_S2` class body (line 1404):
```
LOAD_CONST (2)
STORE_NAME (_SP)
```
And `_S2._u()` which continuously applies `p.sp = self._SP`.

Calculated: 905 pixels / (2 px/frame * 60 fps) = 7.54 seconds > 5 second limit.

### The exact change
Changed `_SP` from `2` to `5`, and increased the timer from 5 to 10 seconds for comfortable margin:
```python
# Before: _SP = 2
_SP = 5

# Before: self.ts = 5
self.ts = 10
```

### How I confirmed it works
With speed 5 (300 px/sec) and 10 seconds, the course can be completed comfortably.

---

## Stage 3: "Pit / Void Stage" (`_S3`)

### What was broken
**Bug 1:** The `_rdb()` method (rebuild bridge) exists but is **never called** in `__init__`. Without the bridge, there's an impassable void pit between x=150 and x=820.

**Bug 2:** An invisible ceiling check at `_SCY = _H - 239 = 361` resets the player whenever `p.r.top <= 361`. The exit and elevated platform are above this line, so the player can never reach them.

### How I found it
Disassembled `_S3.__init__` -- found `_rdb` is defined (line 6425) but never referenced in the init bytecode. Also found in `_S3._u()`:
```
LOAD_FAST (p)
LOAD_ATTR (r)
LOAD_ATTR (top)
LOAD_FAST (self)
LOAD_ATTR (_SCY)
COMPARE_OP (<=)
POP_JUMP_IF_FALSE ...
# resets player position
```

### The exact change
1. Added `self._rdb()` call at the end of `_S3.__init__()` to build the bridge
2. Removed the ceiling check block in `_S3._u()` that reset the player

```python
# Added in __init__:
self._rdb()

# Removed from _u():
# if p.r.top <= self._SCY:
#     p.r.topleft = (40, _H - _T - p._SH)
#     p.vy = 0
```

### How I confirmed it works
The bridge now spans the pit, allowing the player to walk across. Without the ceiling reset, the player can jump to the elevated platform and reach the exit.

---

## Stage 4: "Boss Fight" (`_S4`)

### What was broken
The boss enemy (`_Gx`) has a `_td()` (take damage) method that does:
```python
self.hp -= n
self.hp = self.mh  # Immediately resets HP back to maximum!
```
The boss's HP is reset to max after every hit, making it **immortal**. Since the exit only unlocks when `self.bx.dd` (boss dead) is True, the stage is unbeatable.

### How I found it
Disassembled `_Gx._td()` (line 4655):
```
LOAD_FAST (self)
DUP_TOP
LOAD_ATTR (hp)
LOAD_FAST (n)
INPLACE_SUBTRACT
ROT_TWO
STORE_ATTR (hp)        # self.hp -= n
LOAD_FAST (self)
LOAD_ATTR (mh)
LOAD_FAST (self)
STORE_ATTR (hp)        # self.hp = self.mh  <-- THE BUG
```

### The exact change
Removed the HP reset line:
```python
def _td(self, n):
    self.hp -= n
    # Removed: self.hp = self.mh
```

### How I confirmed it works
After shooting the boss 10 times (hp starts at 10, each bullet does 1 damage), `hp` reaches 0, `dd` becomes True, and the exit becomes accessible.

---

## Stage 5: "Inverted Gravity" (`_S5`)

### What was broken
Three compounding bugs:

1. **Inverted gravity:** `p.gv = _GI` sets gravity to `-0.5` (player floats upward instead of falling down)
2. **Reversed controls:** Uses `_mj()` instead of `_mi()`. In `_mj`, `K_LEFT` sets `vx = +sp` (moves right) and `K_RIGHT` sets `vx = -sp` (moves left)
3. **Teleporting exit:** The exit is a `_Ux` object whose `_u()` method teleports it to a random location whenever the player gets within 50 pixels

### How I found it
Disassembled `_S5.__init__` and `_S5._u()`:
- Init: `LOAD_GLOBAL (_GI)` / `STORE_ATTR (gv)` -- inverted gravity
- Update: `LOAD_METHOD (_mj)` -- wrong movement handler
- Exit: `_Ux` constructor at `(700, _T+4)` with teleport behavior in `_Ux._u()`

Disassembled `_Eq._mj()` to confirm swapped LEFT/RIGHT bindings.

### The exact change
```python
# 1. Changed gravity from _GI to _GN:
p.gv = _GN

# 2. Changed movement handler from _mj to _mi:
p._mi(k)

# 3. Replaced teleporting _Ux with static _Tx exit:
self.wx = _Tx(700, _H - _T - _T)
```

### How I confirmed it works
Player falls normally, controls work as expected (left=left, right=right), and the exit stays in place allowing the player to reach it.

---

## Stage 6: "Invisible Wall Maze" (`_S6`)

### What was broken
The exit `_Tx` at `(460, 255)` is placed **inside a sealed invisible box**. Four invisible wall rectangles form a closed box (x: 330-630, y: 140-410). These walls are added to `self.pf` (collision list) but deliberately **not drawn** in `_v()` (via `if p not in self._bw` check). With no openings, the exit is **physically unreachable**.

### How I found it
Disassembled `_S6.__init__` (line 7965), found 4 wall rects added:
- Top: `(330, 140, 300, 40)`
- Bottom: `(330, 370, 300, 40)`
- Left: `(330, 140, 40, 270)`
- Right: `(590, 140, 40, 270)`

The exit at `(460, 255)` is geometrically inside this box. In `_S6._v()`, the rendering loop skips walls in `self._bw`, confirming they're intentionally invisible.

### The exact change
Made the bottom wall only half-width, creating a gap for the player to enter:
```python
# Before: (self._BX, self._BY + self._BH - self._WT, self._BW, self._WT)
# After:  (self._BX, self._BY + self._BH - self._WT, self._BW // 2, self._WT)
```
This creates an opening on the right side of the bottom wall (x: 480-630) while preserving the maze challenge.

### How I confirmed it works
The player can now navigate through the gap in the bottom-right of the invisible box, reach the exit at `(460, 255)`, and complete the final stage.

---

## Summary Table

| Stage | Bug Type | Root Cause | Fix |
|-------|----------|-----------|-----|
| 1 | Impossible condition | Door threshold 9999 vs 3 coins | Changed threshold to 3 |
| 2 | Speed nerf + tight timer | Player speed 2 vs 5-sec timer | Changed speed to 5, timer to 10s |
| 3 | Missing call + ceiling trap | `_rdb()` never called; invisible ceiling | Added `_rdb()` call; removed ceiling check |
| 4 | HP reset | Boss HP resets to max after damage | Removed reset line |
| 5 | Triple sabotage | Inverted gravity + reversed controls + teleporting exit | Fixed gravity, controls, and exit type |
| 6 | Sealed invisible box | Exit trapped inside invisible walls | Added gap in bottom wall |
