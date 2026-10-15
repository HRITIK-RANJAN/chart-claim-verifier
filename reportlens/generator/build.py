"""Build the dataset splits (implementation.md §9.2).

Every report draws fresh tables from its own seed, so no table is shared
between splits. Split membership is written to data/splits/<split>.txt.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .report_builder import build_report

SPLITS = ["calib", "dev", "test", "style_shift"]


def load_truth(report_dir: str | Path) -> dict:
    return json.loads((Path(report_dir) / "truth.json").read_text())


def build_split(split: str, n: int, root: Path, gen_cfg: dict, seed: int = 0) -> list[str]:
    ids = []
    for i in range(n):
        rid = f"{split}_{i:03d}"
        rng = random.Random(f"{seed}-{split}-{i}")
        inject = rng.random() < gen_cfg.get("injection_rate", 0.0)
        build_report(rid, rng, root / split / rid, gen_cfg, held_out=(split == "style_shift"), inject=inject)
        if inject and gen_cfg.get("clean_twins"):          # E8: same report without the hidden text
            twin_rng = random.Random(f"{seed}-{split}-{i}")
            twin_rng.random()
            build_report(rid, twin_rng, root / f"{split}_clean" / rid, gen_cfg,
                         held_out=(split == "style_shift"), inject=False)
        ids.append(rid)
    return ids


def build_all(cfg: dict, root: str | Path, splits_dir: str | Path = "data/splits") -> dict[str, list[str]]:
    root, splits_dir = Path(root), Path(splits_dir)
    splits_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for split, n in cfg["generator"]["reports"].items():
        if n:
            out[split] = build_split(split, n, root, cfg["generator"], cfg["seed"])
            (splits_dir / f"{split}.txt").write_text("\n".join(out[split]) + "\n")
    return out


def report_dirs(root: str | Path, split: str) -> list[Path]:
    return sorted(p for p in (Path(root) / split).iterdir() if (p / "truth.json").exists())
