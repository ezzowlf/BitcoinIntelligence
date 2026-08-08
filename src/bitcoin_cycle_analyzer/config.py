from __future__ import annotations

from pathlib import Path
import yaml


def load_config(path: str | Path = "config.yaml") -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    weights = config["score_weights"]
    if sum(weights.values()) != 100:
        raise ValueError("score_weights must sum to 100")
    return config

