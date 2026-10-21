"""Measure a running FaceLock's CPU and memory.

Usage:  .venv\\Scripts\\python tools\\bench.py [--minutes 10] [--label present]
Attaches to FaceLock.exe (or `python -m facelock`), samples once per second, writes
bench_<label>.csv next to this script and prints a summary. Run once per state you
want to measure (sitting = present, away/locked = locked, during a call = busy).
"""
import argparse
import csv
import os
import statistics
import time

import psutil


def find():
    for p in psutil.process_iter(["name", "cmdline"]):
        name = (p.info["name"] or "").lower()
        cmd = " ".join(p.info["cmdline"] or []).lower()
        if name == "facelock.exe" or "-m facelock" in cmd or "run_facelock" in cmd:
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--label", default="run")
    args = ap.parse_args()
    proc = find()
    if proc is None:
        raise SystemExit("FaceLock is not running")
    ncpu = psutil.cpu_count()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"bench_{args.label}.csv")
    rows = []
    proc.cpu_percent(None)
    end = time.time() + args.minutes * 60
    print(f"Sampling PID {proc.pid} for {args.minutes} min -> {out}")
    while time.time() < end:
        time.sleep(1)
        try:
            cpu = proc.cpu_percent(None) / ncpu  # % of the whole machine
            mem = proc.memory_info()
        except psutil.NoSuchProcess:
            print("FaceLock exited")
            break
        rows.append((round(time.time(), 1), round(cpu, 2), round(mem.rss / 2 ** 20, 1), round(mem.private / 2 ** 20, 1)))
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "cpu_pct_machine", "working_set_mb", "private_mb"])
        w.writerows(rows)
    if rows:
        cpus = [r[1] for r in rows]
        ws = [r[2] for r in rows]
        print(f"CPU avg {statistics.mean(cpus):.2f}%  p95 {sorted(cpus)[int(len(cpus) * .95) - 1]:.2f}%  "
              f"max {max(cpus):.2f}%   (whole machine, {ncpu} logical CPUs)")
        print(f"Working set avg {statistics.mean(ws):.0f} MB  max {max(ws):.0f} MB  "
              f"growth {ws[-1] - ws[0]:+.0f} MB")


if __name__ == "__main__":
    main()
