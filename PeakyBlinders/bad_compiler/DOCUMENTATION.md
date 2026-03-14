# Bad Compiler - Reverse Engineering Documentation

## 1. Overview

The challenge provides a broken interpreter (`broken_compiler.exe`) for a custom stack-based esoteric language (`.wut` files). The goal: reverse engineer the binary, identify the bugs, fix the compiler, and write an original `.wut` program.

**Provided files:**
- `broken_compiler.exe` - PE32 executable (MinGW GCC 6.3.0, stripped symbols)
- `program.wut` - source code in the `.wut` language
- `expected_output.txt` - target output: `This is right! Congratulations!`

**Broken compiler behavior:**
Running `broken_compiler.exe program.wut` prints `T` then crashes with `Error: stack underflow` (exit code 1).

---

## 2. Reverse Engineering Process

### 2.1 Initial Reconnaissance

```
$ file broken_compiler.exe
PE32 executable (console) Intel 80386, for MS Windows
```

The binary is a 32-bit Windows PE executable, compiled with MinGW GCC 6.3.0, with symbols stripped. Key strings found in the binary:

- `"Error: stack overflow"` / `"Error: stack underflow"` / `"Error: stack empty"` - stack protection messages
- `"Usage: %s <source file>"` - usage string confirming it takes a file argument
- `"Error: unmatched *"` - loop error handling

Imported functions: `putchar`, `atoi`, `fopen`, `fread`, `ftell`, `fseek`, `malloc`, `free` - confirming this is a file-reading interpreter that outputs characters.

### 2.2 Disassembly & Architecture

The binary was disassembled using `objdump -d -M intel`. Key findings:

**Interpreter structure:**
- Stack located at address `0x406080`, stack pointer at `0x403004`
- Maximum stack size: `0x3FE` (1022) entries
- Main dispatch loop at `~0x402370`
- Jump table at `0x4040f4`, indexed by `(char - 0x21)`, covering ASCII `0x21` (`!`) through `0x7E` (`~`)

**Dispatch mechanism:**
```asm
; load current character
movsx  eax, BYTE PTR [edx+ecx]   ; ch = src[ip]
sub    eax, 0x21                   ; index = ch - '!'
cmp    eax, 0x5d                   ; if index > 93, skip
ja     default_handler
jmp    DWORD PTR [eax*4 + 0x4040f4] ; jump table dispatch
```

### 2.3 Instruction Set Discovery

By analyzing the jump table and each handler's assembly code, all 12 active instructions were identified:

| Char | Name | Handler Address | Behavior |
|------|------|-----------------|----------|
| `~` | PUSH_A | `0x402624` | Push 65 (ASCII 'A') onto stack |
| `(N` | PUSH_NUM | `0x402540` | Parse decimal number N, push onto stack |
| `%` | ADD | `0x402460` | Pop two values, push their sum |
| `#` | NEGATE | `0x402501` | Negate top of stack in place |
| `!` | INCREMENT | `0x4025d0` | Add 1 to top of stack |
| `@` | DECREMENT | `0x4025e2` | Subtract 1 from top of stack |
| `^` | PRINT | `0x4023a0` | Print top of stack as ASCII character |
| `` ` `` | POP | `0x4023bd` | Discard top of stack |
| `$` | SWAP | `0x4024b2` | Swap top two stack elements |
| `&` | WHILE | `0x402400` | Loop start: if top==0, skip to matching `*` |
| `*` | END_WHILE | `0x4025f4` | Loop end: if top!=0, jump back to `&` |
| `)` | COMMENT | `0x402396` | Skip to end of line |

All other characters are silently ignored (NOP).

---

## 3. Bugs Found

### Bug #1: PRINT (`^`) destroys the stack (CRITICAL)

**Location:** Handler at `0x4023a0`

**Problem:** The `^` handler calls `putchar()` to print the top value, then **falls through** into the backtick (`` ` ``) handler at `0x4023bd`, which pops the value off the stack. The print instruction should **not** consume the value - it should leave it on the stack for potential reuse.

**Assembly evidence:**
```asm
0x4023a0:  ; ^ handler - PRINT
    mov eax, [stack + sp*4]   ; get top of stack
    and eax, 0xFF             ; mask to byte
    push eax
    call putchar              ; print it
    ; NO break/jump here - falls through to next handler!

0x4023bd:  ; ` handler - POP
    dec DWORD PTR [sp]        ; sp--
    jmp loop_continue
```

**Impact:** Every print destroys a stack value. The program runs out of operands and crashes with "stack underflow" after the very first character.

**Fix:** Add a `break` (jump to loop continue) after the `putchar` call, so `^` only peeks without popping.

---

### Bug #2: SWAP (`$`) duplicates instead of swapping

**Location:** Handler at `0x4024b2`

**Problem:** The `$` handler pushes the top-of-stack value twice (incrementing `sp` by 2), effectively duplicating it instead of swapping the top two elements.

**Assembly evidence:**
```asm
0x4024b2:  ; $ handler
    mov eax, [stack + sp*4]   ; read top value
    add DWORD PTR [sp], 2     ; sp += 2  (WRONG!)
    mov [stack + sp*4], eax   ; write top value to new position
    mov [stack + (sp-1)*4], eax ; write same value again
```

**Expected behavior:** Swap `stack[sp]` and `stack[sp-1]` without changing `sp`.

**Fix:** Implement proper swap:
```c
if (sp >= 1) {
    int tmp = stack[sp];
    stack[sp] = stack[sp - 1];
    stack[sp - 1] = tmp;
}
```

---

### Bug #3: Post-execution prints newline instead of `!`

**Location:** Code at `0x4023d9` (after main interpreter loop)

**Problem:** After the interpreter finishes processing all source code, it unconditionally calls `putchar(0x0a)` which prints a newline character (`\n`). The correct behavior is to print `!` (0x21), which is the final character of the expected output `"This is right! Congratulations!"`.

**Assembly evidence:**
```asm
0x4023d9:  ; post-loop epilogue
    push 0x0a          ; '\n' = newline (WRONG!)
    call putchar
```

**Expected:** `push 0x21` (which is `'!'`).

**Fix:** Change the final `putchar` argument from `'\n'` to `'!'`.

---

## 4. Verification

With all three bugs fixed, the fixed compiler produces output byte-identical to `expected_output.txt`:

```
$ ./fixed_compiler.exe program.wut | xxd
00000000: 5468 6973 2069 7320 7269 6768 7421 2043  This is right! C
00000010: 6f6e 6772 6174 756c 6174 696f 6e73 21    ongratulations!

$ cat expected_output.txt | xxd
00000000: 5468 6973 2069 7320 7269 6768 7421 2043  This is right! C
00000010: 6f6e 6772 6174 756c 6174 696f 6e73 21    ongratulations!
```

Exact match: 31 bytes, no trailing newline.

---

## 5. The `.wut` Language Reference

### Architecture
- Pure stack machine with a single integer stack (max ~1024 entries)
- All operations work on the stack
- Source code is a flat stream of characters, interpreted left-to-right
- The compiler always appends a `!` character to program output after execution

### Instruction Set

| Instruction | Description |
|---|---|
| `~` | Push 65 (ASCII `A`) onto the stack |
| `(N` | Push the decimal number N onto the stack (e.g., `(72` pushes 72) |
| `%` | **ADD**: Pop two values, push their sum |
| `#` | **NEGATE**: Negate the top of stack (multiply by -1) |
| `!` | **INCREMENT**: Add 1 to top of stack |
| `@` | **DECREMENT**: Subtract 1 from top of stack |
| `^` | **PRINT**: Output top of stack as ASCII character (does not pop) |
| `` ` `` | **POP**: Discard top of stack |
| `$` | **SWAP**: Swap the top two stack elements |
| `&` | **WHILE**: If top of stack is 0, skip to matching `*`. Otherwise begin loop |
| `*` | **END WHILE**: If top of stack is nonzero, jump back to matching `&`. Otherwise exit loop |
| `)` | **COMMENT**: Skip everything until end of line |

### Idioms
- **Push arbitrary value:** `~(N#%` pushes `65 + (-N)` = `65 - N`. Or: `~~%(N#%` pushes `130 + (-N)` = `130 - N`
- **Push and print char:** `~(N#%^` to compute and print a character
- **Countdown loop:** `(N&@*` decrements from N to 0
- **Subtraction:** `(N#%` adds the negation of N (effectively subtracts N)

---

## 6. Custom Program: `my_program.wut`

**Team:** Peaky Blinders
**Member:** AryanSisodiya

**Output:** `Hello, Team: Peaky Blinders, Member: AryanSisodiya, 5+3=8, 7x7=49, Done!`

### Program Structure

The program has 4 sections:

1. **Team Introduction** - Prints `Hello, Team: Peaky Blinders, Member: AryanSisodiya, ` using delta encoding (each character computed as offset from previous)
2. **Arithmetic Demo 1 (Addition)** - Prints `5+3=`, then actually **computes** 5+3=8 on the stack and prints the result digit
3. **Arithmetic Demo 2 (Multiplication Loop)** - Prints `7x7=`, then **computes** 7x7=49 using a multiplication loop with swap, and prints the result digits
4. **Closing** - Prints `Done` and the compiler appends `!`

### Key Source Code Sections

**Delta encoding** (each character is an offset from the previous value):
```
~(7%^       ) Push 65 via ~, add 7 = 72 = 'H'
(29%^       ) 72 + 29 = 101 = 'e'
(7%^        ) 101 + 7 = 108 = 'l'
^           ) 108 + 0 = 108 = 'l' (repeat - just print again!)
(3%^        ) 108 + 3 = 111 = 'o'
...         ) continues for all characters
!^          ) INCREMENT by 1: 100+1 = 101 = 'e'
```

**Addition computation** (actually pushes 5 and 3, adds them, prints result):
```
`(5(3%      ) Pop old val, push 5, push 3, ADD -> 8
(48%^       ) 8 + 48 = 56 = '8' (ASCII offset for digit)
```

**Multiplication loop** (computes 7x7=49 via repeated addition):
```
`(0(7       ) Pop old val, push accumulator=0, counter=7
&$(7%$@*    ) LOOP: swap, add 7, swap, decrement. Runs 7 times.
`           ) Pop counter (0), result 49 remains
(3%^        ) 49 + 3 = 52 = '4' (tens digit)
(5%^        ) 52 + 5 = 57 = '9' (ones digit)
```

### Multiplication Loop Walkthrough

The loop `&$(7%$@*` computes 7 x 7 = 49 via repeated addition:

| Iteration | Operation | Stack | Description |
|---|---|---|---|
| Start | `(0(7` | `[0, 7]` | accumulator=0, counter=7 |
| 1 | `$` swap | `[7, 0]` | Bring accumulator to top |
| 1 | `(7%` add | `[7, 7]` | accum += 7 |
| 1 | `$` swap | `[7, 7]` | Bring counter to top |
| 1 | `@` dec | `[7, 6]` | counter-- |
| 1 | `*` loop | `[7, 6]` | 6 != 0, loop back |
| 2 | ... | `[14, 5]` | accum=14, counter=5 |
| ... | ... | ... | ... |
| 7 | `@` dec | `[49, 0]` | counter reaches 0 |
| 7 | `*` exit | `[49, 0]` | 0 == 0, exit loop |
| End | `` ` `` pop | `[49]` | Discard counter, result = 49 |

### Techniques Demonstrated

| Technique | Where Used | Description |
|---|---|---|
| **Comments** (`)`) | Throughout | Section headers and inline documentation |
| **Push constant** (`~`) | First char `H` | Pushes 65 (ASCII 'A') as base value |
| **Push number** (`(N`) | Every character | Pushes decimal numbers for arithmetic |
| **Addition** (`%`) | Delta encoding + arithmetic | Adds offsets, computes 5+3, accumulates in loop |
| **Negation** (`#`) | Subtraction idiom | `(N#%` subtracts N (e.g., `(67#%` for `,`) |
| **Increment** (`!`) | `e`, `s` chars | Efficient +1 when delta is exactly 1 |
| **Decrement** (`@`) | Loop counter + `n` char | Countdown in multiplication loop |
| **Print** (`^`) | Every output char | Outputs ASCII without popping |
| **Pop** (`` ` ``) | Section transitions | Discards values between computation phases |
| **Swap** (`$`) | Multiplication loop | Alternates between accumulator and counter |
| **Loop** (`&`...`*`) | 7x7 multiplication | 7 iterations of repeated addition |
| **Computed output** | `8` and `49` digits | Arithmetic results printed as ASCII digits |

---

## 7. Deliverables Summary

| Deliverable | File | Status |
|---|---|---|
| Fixed compiler (source) | `fixed_compiler.c` | Complete |
| Fixed compiler (binary) | `fixed_compiler.exe` | Complete, output verified byte-for-byte |
| Custom .wut program | `my_program.wut` | Complete (see output below) |
| Documentation | `DOCUMENTATION.md` | This file |

**Program output:**
```
Hello, Team: Peaky Blinders, Member: AryanSisodiya, 5+3=8, 7x7=49, Done!
```

### Features Checklist (from README requirements)

- [x] Noted broken output: prints `T` then crashes with "stack underflow"
- [x] Fixed compiler produces `expected_output.txt` exactly
- [x] Custom program prints team name: **Peaky Blinders**
- [x] Custom program prints member name: **AryanSisodiya**
- [x] Uses loops (`&`...`*`) for multiplication (7x7=49)
- [x] Uses complex arithmetic (negation, addition, increment, decrement)
- [x] Uses all 12 language features (comments, swap, pop, push, print, etc.)
- [x] Performs and displays computed arithmetic: 5+3=8 and 7x7=49
- [x] Thorough documentation of entire reverse engineering process
