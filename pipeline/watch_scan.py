# -*- coding: utf-8 -*-
"""
watch_scan.py — unattended watchdog for the long main scan.

Polls every 10 min: if the driver process family died (no python processes
running the p1_multicity driver) while the scan is incomplete (no
multicity_results.csv), relaunch with --skip-sim so completed phases are
reused (Phase A restarts from scratch if it died mid-phase; sweep phases
resume per level).

Design-free: only restarts the frozen driver with identical arguments.
"""
import os
import subprocess
import sys
import time

SCRIPTS = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\sim\scripts"
OUT = os.path.join(os.path.dirname(SCRIPTS), "outputs", "p1_multicity")
DONE = os.path.join(OUT, "multicity_results.csv")
MAX_RESTARTS = 8
POLL_SEC = 600


def driver_alive():
    """True if any python process has p1_multicity.py in its command line."""
    import subprocess as sp
    cmdlines = []
    try:
        out = sp.run(["wmic", "process", "where", "name='python.exe'",
                      "get", "commandline"], capture_output=True, text=True,
                     timeout=30).stdout or ""
        cmdlines.append(out)
    except Exception:
        pass
    if not any("p1_multicity.py" in c for c in cmdlines):
        try:
            out = sp.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
                 "| Select-Object -ExpandProperty CommandLine"],
                capture_output=True, text=True, timeout=90).stdout or ""
            cmdlines.append(out)
        except Exception:
            pass
    if not cmdlines:
        return True  # cannot determine -> assume alive (avoid double runs)
    return any("p1_multicity.py" in c for c in cmdlines)


def main():
    restarts = 0
    while True:
        if os.path.exists(DONE):
            print(f"[watchdog] results.csv exists -> scan complete, exiting",
                  flush=True)
            return
        if not driver_alive():
            restarts += 1
            if restarts > MAX_RESTARTS:
                print("[watchdog] too many restarts, giving up", flush=True)
                return
            print(f"[watchdog] driver down -> relaunch #{restarts} "
                  f"(--skip-sim)", flush=True)
            subprocess.Popen([sys.executable, "p1_multicity.py",
                              "--n-procs", "12", "--skip-sim"],
                             cwd=SCRIPTS,
                             stdout=open(os.path.join(OUT, "watchdog.log"),
                                         "a", encoding="utf-8"),
                             stderr=subprocess.STDOUT)
        else:
            print(f"[watchdog] alive ({restarts} restarts so far)", flush=True)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
