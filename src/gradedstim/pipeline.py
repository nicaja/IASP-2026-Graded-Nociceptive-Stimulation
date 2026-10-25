"""Statistics stage: stack the per-recording features, fit models, correct maps, write tables."""

from __future__ import annotations

import json
import platform
from concurrent.futures import ProcessPoolExecutor, as_completed
from importlib.metadata import version

import numpy as np
import pandas as pd

from . import aperiodic, config as cfg, correlations, figures, maps, models, tables
from .features import WEIGHTINGS, entities, recordings


def stack_features(config: dict) -> dict[str, dict]:
    """Stack the cached recordings, one dictionary per channel weighting."""
    sources = recordings(config["paths"]["epochs"])
    cache = config["paths"]["work"] / "features"
    blocks = [np.load(cache / f"{p.stem}.npz") for p in sources]
    info = pd.DataFrame([entities(p) for p in sources])
    per_block = ("total", "evoked", "induced", "evoked_fraction", "traces", "spectrum",
                 "map_total", "fraction_map", "channel_counts")
    shared = ("scalar_frequencies", "map_frequencies", "map_times", "trace_times", "spectrum_frequencies")
    stacked = {}
    for w, weighting in enumerate(WEIGHTINGS):
        stacked[weighting] = {k: np.stack([b[k][w] for b in blocks]) for k in per_block}
        stacked[weighting].update({k: blocks[0][k] for k in shared})
        stacked[weighting].update(subjects=info.subject.to_numpy(str), tasks=info.task.to_numpy(str),
                                  runs=info.run.to_numpy(int),
                                  event_counts=np.stack([b["event_counts"] for b in blocks]))
    for b in blocks:
        b.close()
    return stacked


def run_order_z(subjects, tasks, runs) -> np.ndarray:
    """Within-animal recording order, standardised (localisation runs ordered after main runs)."""
    output = np.zeros(len(subjects))
    for subject in np.unique(subjects):
        idx = np.flatnonzero(subjects == subject)
        raw = np.array([int(r) + (100 if t == "depthloc" else 0) for t, r in zip(tasks[idx], runs[idx])], float)
        if raw.std() > 0:
            output[idx] = (raw - raw.mean()) / raw.std()
    return output


def scalar_table(features_: dict, config: dict) -> pd.DataFrame:
    """One row per recording x intensity x region with the four scalar outcomes."""
    order = run_order_z(features_["subjects"], features_["tasks"], features_["runs"])
    rows = []
    for b, subject in enumerate(features_["subjects"]):
        for ci, intensity in enumerate(config["design"]["conditions"]):
            for ri, region in enumerate(config["design"]["regions"]):
                rows.append({
                    "block_index": b,
                    "block_id": f"sub-{subject}_{features_['tasks'][b]}_run-{features_['runs'][b]}",
                    "subject": subject, "task": features_["tasks"][b], "run": int(features_["runs"][b]),
                    "run_order_z": order[b], "intensity": intensity, "region": region,
                    "n_events": int(features_["event_counts"][b, ci]),
                    "n_channels": int(features_["channel_counts"][b, ci, ri]),
                    **{k: float(features_[k][b, ci, ri]) for k in models.SCALAR},
                })
    return pd.DataFrame(rows)


def drop_excluded(table: pd.DataFrame, config: dict) -> pd.DataFrame:
    excluded = np.zeros(len(table), dtype=bool)
    for subject, region in config["design"]["excluded"]:
        excluded |= (table.subject.str.zfill(2) == subject.zfill(2)) & (table.region == region)
    return table.loc[~excluded].copy()


def statistics(config: dict, workers: int = 6) -> None:
    """Mixed models and corrected maps for the primary and the three sensitivity analyses."""
    results = config["paths"]["results"]
    stacked = stack_features(config)
    for weighting, features_ in stacked.items():
        scalar = scalar_table(features_, config)
        spectral = aperiodic.fit_table(features_, scalar, config)
        for name, (variant_weighting, keep_excluded) in cfg.variants(config).items():
            if variant_weighting != weighting:
                continue
            folder = results / name
            folder.mkdir(parents=True, exist_ok=True)
            part = (lambda t: t) if keep_excluded else (lambda t: drop_excluded(t, config))
            part(scalar).to_csv(folder / "scalar_features.csv", index=False)
            part(spectral).to_csv(folder / "aperiodic_features.csv", index=False)
            ids, animal = maps.animal_average(features_["map_total"].astype(np.float32), features_["subjects"],
                                              config, keep_excluded)
            np.savez_compressed(folder / "animal_maps.npz", subjects=ids, maps=animal,
                                contrasts=maps.contrasts(animal, config),
                                frequencies=features_["map_frequencies"], times=features_["map_times"])
            if name == "primary":
                figures.write_figure_data(features_, part(spectral), folder, config)
    jobs = [(str(results / name), outcome) for name in cfg.variants(config) for outcome in models.OUTCOMES]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for done in as_completed([pool.submit(models.fit_outcome_job, job, config) for job in jobs]):
            print(f"model: {done.result()}", flush=True)
    for name in cfg.variants(config):
        folder = results / name
        pd.concat([pd.read_csv(folder / f"contrasts_{o}.csv", float_precision="round_trip")
                   for o in models.OUTCOMES]).to_csv(folder / "contrasts.csv", index=False)
        for o in models.OUTCOMES:
            (folder / f"contrasts_{o}.csv").unlink()
    maps.correct_all(results, config, workers)
    correlations.write(results / "primary", config)
    tables.write_all(results, config)
    (results / "software_versions.json").write_text(json.dumps({
        "python": platform.python_version(),
        **{p: version(p) for p in ("mne", "numpy", "scipy", "pandas", "statsmodels", "fooof", "matplotlib")},
    }, indent=2) + "\n", encoding="utf-8")
