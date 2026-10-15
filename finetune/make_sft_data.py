"""Build the chart -> JSON-table fine-tuning set (implementation.md §10).

Charts come from separate generator seeds ("ft-*"), and the held-out plotting
style is never used, so the LoRA model cannot simply learn the test styles.

    python finetune/make_sft_data.py --n 6000 --out data/finetune
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from reportlens.generator.plot import render, sample_style
from reportlens.generator.tables import make_table
from reportlens.tools.vlm_table import PROMPT


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--out", default="data/finetune")
    ap.add_argument("--val", type=float, default=0.05)
    args = ap.parse_args()
    out = Path(args.out)
    (out / "img").mkdir(parents=True, exist_ok=True)
    files = {"train": (out / "train.jsonl").open("w"), "val": (out / "val.jsonl").open("w")}
    for i in range(args.n):
        rng = random.Random(f"ft-{i}")
        t = make_table(rng, f"ft{i}")
        img = out / "img" / f"ft{i}.png"
        render(t, sample_style(rng, held_out=False), img)
        target = {s: dict(zip(t.x_values, vals)) for s, vals in t.series.items()}
        row = {"image": str(img), "messages": [
            {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]},
            {"role": "assistant", "content": [{"type": "text", "text": json.dumps(target)}]}]}
        files["val" if rng.random() < args.val else "train"].write(json.dumps(row) + "\n")
    for f in files.values():
        f.close()
    print(f"wrote {args.n} examples to {out}")


if __name__ == "__main__":
    main()
