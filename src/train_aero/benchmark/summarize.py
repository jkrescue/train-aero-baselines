"""Summarise the PhysicsNeMo-CFD benchmark outputs into one Markdown file.

    python -m train_aero.benchmark.summarize [--results-dir DIR] [--out FILE]

Reads `<results-dir>/<fold>/benchmark_results.json`.  Field metrics are the engine's per-case
values averaged over the fold's test cases; integrated quantities follow `train_aero.stats`.
A cost table is appended from the work directory's `runs/*/run.json` when available.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

from train_aero.folds import FOLDS, MODELS
from train_aero.paths import layout
from train_aero.stats import error_over_span, paired_difference

MODEL_NAMES = list(MODELS.values())          # GeoTransolver, SMART, AB-UPT
SHEAR = {a: f"l2_shear_stress_wall_shear_stress_true_{a}_l2_error" for a in "xyz"}
COLUMNS = [("Cp", "Cp L2", False), ("Cp_aw", "Cp L2 (area-wt)", False), ("tau_x", "τx L2", False),
           ("tau_y", "τy L2", False), ("tau_z", "τz L2", False), ("Cd", "Cd rel err", True),
           ("Cs", "Cs err/span", True), ("Cl", "Cl err/span", True), ("CMx_lee", "C_Mx,lee err/span", True)]
PAIRS = (("SMART", "GeoTransolver"), ("AB-UPT", "GeoTransolver"), ("AB-UPT", "SMART"))


def load(results_dir: Path, fold: str) -> dict[str, dict]:
    f = results_dir / fold / "benchmark_results.json"
    if not f.exists():
        return {}
    return {r["model"]: r for r in json.loads(f.read_text()) if not r.get("skipped")}


def fold_stats(run: dict) -> dict[str, float]:
    rows = run["per_case"]

    def mean(key: str) -> float:
        return st.mean(r["metrics"][key] for r in rows)

    out = {"Cp": mean("l2_pressure"), "Cp_aw": mean("l2_pressure_area_weighted"),
           "tau_x": mean(SHEAR["x"]), "tau_y": mean(SHEAR["y"]), "tau_z": mean(SHEAR["z"]),
           "Cd": mean("drag_error")}
    for key, metric in (("Cs", "side_force"), ("Cl", "lift"), ("CMx_lee", "roll_moment_lee")):
        out[key], out[key + "_sign"] = error_over_span(rows, metric)
    return out


def fmt(v: float | None, pct: bool = False) -> str:
    return "—" if v is None else (f"{100 * v:.1f}%" if pct else f"{v:.4f}")


def table_header(first: list[str], extra: list[str] = ()) -> list[str]:
    head = first + [c[1] for c in COLUMNS] + list(extra)
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]


def family_section(family: str, folds: list[str], data: dict[str, dict]) -> list[str]:
    lines = [f"## {family}: per fold", "", *table_header(["fold", "model"])]
    per: dict[str, dict[str, dict]] = {m: {} for m in MODEL_NAMES}
    for f in folds:
        for m in MODEL_NAMES:
            run = data[f].get(f"{m}/seed0")
            if run:
                per[m][f] = s = fold_stats(run)
                lines.append(f"| {f} | {m} | " + " | ".join(fmt(s[k], p) for k, _, p in COLUMNS) + " |")

    lines += ["", f"## {family}: mean over folds (n = folds available)", "",
              *table_header(["model", "n"], ["Cs sign ok", "C_Mx,lee sign ok"])]
    for m in MODEL_NAMES:
        if not per[m]:
            continue
        agg = defaultdict(list)
        for s in per[m].values():
            for k, v in s.items():
                agg[k].append(v)
        lines.append(f"| {m} | {len(per[m])} | " + " | ".join(fmt(st.mean(agg[k]), p) for k, _, p in COLUMNS)
                     + f" | {fmt(st.mean(agg['Cs_sign']), True)} | {fmt(st.mean(agg['CMx_lee_sign']), True)} |")

    lines += ["", f"## {family}: paired differences over common folds (positive = first model worse)", "",
              "| pair | metric | folds | mean diff | sd | t = mean/SE | folds where first is worse |",
              "|---|---|---|---|---|---|---|"]
    for a, b in PAIRS:
        common = [f for f in folds if f in per[a] and f in per[b]]
        if len(common) < 2:
            continue
        for key, name in (("Cp", "Cp L2"), ("CMx_lee", "C_Mx,lee err/span")):
            d = paired_difference([per[a][f][key] for f in common], [per[b][f][key] for f in common])
            lines.append(f"| {a} − {b} | {name} | {d['n']} | {d['mean']:+.4f} | {d['sd']:.4f} | {d['t']:+.2f} "
                         f"| {d['a_worse']}/{d['n']} |")
    return lines + [""]


def seed_section(data: dict[str, dict]) -> list[str]:
    lines = ["## Seed noise (default settings, seeds 0/1/2)", "",
             "| fold | model | n | Cp L2 mean | Cp L2 sd | C_Mx,lee err/span mean | values (Cp L2) |",
             "|---|---|---|---|---|---|---|"]
    for f in FOLDS:
        for m in MODEL_NAMES:
            runs = [data[f][k] for k in sorted(data[f]) if re.fullmatch(rf"{re.escape(m)}/seed\d", k)]
            if len(runs) < 2:
                continue
            s = [fold_stats(r) for r in runs]
            cp = [x["Cp"] for x in s]
            lines.append(f"| {f} | {m} | {len(s)} | {st.mean(cp):.4f} | {st.stdev(cp):.4f} | "
                         f"{fmt(st.mean(x['CMx_lee'] for x in s), True)} | {' / '.join(f'{v:.4f}' for v in cp)} |")
    return lines + [""]


def variant_section(data: dict[str, dict]) -> list[str]:
    lines = ["## Variants (tagged runs: learning rate, points, area-weighted loss, centred AB-UPT, extra seeds)",
             "", *table_header(["fold", "run"])]
    for f in FOLDS:
        for label, run in sorted(data[f].items()):
            if not label.endswith("/seed0"):
                s = fold_stats(run)
                lines.append(f"| {f} | {label} | " + " | ".join(fmt(s[k], p) for k, _, p in COLUMNS) + " |")
    return lines


def cost_section(runs_dir: Path) -> list[str]:
    rows = defaultdict(list)
    for rj in sorted(runs_dir.rglob("run.json")):
        meta = json.loads(rj.read_text())
        if meta.get("tag") != "-" or meta.get("seed") != 0 or meta.get("train_rc") != 0:
            continue
        params = None
        metrics = rj.parent / "train/metrics.jsonl"
        if metrics.exists():
            with metrics.open() as fh:
                for line in fh:
                    if '"num_parameters"' in line:
                        params = json.loads(line)["num_parameters"]
                        break
        mem = re.search(r"[0-9.]+", meta.get("peak_train_mem", "")) if meta.get("peak_train_mem") else None
        rows[(meta["family"], MODELS[meta["model"]])].append(
            (meta["train_seconds"], float(mem.group()) if mem else None, params))
    if not rows:
        return []
    lines = ["", "## Cost (seed 0, default settings, 300 epochs)", "",
             "| family | model | runs | parameters | train time / run | peak train memory |",
             "|---|---|---|---|---|---|"]
    for family in ("noses", "lengths"):
        for m in MODEL_NAMES:
            r = rows.get((family, m))
            if not r:
                continue
            params = next((p for _, _, p in r if p), None)
            mems = sorted({round(x, 1) for _, x, _ in r if x is not None})
            mem = "—" if not mems else f"{mems[0]:.1f} GB" if len(mems) == 1 else f"{mems[0]:.1f}–{mems[-1]:.1f} GB"
            lines.append(f"| {family} | {m} | {len(r)} | {f'{params / 1e6:.2f} M' if params else '—'} | "
                         f"{st.mean(t for t, _, _ in r) / 60:.0f} min | {mem} |")
    return lines


def main() -> None:
    lay = layout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results-dir", type=Path, default=lay.bench / "results")
    ap.add_argument("--runs-dir", type=Path, default=lay.runs)
    ap.add_argument("--out", type=Path, default=None, help="default: <results-dir>/BENCH_SUMMARY.md")
    args = ap.parse_args()

    data = {f: load(args.results_dir, f) for f in FOLDS}
    lines = ["# PhysicsNeMo-CFD benchmark summary", "",
             "Engine: `physicsnemo.cfd.evaluation.benchmarks.engine.run_benchmark`; metrics `l2_pressure`, "
             "`l2_pressure_area_weighted`, `l2_shear_stress`, `drag`, `lift` (built-in) + `side_force`, "
             "`roll_moment_lee` (registered). Seed 0, default settings, unless stated.", ""]
    for family in ("noses", "lengths"):
        lines += family_section(family, [f for f, s in FOLDS.items() if s["family"] == family], data)
    lines += seed_section(data) + variant_section(data) + cost_section(args.runs_dir)
    out = args.out or args.results_dir / "BENCH_SUMMARY.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
