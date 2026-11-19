"""Minimal GPU job queue for the study.

    python -m train_aero.runs.scheduler [--jobs configs/jobs.txt] [--gpus 0 1] [--reserve 1:21]

Re-reads the job file every loop, so jobs can be appended while it runs.  Line format
(file order = priority)::

    <fold> <model: gt|smart|abupt> <seed> <tag|-> [overrides...]

Each job runs `scripts/run_one.sh <gpu> ...`.  A GPU takes a job only when it runs no other
job of ours, foreign processes use < 3 GB, and the free memory minus the reserve covers the
model's need.  Create `<workdir>/STOP` to stop launching new jobs.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import time
from pathlib import Path

from train_aero.paths import CONFIG_DIR, REPO_ROOT, layout

NEED_GB = {"gt": 22.0, "abupt": 21.0, "smart": 13.0}   # peak training memory + inference headroom
FOREIGN_MAX_GB = 3.0
POLL_S = 30
IDLE_EXIT_POLLS = 20


def gpu_memory_gb(gpu: int) -> tuple[float, float]:
    out = subprocess.run(["nvidia-smi", "-i", str(gpu), "--query-gpu=memory.used,memory.total",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True).stdout
    used, total = (float(x) / 1024 for x in out.split(","))
    return used, total


def parse_jobs(path: Path) -> list[list[str]]:
    return [line.split(None, 4) for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--jobs", type=Path, default=CONFIG_DIR / "jobs.txt")
    ap.add_argument("--gpus", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--reserve", nargs="*", default=["0:1.5", "1:21"],
                    help="GPU:GB kept free for other users, e.g. 1:21")
    ap.add_argument("--max-jobs", type=int, default=2,
                    help="co-running jobs on one card gave no throughput gain; default one per GPU")
    args = ap.parse_args()
    reserve = {int(k): float(v) for k, v in (r.split(":") for r in args.reserve)}

    lay = layout()
    (lay.workdir / "logs").mkdir(parents=True, exist_ok=True)
    log = open(lay.workdir / "logs/scheduler.log", "a")   # noqa: SIM115  (kept open for child processes)

    def say(*msg: object) -> None:
        print(time.strftime("%m-%d %H:%M:%S"), *msg, file=log, flush=True)

    running: dict[str, tuple[subprocess.Popen, int, float]] = {}
    done: set[str] = set()
    idle = 0
    say("scheduler start")
    while True:
        for key in list(running):
            proc, _, _ = running[key]
            if proc.poll() is not None:
                say("finished", key, "rc", proc.returncode)
                done.add(key)
                del running[key]
        pending = [j for j in parse_jobs(args.jobs)
                   if " ".join(j[:4]) not in running and " ".join(j[:4]) not in done]
        if (lay.workdir / "STOP").exists():
            pending = []
        for job in pending:
            if len(running) >= args.max_jobs:
                break
            key, need = " ".join(job[:4]), NEED_GB[job[1]]
            for gpu in args.gpus:
                used, total = gpu_memory_gb(gpu)
                ours = sum(n for _, g, n in running.values() if g == gpu)
                foreign = max(0.0, used - ours)
                if ours == 0 and foreign < FOREIGN_MAX_GB and total - reserve.get(gpu, 0.0) - foreign >= need:
                    extra = shlex.split(job[4]) if len(job) > 4 else []
                    cmd = [str(REPO_ROOT / "scripts/run_one.sh"), str(gpu), *job[:4], *extra]
                    running[key] = (subprocess.Popen(cmd, stdout=log, stderr=log), gpu, need)
                    say("start", key, "gpu", gpu, "extra", extra)
                    time.sleep(20)
                    break
        idle = idle + 1 if not running and not pending else 0
        if idle > IDLE_EXIT_POLLS:
            say("queue empty, exit")
            break
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
