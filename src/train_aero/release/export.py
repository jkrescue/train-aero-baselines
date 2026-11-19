"""Export the publishable artefacts of a work directory into the repository (and a release folder).

    python -m train_aero.release.export --repo . [--checkpoints DIR]

Into `<repo>/results/`:
  summary.md                          benchmark summary (train_aero.benchmark.summarize)
  benchmark/<fold>/benchmark_results.{json,csv}
  figures/<fold>/*.png                report visuals of the benchmark
  baselines/<fold>.json               no-learning baselines
  runs/<family>/<model>/<fold>/<run>/ run.json, score.json, history.csv, resolved_config.yaml,
                                      bench_infer_config.yaml
  checkpoints.json                    manifest of the released checkpoints (sha256, size, run)

With `--checkpoints DIR`, the final `.mdlus` of every run is copied to DIR as
`<family>-<model>-<fold>-<run>.mdlus` for upload as GitHub release assets.

Absolute paths are rewritten to `${TRAIN_AERO_WORKDIR}`, `${PHYSICSNEMO_ROOT}`, ... and home
directories to `~`, so nothing machine- or user-specific is published.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

from train_aero.folds import FOLDS
from train_aero.paths import Layout, layout

HISTORY_FIELDS = ["loss", "pressure_l2", "wss_l2"]
HOME = re.compile(r"/(?:home|Users)/[^/\s\"']+")


def sanitizer(lay: Layout):
    subs = [(str(p), f"${{{var}}}") for p, var in (
        (lay.physicsnemo_root, "PHYSICSNEMO_ROOT"), (lay.physicsnemo_cfd_root, "PHYSICSNEMO_CFD_ROOT"),
        (lay.workdir, "TRAIN_AERO_WORKDIR"), (lay.source_data, "TRAIN_AERO_SOURCE_DATA")) if p]
    subs.sort(key=lambda sv: -len(sv[0]))

    def clean(text: str) -> str:
        for s, v in subs:
            text = text.replace(s, v)
        return HOME.sub("~", text)

    return clean


def copy_text(src: Path, dst: Path, clean) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(clean(src.read_text()))


def history_csv(metrics: Path, dst: Path) -> None:
    """Per-epoch train / validation curves from the recipe's metrics.jsonl."""
    rows: dict[int, dict] = {}
    with metrics.open() as fh:
        for line in fh:
            rec = json.loads(line)
            phase = rec.get("phase")
            if phase in ("train_summary", "val_summary"):
                prefix = "train" if phase == "train_summary" else "val"
                row = rows.setdefault(rec["epoch"], {"epoch": rec["epoch"]})
                row.update({f"{prefix}_{k}": rec.get(k) for k in HISTORY_FIELDS})
    dst.parent.mkdir(parents=True, exist_ok=True)
    cols = ["epoch"] + [f"{p}_{k}" for p in ("train", "val") for k in HISTORY_FIELDS]
    with dst.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows[e] for e in sorted(rows))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export(lay: Layout, repo: Path, checkpoints: Path | None) -> None:
    clean = sanitizer(lay)
    out = repo / "results"
    for sub in ("benchmark", "figures", "baselines", "runs"):
        shutil.rmtree(out / sub, ignore_errors=True)

    results = lay.bench / "results"
    if (results / "BENCH_SUMMARY.md").exists():
        copy_text(results / "BENCH_SUMMARY.md", out / "summary.md", clean)
    for fold in FOLDS:
        for name in ("benchmark_results.json", "benchmark_results.csv"):
            if (results / fold / name).exists():
                copy_text(results / fold / name, out / "benchmark" / fold / name, clean)
        for png in sorted((results / fold / "visuals").glob("*.png")):
            (out / "figures" / fold).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(png, out / "figures" / fold / png.name)
    for f in sorted((lay.workdir / "results/baselines").glob("*.json")):
        copy_text(f, out / "baselines" / f.name, clean)

    manifest = []
    if checkpoints:
        checkpoints.mkdir(parents=True, exist_ok=True)
    for rj in sorted(lay.runs.rglob("run.json")):
        run = rj.parent
        rel = run.relative_to(lay.runs)
        dst = out / "runs" / rel
        copy_text(rj, dst / "run.json", clean)
        for src, name in ((run / "score.json", "score.json"),
                          (run / "train/resolved_config.yaml", "resolved_config.yaml"),
                          (run / "bench_infer_config.yaml", "bench_infer_config.yaml")):
            if src.exists():
                copy_text(src, dst / name, clean)
        if (run / "train/metrics.jsonl").exists():
            history_csv(run / "train/metrics.jsonl", dst / "history.csv")
        ckpt = sorted((run / "train/checkpoints").glob("*.mdlus"))
        if ckpt:
            asset = "-".join(rel.parts) + ".mdlus"          # <family>-<model>-<fold>-<run>.mdlus
            manifest.append({"asset": asset, "run": str(rel), "model_class": ckpt[-1].name.split(".")[0],
                             "bytes": ckpt[-1].stat().st_size, "sha256": sha256(ckpt[-1])})
            if checkpoints:
                shutil.copyfile(ckpt[-1], checkpoints / asset)
    (out / "checkpoints.json").write_text(json.dumps(manifest, indent=1) + "\n")

    leaks = [p for p in out.rglob("*") if p.suffix in {".json", ".csv", ".md", ".yaml"}
             and HOME.search(p.read_text())]
    if leaks:
        raise RuntimeError(f"absolute home paths left in: {leaks[:5]}")
    print(f"exported {len(manifest)} runs to {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", type=Path, required=True, help="repository root to export into")
    ap.add_argument("--checkpoints", type=Path, default=None, help="folder for release assets")
    args = ap.parse_args()
    export(layout(), args.repo.resolve(), args.checkpoints)


if __name__ == "__main__":
    main()
