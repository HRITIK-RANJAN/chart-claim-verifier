"""Load configs/default.yaml and merge an experiment config on top."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "configs" / "default.yaml"


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(exp_path: str | Path | None = None, **overrides: Any) -> dict:
    cfg = yaml.safe_load(DEFAULT.read_text())
    if exp_path:
        cfg = _merge(cfg, yaml.safe_load(Path(exp_path).read_text()) or {})
    if overrides:
        cfg = _merge(cfg, overrides)
    return cfg
