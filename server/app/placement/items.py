"""Placement content: content/placement/{grammar,vocab}.json and calibration/*.json."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import CONTENT_DIR

PLACEMENT_DIR = CONTENT_DIR / "placement"


@lru_cache(maxsize=None)
def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def grammar_items(root: Path = PLACEMENT_DIR) -> list[dict[str, Any]]:
    """[{id, codes, ko, en}]"""
    return _load(root / "grammar.json")["items"]


def vocab_items(root: Path = PLACEMENT_DIR) -> list[dict[str, Any]]:
    """[{id, word, real, lemma?, pos?, rank?, band?, quantile?}]"""
    return _load(root / "vocab.json")["items"]


def calibration_paths(root: Path = PLACEMENT_DIR) -> list[Path]:
    return sorted((root / "calibration").glob("*.json"))


def calibration_ids(root: Path = PLACEMENT_DIR) -> list[str]:
    return [_load(p)["id"] for p in calibration_paths(root)]
