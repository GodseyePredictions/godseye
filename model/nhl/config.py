"""Loads nhl/config.yaml, the one place NHL thresholds live. Tests may pass their own copy."""
import copy
from pathlib import Path

import yaml

HERE = Path(__file__).parent


def load(path: Path | None = None) -> dict:
    return yaml.safe_load((path or HERE / "config.yaml").read_text())


CONFIG = load()


def copy_config() -> dict:
    return copy.deepcopy(CONFIG)
