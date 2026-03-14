#!/usr/bin/env python3
"""
XPLOIT Vault System — solver script
Prereqs:  ./chal_patched must exist (apply patches first)
          .vault_state   must exist (created by this script)
"""
import subprocess, os

# Create .vault_state with a known first byte (0x00)
with open('.vault_state', 'wb') as f:
    f.write(bytes(16))

binary    = './chal_patched'
vault_byte = 0x00   # first byte of .vault_state

proc = subprocess.Popen(
    [binary],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
pid = proc.pid
g_pid_seed = (pid ^ (pid >> 8)) & 0xFF
expected   = (g_pid_seed ^ vault_byte ^ len(binary)) & 0xFF

print(f"[*] PID={pid}  g_pid_seed=0x{g_pid_seed:02x}  vault_byte=0x{vault_byte:02x}")
print(f"[*] strlen(argv[0])={len(binary)}  expected=0x{expected:02x} => hex input: '{expected:x}'")
print()

stdout, stderr = proc.communicate(
    input=b'ADMIN\n' + f'{expected:x}\n'.encode(),
    timeout=5
)
print(stdout.decode())
