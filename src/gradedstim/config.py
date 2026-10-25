"""Read config.toml and derive the frequency grids used throughout."""

from __future__ import annotations

import tomllib
from pathlib import Path

import numpy as np


def load(path: str | Path = "config.toml") -> dict:
    path = Path(path)
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    for key, value in config["paths"].items():
        config["paths"][key] = (path.parent / value).resolve()
    return config


def log_frequencies(spec) -> np.ndarray:
    low, high, count = spec
    return np.geomspace(float(low), float(high), int(count))


def cycles(frequencies: np.ndarray) -> np.ndarray:
    """Morlet cycles: frequency / 4, kept between 5 and 10."""
    return np.clip(frequencies / 4, 5, 10)


def frequency_grid(config: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One combined grid; returns it with the indices of the scalar and map frequencies."""
    scalar = log_frequencies(config["power"]["scalar_frequencies"])
    maps = log_frequencies(config["power"]["map_frequencies"])
    combined = np.unique(np.r_[scalar, maps])
    return combined, np.searchsorted(combined, scalar), np.searchsorted(combined, maps)


def variants(config: dict) -> dict[str, tuple[str, bool]]:
    """Primary analysis and the three sensitivity analyses reported in the supplement.

    weighting "original": each physical contact counts once (primary).
    weighting "copies": repaired copies of neighbouring contacts are averaged as stored.
    The flag says whether the excluded recordings (animal 13 ACC) are put back.
    """
    return {
        "primary": ("original", False),
        "with_copies": ("copies", False),
        "with_animal13_acc": ("original", True),
        "with_copies_and_animal13_acc": ("copies", True),
    }
