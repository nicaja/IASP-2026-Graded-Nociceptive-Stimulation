"""Corrected time-frequency maps of total power (20-200 Hz, 0-400 ms, 10-ms bins).

Sequences are averaged within each animal, so every animal contributes one map per intensity.
For each region and contrast, the animal-level difference maps are tested with:

- TFCE (threshold-free cluster enhancement) with 4096 sign flips of whole animal maps,
  then Bonferroni correction across the nine region-by-contrast maps (primary);
- a maximum-|t| procedure that shuffles the three intensity labels within each animal and takes
  the largest |t| across all nine maps as one null value (sensitivity).
"""

from __future__ import annotations

import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from mne.stats import combine_adjacency, permutation_cluster_1samp_test

from . import config as cfg


def animal_average(blocks: np.ndarray, subjects, config: dict, keep_excluded: bool):
    subjects = np.asarray(subjects).astype(str)
    ids = np.asarray(sorted(np.unique(subjects), key=int))
    values = np.stack([blocks[subjects == subject].mean(0) for subject in ids])
    if not keep_excluded:
        regions = config["design"]["regions"]
        for subject, region in config["design"]["excluded"]:
            values[ids == subject.zfill(2), :, regions.index(region)] = np.nan
    return ids, values


def contrasts(maps: np.ndarray, config: dict) -> np.ndarray:
    """animals x condition x region x ... -> animals x contrast x region x ..."""
    conditions = config["design"]["conditions"]
    return np.stack([maps[:, conditions.index(high)] - maps[:, conditions.index(low)]
                     for _, high, low in config["design"]["contrasts"]], axis=1)


def t_statistic(data: np.ndarray, axis: int) -> np.ndarray:
    mean = np.nanmean(data, axis=axis)
    se = np.nanstd(data, axis=axis, ddof=1) / np.sqrt(np.maximum(np.sum(np.isfinite(data), axis=axis), 1))
    return np.divide(mean, se, out=np.zeros_like(mean, dtype=float), where=np.isfinite(se) & (se > 0))


def tfce(sample: np.ndarray, seed: int, config: dict):
    """TFCE one-sample test; returns mean effect, TFCE statistic and per-bin P within the map."""
    n_animals, n_frequencies, n_times = sample.shape
    flat = sample.reshape(n_animals, n_frequencies * n_times)
    statistic, clusters, cluster_p, _ = permutation_cluster_1samp_test(
        flat, threshold={"start": config["statistics"]["tfce_start"], "step": config["statistics"]["tfce_step"]},
        n_permutations=config["statistics"]["permutations"], tail=0,
        adjacency=combine_adjacency(n_frequencies, n_times), out_type="mask", seed=seed, n_jobs=1, verbose=False)
    p_map = np.ones(flat.shape[1])
    for cluster, p in zip(clusters, cluster_p):
        mask = np.asarray(cluster).reshape(-1).astype(bool)
        p_map[mask] = np.minimum(p_map[mask], float(p))
    return sample.mean(axis=0), statistic.reshape(n_frequencies, n_times), p_map.reshape(n_frequencies, n_times)


def global_maximum(maps: np.ndarray, config: dict):
    """Within-animal intensity-label shuffles; the null is the largest |t| over all nine maps."""
    observed = t_statistic(contrasts(maps, config), axis=0)
    labels = np.asarray(list(itertools.permutations(range(3))), dtype=np.int8)
    count = config["statistics"]["permutations"]
    rng = np.random.default_rng(config["statistics"]["seed"] + 1000)
    null = np.empty(count, dtype=np.float32)
    animals = np.arange(len(maps))[None, :, None]
    conditions = config["design"]["conditions"]
    for start in range(0, count, 8):
        stop = min(start + 8, count)
        permuted = maps[animals, labels[rng.integers(0, len(labels), size=(stop - start, len(maps)))]]
        shuffled = np.stack([permuted[:, :, conditions.index(high)] - permuted[:, :, conditions.index(low)]
                             for _, high, low in config["design"]["contrasts"]], axis=2)
        null[start:stop] = np.nanmax(np.abs(t_statistic(shuffled, axis=1)), axis=(1, 2, 3, 4))
    exceed = count - np.searchsorted(np.sort(null.astype(float)), np.abs(observed), side="left")
    return observed, (exceed + 1.0) / (count + 1.0), null


def _tfce_job(source: str, target: str, ci: int, ri: int, config: dict) -> str:
    if not Path(target).exists():
        with np.load(source) as data:
            sample = data["contrasts"][:, ci, ri]
        sample = sample[np.isfinite(sample).all(axis=(1, 2))]
        effect, statistic, p = tfce(sample, config["statistics"]["seed"] + ci * 10 + ri, config)
        family = len(config["design"]["regions"]) * len(config["design"]["contrasts"])
        np.savez_compressed(target, effect=effect, statistic=statistic, p_within=p,
                            p_global=np.minimum(p * family, 1), n_animals=len(sample))
    return target


def _maximum_job(folder: str, config: dict) -> str:
    target = Path(folder) / "maximum_maps.npz"
    if not target.exists():
        with np.load(Path(folder) / "animal_maps.npz") as data:
            observed, p, null = global_maximum(data["maps"], config)
        np.savez_compressed(target, statistic=observed, p_global=p, null_maximum=null)
    return str(target)


def correct_all(results: Path, config: dict, workers: int) -> None:
    """TFCE for every variant, region and contrast, plus the maximum-|t| family per variant.

    A region whose data do not change between variants (S1 and PFC when only animal 13 ACC is
    put back) is tested once and shared.
    """
    regions, contrast_names = config["design"]["regions"], [c[0] for c in config["design"]["contrasts"]]
    cache = results / "permutations"
    cache.mkdir(exist_ok=True)
    jobs, lookup = {}, {}
    for name, (weighting, keep_excluded) in cfg.variants(config).items():
        for ci, contrast in enumerate(contrast_names):
            for ri, region in enumerate(regions):
                differs = keep_excluded and any(region == r for _, r in config["design"]["excluded"])
                key = f"{weighting}{'_all' if differs else ''}_{region}_{contrast}"
                lookup[name, ci, ri] = cache / f"{key}.npz"
                jobs.setdefault(key, (str(results / name / "animal_maps.npz"), str(cache / f"{key}.npz"), ci, ri))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = [pool.submit(_tfce_job, *job, config) for job in jobs.values()]
        pending += [pool.submit(_maximum_job, str(results / name), config) for name in cfg.variants(config)]
        for done in as_completed(pending):
            print(f"permutations: {Path(done.result()).name}", flush=True)
    for name in cfg.variants(config):
        folder = results / name
        with np.load(folder / "maximum_maps.npz") as maximum:
            max_p = maximum["p_global"]
        arrays = {k: np.empty((3, 3, 30, 40)) for k in ("effect", "statistic", "p_within", "p_global")}
        rows = []
        for ci, contrast in enumerate(contrast_names):
            for ri, region in enumerate(regions):
                with np.load(lookup[name, ci, ri]) as result:
                    for key in arrays:
                        arrays[key][ci, ri] = result[key]
                    rows.append({"region": region, "contrast": contrast, "n_animals": int(result["n_animals"]),
                                 "tfce_p": float(result["p_global"].min()),
                                 "tfce_bins": int((result["p_global"] < 0.05).sum()),
                                 "maximum_p": float(max_p[ci, ri].min()),
                                 "maximum_bins": int((max_p[ci, ri] < 0.05).sum()),
                                 "mean_effect": float(result["effect"].mean())})
        np.savez_compressed(folder / "tfce_maps.npz", **arrays, mask=arrays["p_global"] < 0.05,
                            maximum_mask=max_p < 0.05)
        pd.DataFrame(rows).to_csv(folder / "map_tests.csv", index=False)
