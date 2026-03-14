# XPLOIT Vault System — Reverse Engineering Writeup

**Challenge:** `chal` — ELF 64-bit PIE binary  
**Goal:** Make the binary print `VAULT SYSTEM CLEARED.`  
**Submitted by:** [Your Name]

---

## 1 — Initial Recon

### `file`

```
chal: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV),
      dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2,
      BuildID[sha1]=57f99b9ae8cee316c0fc6f515f2096165b3b81c5,
      for GNU/Linux 3.2.0, not stripped
```

The binary is a 64-bit Position-Independent Executable (PIE). It is **not stripped**, which means all function names survive in the symbol table — a major advantage for reversing.

### `strings chal` — notable extracts

```
CERT_VALID
ID_9921
Connecting to legacy mainframe...
Legacy Admin Unlocked. Password: FAKE_PASSWORD_123
Backup vault empty. System compromised.
[WARN] Memory integrity violation detected.
Crypto module: ADVANCED mode.
XPLOIT_VAULT_SYSTEM_V2
[SYS] kernel handshake initialised.
.vault_state
[ERROR] Cannot write vault state. Check permissions.
[VAULT] Cold start detected. Vault state file initialised.
[VAULT] Authentication suspended. Re-run system to resume.
[-] FATAL: Kernel level debugger detected. Self-destructing.
Input Operator ID:
[+] AUTHORIZATION ACCEPTED: Level 999 Admin.
[+] OMEGA_TOKEN active: XPLOIT-2026-OMEGA
[-] AUTHORIZATION: Level 0 Guest.
[-] Access to Omega Protocol denied.
Vault Unlock Code:
  VAULT SYSTEM CLEARED.
  All authentication layers bypassed successfully.
[-] Vault unlock failed. Access denied.
Initializing XPLOIT Vault System...
Terminating session...
```

**Key observations from strings:**

- There is an anti-debug message: `FATAL: Kernel level debugger detected` — the binary tries to detect a debugger.
- There is a `.vault_state` file read/write — the binary uses the filesystem to persist state between runs.
- The target output `VAULT SYSTEM CLEARED.` and `Vault Unlock Code:` are both present — a vault unlock function exists.
- `FAKE_PASSWORD_123`, `1234`, `FAKE_` prefixes — deliberate red herrings in the binary.
- `Level 999 Admin` — the authentication check compares against the number 999.

### Symbol table — function names

`objdump -d chal` revealed all function names because the binary is not stripped:

```
legacy_auth_v1
unlock_backup_vault
initialize_telemetry
verify_network_cert
init_secure_channel
destroy_secure_channel
scan_memory_integrity
load_crypto_module
compute_session_hash
omega_protocol_legacy
emit_system_diagnostics
check_vault_state
security_watchdog
user_authentication_module
unlock_vault_sequence       ← target function
main
```

### Section layout (relevant)

| Section  | VirtAddr | FileOffset | Size  | Flags |
|----------|----------|------------|-------|-------|
| .text    | 0x1280   | 0x1280     | 0x91a | RX    |
| .rodata  | 0x2000   | 0x2000     | 0x4c6 | R     |
| .bss     | 0x4010   | —          | 0x38  | RW    |

Because the PIE base is 0 in the file, **virtual address = file offset** for code and read-only data. All patch offsets in this document are therefore also the file offsets.

### Global variables (in .bss)

| Name             | Address | Size | Role                                    |
|------------------|---------|------|-----------------------------------------|
| `g_argv0`        | 0x4020  | 8    | Pointer to `argv[0]`                    |
| `g_pid_seed`     | 0x4028  | 1    | `(pid ^ (pid>>8)) & 0xFF`               |
| `g_vault_byte`   | 0x4029  | 1    | First byte read from `.vault_state`     |
| `g_session_key`  | 0x4030  | 16   | Key array (zeroed at end of init)       |
| `g_session_active` | 0x4040 | 4  | Session flag (zeroed at end of init)    |

---

## 2 — Function Map

### `main` (0x1b0e) — orchestrator

```
main
 ├─ stores argv[0] → g_argv0
 ├─ puts("Initializing XPLOIT Vault System...")
 ├─ emit_system_diagnostics()
 ├─ check_vault_state()
 ├─ initialize_telemetry()
 ├─ verify_network_cert()
 ├─ init_secure_channel()
 ├─ scan_memory_integrity()
 ├─ load_crypto_module()
 ├─ compute_session_hash()
 ├─ destroy_secure_channel()
 ├─ omega_protocol_legacy(ptr_to_rodata)
 ├─ security_watchdog()
 ├─ user_authentication_module()    ← PROBLEM: always exits
 └─ puts(partial_rodata_string)     ← PROBLEM: calls puts instead of unlock
```

After patching, the final `call puts` will become `call unlock_vault_sequence`.

---

### `emit_system_diagnostics` (0x1752) — computes g_pid_seed

```c
pid_t pid = getpid();
g_pid_seed = (pid ^ (pid >> 8)) & 0xFF;
puts("[SYS] kernel handshake initialised.");
```

This seeds a global byte used later in the unlock code formula. The PID is runtime-dependent.

---

### `check_vault_state` (0x178b) — manages .vault_state file

**Cold start (file does not exist):**
1. Creates `.vault_state` in write-binary mode.
2. Writes 16 bytes computed from `time()` and a mixing loop.
3. Prints `[VAULT] Cold start detected.`
4. **Calls `exit(0)` — terminates on first run.**

**Warm start (file exists):**
1. Opens `.vault_state` in read-binary mode.
2. Reads 1 byte into `g_vault_byte`.
3. Returns normally.

The cold-start exit is intentional design — the binary must be run twice (or the file created manually) before it reaches the vault unlock stage.

---

### `initialize_telemetry` (0x13e9) — decoy

Seeds rand with time(), computes a random value, reduces it modulo 10000, left-shifts by 2, XORs with `0xdeadbeef`. Result stored only in a **stack-local variable** — never written to any global. Function is pure noise.

---

### `verify_network_cert` (0x146a) — always passes

Puts the string `"CERT_VALID_9921"` on the stack, checks that the first byte equals `'C'` (0x43). The first byte is always `'C'`. This check **always passes** and is a decoy.

---

### `init_secure_channel` (0x14ca) — fills g_session_key

Loops 16 times (i = 0..15) and fills `g_session_key[i]` with:

```
key[i] = ((time(NULL) >> (i & 7)) ^ (i * 0x37)) & 0xFF
```

Sets `g_session_active = 1`. The key is built but immediately zeroed out by `destroy_secure_channel` later — another decoy.

---

### `scan_memory_integrity` (0x1564) — decoy check that always passes

Builds an array of 32 bytes where `arr[i] = i ^ 0xAB`, sums them, and checks if the sum equals `0xDEAD` (57005). The actual sum is:

```
Σ(i ^ 0xAB) for i in 0..31  =  0x15F0  =  5616
```

5616 ≠ 57005, so the exit is **never taken**. The function is a red herring.

---

### `load_crypto_module` (0x160c) — decoy

Reads 8 bytes from `fake_key.1` (embedded at 0x2488, bytes: `2e 2e 2e 00 00 54 65 72`) and performs a rotate-left-1 LFSR step for each:

```
state = rotl8(state ^ key[i], 1)
```

Final state = `0x61`. If it were `0xFF`, it prints `"Crypto module: ADVANCED mode."`. Since it isn't `0xFF`, nothing is printed. No exit. Irrelevant.

---

### `compute_session_hash` (0x166e) — decoy

Computes an FNV-1a hash of the string `"XPLOIT_VAULT_SYSTEM_V2"` (result: `0x8864eb23`). Returns the value in `eax` but **nothing in `main` uses the return value**. Decoy.

---

### `destroy_secure_channel` (0x1536) — cleanup

`memset(g_session_key, 0, 16); g_session_active = 0;` — zeroes out the session key. Irrelevant to the challenge.

---

### `omega_protocol_legacy` (0x16c2) — decoy

Accepts a pointer argument. If the pointer is non-NULL and the first byte is non-zero, it XORs each byte of `fake_enc.0` (38 bytes at 0x24a0) with `0xAB`, storing the result in a stack buffer. Only the first byte of the result is ever read back. The decrypted value is never used after the function returns. This function is purely obfuscation.

---

### `security_watchdog` (0x18ef) — **ANTI-DEBUG (PROBLEM 1)**

```asm
mov edi, 0       ; PTRACE_TRACEME
call ptrace
test rax, rax
jns  pass        ; if rax >= 0 (no debugger) → skip
puts "[-] FATAL: Kernel level debugger detected. Self-destructing."
call exit(1)
pass:
ret
```

`ptrace(PTRACE_TRACEME, 0, 0, 0)` returns `0` when running normally, and `-1` when the process is already being traced (under GDB). The `jns` (jump-if-not-signed) at `0x1918` takes the safe branch when the return is 0. Under a debugger the branch is not taken and the binary exits.

**This needs patching to allow GDB-based analysis.**

---

### `user_authentication_module` (0x1936) — **BROKEN AUTH (PROBLEM 2)**

```c
int counter = 1;           // ← BUG: should be 999
printf("Input Operator ID: ");
fgets(input, 64, stdin);
if (counter == 999) {      // ← always fails: 1 ≠ 999
    puts("[+] AUTHORIZATION ACCEPTED: Level 999 Admin.");
    puts("[+] OMEGA_TOKEN active: XPLOIT-2026-OMEGA");
    return;                // ← returns to main
} else {
    puts("[-] AUTHORIZATION: Level 0 Guest.");
    puts("[-] Access to Omega Protocol denied.");
    exit(1);               // ← always reaches here
}
```

`counter` is hard-coded to `1` but the comparison requires `999` (0x3e7). The user's input is **read but never compared against counter** — the variable is never updated. The auth check therefore always fails and always calls `exit(1)`.

---

### `unlock_vault_sequence` (0x19f2) — **TARGET FUNCTION (PROBLEM 3)**

This function is never called from `main`. It computes an expected unlock code and compares it to user input:

```c
uint8_t expected = (g_pid_seed ^ g_vault_byte ^ strlen(g_argv0)) & 0xFF;
printf("Vault Unlock Code: ");
fgets(input, 16, stdin);
uint8_t entered = strtol(input, NULL, 16) & 0xFF;  // parsed as hex
if (entered == expected) {
    /* print VAULT SYSTEM CLEARED */
    exit(0);
} else {
    puts("[-] Vault unlock failed. Access denied.");
    exit(1);
}
```

---

### Decoy / irrelevant functions

| Function | Reason it is irrelevant |
|----------|------------------------|
| `legacy_auth_v1` | Never called from main; prints decoy string and returns |
| `unlock_backup_vault` | Never called from main; checks strcmp against `"1234"`, exits if match |

Both functions appear in the symbol table to confuse analysis but are unreachable during normal execution.

---

## 3 — Every Change Made

Three patches to the binary were applied, each at the exact instruction responsible for the problem.

### Preparation — vault state file

On first run, `check_vault_state` writes a 16-byte file and calls `exit(0)`. To avoid that, we create the file manually before running the patched binary:

```bash
python3 -c "open('.vault_state','wb').write(bytes(16))"
```

This gives `g_vault_byte = 0x00` (first byte of the file).

---

### Patch 1 — `security_watchdog`: bypass anti-debug (`0x1918`)

**What the original code was doing:**

```asm
; 0x1918
79 19   jns  0x1933    ; jump if ptrace returned >= 0 (not traced)
                       ; fall-through to exit(1) if under debugger
```

**Why it was a problem:**

The `jns` (jump-if-not-sign) is a *conditional* jump. Under a debugger, ptrace returns -1 (negative), so the sign flag is set and the branch is not taken — the binary falls through to the exit. This prevents using GDB to inspect runtime values.

**What was changed and why:**

```asm
; 0x1918  PATCHED
eb 19   jmp  0x1933    ; unconditional jump — always bypasses exit
```

Changed opcode byte from `0x79` (jns) to `0xeb` (jmp, short, unconditional). The offset byte `0x19` is unchanged. The jump now always reaches the safe `nop; ret` path regardless of the ptrace return value.

| Offset | Before | After | Meaning |
|--------|--------|-------|---------|
| 0x1918 | `79`   | `eb`  | `jns` → `jmp` |
| 0x1919 | `19`   | `19`  | offset unchanged |

---

### Patch 2 — `user_authentication_module`: fix counter initialisation (`0x1951`)

**What the original code was doing:**

```asm
; 0x1951
c7 45 ac 01 00 00 00    movl  $0x1, [rbp-0x54]   ; counter = 1
```

Later:
```asm
; 0x198c
3d e7 03 00 00          cmp  eax, 0x3e7           ; eax == 999?
75 20                   jne  guest_path            ; always taken (1 ≠ 999)
```

**Why it was a problem:**

The variable `counter` is initialised to `1`. The function reads user input with `fgets` but never touches `counter` — the user input has no effect on the outcome. The check `counter == 999` always evaluates to `false`, so `exit(1)` is always called, and `main` is never resumed.

**What was changed and why:**

```asm
; 0x1951  PATCHED
c7 45 ac e7 03 00 00    movl  $0x3e7, [rbp-0x54]  ; counter = 999
```

Changed the 32-bit immediate from `0x00000001` (little-endian: `01 00 00 00`) to `0x000003e7` (little-endian: `e7 03 00 00`). Now `counter == 999` at the comparison, the `jne` is not taken, and the admin path executes and returns to `main`.

| Offset | Before         | After          | Meaning           |
|--------|----------------|----------------|-------------------|
| 0x1954 | `01 00 00 00`  | `e7 03 00 00`  | immediate 1 → 999 |

---

### Patch 3 — `main`: replace `call puts` with `call unlock_vault_sequence` (`0x1b8e`)

**What the original code was doing:**

```asm
; 0x1b84
48 8d 05 e2 08 00 00    lea  rax, [rip+0x8e2]   ; rax = 0x246d (mid-string in rodata)
48 89 c7                mov  rdi, rax
; 0x1b8e
e8 cd f5 ff ff          call puts@plt            ; prints a partial, meaningless string
b8 00 00 00 00          mov  eax, 0
c9                      leave
c3                      ret
```

`unlock_vault_sequence` (at 0x19f2) is a complete, well-formed function in the binary — it contains the vault unlock prompt, the code verification, and all success/failure output. However, it is **never called** by `main`. After `user_authentication_module` returns (once patched), `main` calls `puts` on a stray pointer into the middle of a rodata string, then returns.

**Why it was a problem:**

The `call puts` at 0x1b8e is the wrong call target. `unlock_vault_sequence` is where the vault code verification and the `VAULT SYSTEM CLEARED` output live. Without calling it, the binary just prints garbage and exits cleanly, never reaching the goal.

**What was changed and why:**

```asm
; 0x1b8e  PATCHED
e8 5f fe ff ff          call unlock_vault_sequence    ; call 0x19f2
```

The `call` opcode (`0xe8`) is kept. Only the 4-byte relative offset changes.

Offset calculation:
```
next_PC = 0x1b8e + 5 = 0x1b93
target  = 0x19f2
offset  = 0x19f2 - 0x1b93 = -0x1a1 = 0xfffffe5f  (32-bit two's complement)
```

| Offset | Before          | After           | Meaning                   |
|--------|-----------------|-----------------|---------------------------|
| 0x1b8f | `cd f5 ff ff`   | `5f fe ff ff`   | call target: puts → unlock_vault_sequence |

---

### Patch script (Python)

```python
with open('chal', 'rb') as f:
    data = bytearray(f.read())

# Patch 1: security_watchdog — jns → jmp (0x1918)
data[0x1918] = 0xeb

# Patch 2: user_authentication_module — counter = 999 (0x1954)
data[0x1954] = 0xe7
data[0x1955] = 0x03

# Patch 3: main — call puts → call unlock_vault_sequence (0x1b8f)
data[0x1b8f] = 0x5f
data[0x1b90] = 0xfe
data[0x1b91] = 0xff
data[0x1b92] = 0xff

with open('chal_patched', 'wb') as f:
    f.write(data)
```

---

## 4 — The Unlock Code

### Where in the binary the computation lives

In `unlock_vault_sequence` (0x19f2), before the input prompt:

```asm
; 0x1a0e
0f b6 15 13 26 00 00    movzbl  g_pid_seed(%rip), %edx   ; edx = g_pid_seed
0f b6 05 0d 26 00 00    movzbl  g_vault_byte(%rip), %eax ; eax = g_vault_byte
89 d3                    mov     %edx, %ebx
31 c3                    xor     %eax, %ebx               ; ebx = pid_seed ^ vault_byte

48 8b 05 f9 25 00 00    mov     g_argv0(%rip), %rax
48 89 c7                 mov     %rax, %rdi
e8 71 f7 ff ff           call    strlen                    ; rax = strlen(argv[0])
31 d8                    xor     %ebx, %eax               ; eax ^= ebx
88 45 ce                 mov     %al, [rbp-0x32]          ; expected = low byte
```

Later:
```asm
; 0x1a80
e8 8b f7 ff ff           call    strtol(input, NULL, 16)  ; parse hex input
88 45 cf                 mov     %al, [rbp-0x31]          ; entered = low byte
0f b6 45 cf              movzbl  [rbp-0x31], %eax
3a 45 ce                 cmp     %al, [rbp-0x32]          ; compare entered vs expected
75 64                    jne     fail
```

### Formula

```
expected = (g_pid_seed  ^  g_vault_byte  ^  strlen(argv[0])) & 0xFF
```

### Each value and where it comes from

| Variable | Source | How computed |
|----------|--------|--------------|
| `g_pid_seed` | `emit_system_diagnostics` (0x1752) | `(getpid() ^ (getpid() >> 8)) & 0xFF` — runtime PID |
| `g_vault_byte` | `check_vault_state` (0x178b) | First byte read from `.vault_state` file |
| `strlen(argv[0])` | `main` (0x1b28) stores `argv[0]` into `g_argv0`; strlen called in unlock | Length of the path used to invoke the binary |

### Calculation for our run

```
Binary invoked as:  ./chal_patched          strlen = 14
.vault_state byte:  0x00                    (manually created, all zeros)
PID at runtime:     49
g_pid_seed:         (49 ^ (49 >> 8)) & 0xFF = (0x31 ^ 0x00) & 0xFF = 0x31

expected = 0x31 ^ 0x00 ^ 14
         = 0x31 ^ 0x0e
         = 0x3f

Enter as hex: "3f"
```

### How to compute it for any run

Because the PID changes on every execution, the unlock code must be computed dynamically. The helper script below starts the patched binary as a subprocess, reads its PID immediately (before the binary has a chance to call `getpid`), computes `g_pid_seed`, and feeds the correct code:

```python
import subprocess

binary = './chal_patched'
vault_byte = 0x00   # first byte of .vault_state (0x00 in our file)

proc = subprocess.Popen([binary], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
pid = proc.pid
g_pid_seed = (pid ^ (pid >> 8)) & 0xFF
expected   = (g_pid_seed ^ vault_byte ^ len(binary)) & 0xFF

stdout, _ = proc.communicate(
    input=b'ADMIN\n' + f'{expected:x}\n'.encode(),
    timeout=5
)
print(stdout.decode())
```

---

## 5 — Final Output

The following shows the complete terminal session after applying all three patches and running the helper script:

```
Initializing XPLOIT Vault System...
[SYS] kernel handshake initialised.
Input Operator ID:
[+] AUTHORIZATION ACCEPTED: Level 999 Admin.
[+] OMEGA_TOKEN active: XPLOIT-2026-OMEGA

Vault Unlock Code:
***************************************************
  VAULT SYSTEM CLEARED.
  All authentication layers bypassed successfully.
  Document your methodology and proceed to
  the next question.
***************************************************
```

**Return code: 0**

All three authentication layers were bypassed by:
1. Neutralising the anti-debug ptrace check (Patch 1)
2. Correcting the broken counter initialisation in the auth module (Patch 2)
3. Redirecting the final call in `main` to `unlock_vault_sequence` (Patch 3)
4. Computing the runtime vault code from PID, vault byte, and argv[0] length
