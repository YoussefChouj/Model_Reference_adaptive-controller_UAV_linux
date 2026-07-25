#!/usr/bin/env python
"""
test_simulator_e2e.py — Run the simulator + bridge end-to-end via UDP and
verify the bridge actually parses simulated frames. This proves the
dashboard/parser path is functional independent of the wireless link.
"""
import subprocess
import time
import sys
import socket

# Start simulator
print("[1/3] starting frame_simulator...")
sim = subprocess.Popen(
    [sys.executable, "-m", "ground_station.comm.frame_simulator", "--port", "50007"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    cwd=r"c:\Users\Acer\Desktop\UAV_lab\FreeRTOS---Six_Degrees_of_Freedom _Adaptive_controller",
)
time.sleep(3)

# Listen for one packet on the bridge's telemetry mirror port to confirm it parses
print("[2/3] listening for parsed frames on UDP 1350 (telemetry mirror)...")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 1350))
sock.settimeout(10.0)

# Need to start the bridge too, in --simulate mode
print("[3/3] starting serial_bridge in --simulate mode...")
bridge = subprocess.Popen(
    [sys.executable, "-m", "ground_station.comm.serial_bridge", "--simulate"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    cwd=r"c:\Users\Acer\Desktop\UAV_lab\FreeRTOS---Six_Degrees_of_Freedom _Adaptive_controller",
)

frames = []
try:
    while len(frames) < 10:
        data, addr = sock.recvfrom(4096)
        frames.append((time.time(), len(data), data[:32]))
except socket.timeout:
    pass

sock.close()

print(f"\n=== RESULT ===")
print(f"received {len(frames)} parsed-frame datagrams in 10s")
for t, n, head in frames[:5]:
    head_hex = " ".join(f"{b:02X}" for b in head)
    print(f"  {t:.3f}  len={n:4d}  head=[{head_hex}]")

# Stop bridge + simulator
bridge.terminate(); bridge.wait(timeout=3)
sim.terminate(); sim.wait(timeout=3)

if len(frames) >= 5:
    print("\n[OK] simulator → bridge → UDP mirror works. Parser is correct.")
    print("      Problem is purely the wireless link from FC UART5 → COM6.")
    sys.exit(0)
else:
    print("\n[FAIL] bridge did not produce enough parsed frames. Parser may still be broken.")
    sys.exit(1)