"""Exploratory: do animals with larger changes in one measure also change more in another?

For each measure and region, the high-minus-low difference is taken within each sequence and
averaged within animal. Spearman correlations across the animals with data in all three regions
are computed separately for 10x vs 2x MT and 20x vs 2x MT (Supplementary Figure S7).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

MEASURES = (("total", "Total"), ("evoked", "Evoked"), ("induced", "Induced"),
            ("evoked_fraction", "Evoked fraction"), ("aperiodic_exponent", "Exponent"),
            ("aperiodic_offset", "Offset"), ("adjusted_power", "Adjusted power"))


def animal_differences(scalar: pd.DataFrame, aperiodic: pd.DataFrame, config: dict) -> pd.DataFrame:
    records = []
    for measure, _ in MEASURES:
        source = aperiodic.loc[aperiodic.fit_ok] if measure in aperiodic else scalar
        wide = source.pivot(index=["subject", "block_id", "region"], columns="intensity", values=measure)
        for contrast, high, low in config["design"]["contrasts"]:
            difference = (wide[high] - wide[low]).dropna()
            result = difference.groupby(level=["subject", "region"]).mean().rename("difference").reset_index()
            records.append(result.assign(measure=measure, contrast=contrast))
    return pd.concat(records, ignore_index=True)


def write(folder: Path, config: dict) -> None:
    scalar = pd.read_csv(folder / "scalar_features.csv", dtype={"subject": str}, float_precision="round_trip")
    aperiodic = pd.read_csv(folder / "aperiodic_features.csv", dtype={"subject": str}, float_precision="round_trip")
    differences = animal_differences(scalar, aperiodic, config)
    columns = pd.MultiIndex.from_product([config["design"]["regions"], [m for m, _ in MEASURES]])
    frames = [differences.loc[differences.contrast == contrast].pivot(
        index="subject", columns=["region", "measure"], values="difference").reindex(columns=columns)
        for contrast, _, _ in config["design"]["contrasts"][:2]]
    complete = frames[0].dropna().index.intersection(frames[1].dropna().index).sort_values()
    values = np.stack([frame.loc[complete].to_numpy() for frame in frames], axis=1)
    matrices = np.stack([np.corrcoef(rankdata(values[:, c, :], axis=0), rowvar=False) for c in range(2)])
    names = dict(MEASURES)
    labels = [f"{region} {names[measure]}" for region, measure in columns]
    np.savez_compressed(folder / "correlations.npz", spearman=matrices, labels=np.asarray(labels),
                        subjects=np.asarray(complete, dtype=str), animal_differences=values,
                        contrasts=np.asarray([c[0] for c in config["design"]["contrasts"][:2]]))
