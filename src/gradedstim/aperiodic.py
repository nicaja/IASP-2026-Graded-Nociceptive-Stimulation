"""Exploratory aperiodic analysis: fit the 1/f-like background of each static spectrum.

For every recording, intensity and region, the 0-550 ms multitaper spectrum is fitted from
20 to 120 Hz with FOOOF (fixed aperiodic mode). The outcomes are the aperiodic exponent (slope),
the offset (vertical level) and the mean 35-120 Hz power above the fitted background
("adjusted power"). Mains-notch bins are interpolated before fitting and left out of the mean.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

TINY = np.finfo(float).tiny


def interpolate_notches(frequencies: np.ndarray, power: np.ndarray, notches) -> np.ndarray:
    """Replace notch-filtered bins by straight lines in log power between their neighbours."""
    log_power = np.log10(np.maximum(power, TINY))
    output = log_power.copy()
    for low, high in notches:
        inside = (frequencies >= low) & (frequencies <= high)
        left, right = np.flatnonzero(frequencies < low), np.flatnonzero(frequencies > high)
        if inside.any() and len(left) and len(right):
            output[inside] = np.interp(frequencies[inside], frequencies[[left[-1], right[0]]],
                                       output[[left[-1], right[0]]])
    return 10.0 ** output


def fit_one(frequencies, power, config) -> dict:
    from fooof import FOOOF

    spectrum = config["spectrum"]
    notches = config["power"]["notches"]
    repaired = interpolate_notches(frequencies, power, notches)
    model = FOOOF(peak_width_limits=tuple(spectrum["peak_width_limits"]), max_n_peaks=spectrum["max_n_peaks"],
                  min_peak_height=spectrum["min_peak_height"], peak_threshold=spectrum["peak_threshold"],
                  aperiodic_mode="fixed", verbose=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            model.fit(frequencies, repaired, spectrum["fit_range"])
            offset, exponent = map(float, model.aperiodic_params_)
            r_squared, error = float(model.r_squared_), float(model.error_)
            above = np.log10(np.maximum(repaired, TINY)) - (offset - exponent * np.log10(frequencies))
            band = config["power"]["band"]
            keep = (frequencies >= band[0]) & (frequencies <= band[1])
            for low, high in notches:
                keep &= ~((frequencies >= low) & (frequencies <= high))
            adjusted = float(np.mean(above[keep]))
        except Exception:
            offset = exponent = r_squared = error = adjusted = np.nan
    return {"aperiodic_offset": offset, "aperiodic_exponent": exponent, "adjusted_power": adjusted,
            "fit_r_squared": r_squared, "fit_error": error,
            "fit_ok": bool(np.isfinite(r_squared) and r_squared >= spectrum["min_r_squared"])}


def fit_table(features: dict, scalar: pd.DataFrame, config: dict) -> pd.DataFrame:
    """One fit per row of the scalar table (same row order: recording, intensity, region)."""
    frequencies = features["spectrum_frequencies"].astype(float)
    spectra = features["spectrum"].reshape(-1, len(frequencies))
    keys = ["block_index", "block_id", "subject", "task", "run_order_z", "intensity", "region"]
    rows = [{**row, **fit_one(frequencies, spectra[i].astype(float), config)}
            for i, row in enumerate(scalar[keys].to_dict("records"))]
    return pd.DataFrame(rows)
