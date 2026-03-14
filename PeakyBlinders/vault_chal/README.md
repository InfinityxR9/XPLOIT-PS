# XPLOIT Vault System

## What You Are Given

One binary file: `chal`

Nothing else.

---

## The Task

Run the binary. Make it print:

```
VAULT SYSTEM CLEARED.
All authentication layers bypassed successfully.
```

---

## How to Submit

Fork this repository, add your writeup as a folder with your name, and open a pull request.

Your folder must contain:

- Your writeup document (PDF or Markdown)
- All screenshots referenced in the writeup
- Any scripts or tools you wrote

---

## What Your Writeup Must Cover

### 1. Initial Recon
What you found before making any changes to the binary. Document everything you ran and everything you noticed. Screenshots required.

### 2. Function Map
Every function you found in the binary. For each one write what it does. For the ones you decided were irrelevant explain how you reached that conclusion.

### 3. Every Change You Made
For every change you made to the binary document:
- What the original code was doing at that location
- Why it was a problem
- What you changed it to and why that change specifically

For every step in your entire process — not just binary changes — include a screenshot and an explanation of what you were doing and what you observed. If you cannot explain something you did, do not include it.

You may use any tool you like — Ghidra, objdump, gdb, Python, a hex editor, anything. What matters is that you understood what you were doing.

### 4. The Unlock Code
The binary will ask you for an unlock code. Document:
- Where in the binary you found how this code is computed
- Every value that feeds into the computation and exactly where each one came from
- The calculation you performed to get your specific code

### 5. Final Output
A screenshot showing `VAULT SYSTEM CLEARED` with the full terminal output visible.

---

## Scoring

**Correctness** — your documented steps must produce `VAULT SYSTEM CLEARED` when followed.

**Understanding** — every change you make to the binary must be explained correctly and specifically. What you changed, why that location, and what it achieves. Vague or incorrect explanations score zero for that change even if the binary works.

**Quality of changes** — changes that preserve and work with the logic of the binary score higher than changes that discard or bypass it entirely. Reaching the output through a shortcut that skips over what the binary is actually doing will score lower than taking the path that engages with it directly. This applies even if both approaches produce the same final output.

Screenshots, clear explanations, and evidence that you understood what you were reversing will always score higher than a working binary with poor documentation.

---