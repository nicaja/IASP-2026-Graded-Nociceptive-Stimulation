"""Per-recording features: Morlet power split into evoked and induced parts, waveforms and spectra.

Each recording ("sequence") holds all three intensities. For every intensity and region this
module computes, from the cleaned epochs:

- total power: mean single-trial Morlet power (phase-locked and non-phase-locked activity);
- evoked power: power of the trial-averaged waveform (phase-locked activity only);
- induced power: total minus evoked, in linear power;
- the scalar endpoints (mean log10 power over 35-120 Hz and 0-400 ms), the evoked fraction,
  time-frequency maps in 10-ms bins, the averaged waveform and a static multitaper spectrum.

Two channel weightings are kept side by side (index 0 and 1 of every array):
0 "original": each physical contact contributes its own clean epochs once (primary analysis);
1 "copies": the 32 stored channels are averaged as stored, so repaired copies of a neighbouring
contact count again (sensitivity analysis).
"""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import re  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from pathlib import Path  # noqa: E402

import mne  # noqa: E402
import numpy as np  # noqa: E402
from mne.time_frequency import psd_array_multitaper, tfr_array_morlet  # noqa: E402

from . import config as cfg  # noqa: E402

WEIGHTINGS = ("original", "copies")
TINY = np.finfo(float).tiny


def entities(path: str | Path) -> dict:
    match = re.search(r"sub-(\d+)_task-([^_]+)_acq-[^_]+_run-(\d+)_", Path(path).name)
    if not match:
        raise ValueError(f"Not a BIDS recording name: {path}")
    return {"subject": match.group(1), "task": match.group(2), "run": int(match.group(3))}


def recordings(root: Path) -> list[Path]:
    return sorted(Path(root).glob("sub-*/ieeg/*_ieeg.fif"))


def load_epochs(path: Path, regions) -> tuple[mne.Epochs, np.ndarray]:
    """Read cleaned epochs and, for every epoch and channel, the contact its samples came from.

    The QC sidecar (.qc.npz) stores a donor index per epoch and channel: a channel's own index
    means its own clean signal; another index means the epoch was repaired with a copy of that
    neighbouring contact in the same region.
    """
    epochs = mne.read_epochs(path, preload=True, verbose="ERROR")
    with np.load(Path(path).with_suffix(".qc.npz"), allow_pickle=False) as qc:
        names = qc["channel_names"].tolist()
        keep = qc["retained_epoch_mask"]
        donors = qc["donor_channel_indices"][keep]
        if names != epochs.ch_names or not np.array_equal(qc["original_selection"][keep], epochs.selection):
            raise ValueError(f"QC sidecar does not match the epochs: {path}")
    for region in regions:
        own = np.array([i for i, name in enumerate(names) if name.startswith(region)])
        if len(own) != 32 or not np.isin(donors[:, own], own).all():
            raise ValueError(f"Expected 32 {region} channels repaired only within {region}: {path}")
    data = epochs.get_data(copy=False)
    if not np.array_equal(data, data[np.arange(len(data))[:, None], donors]):
        raise ValueError(f"Stored samples disagree with the donor record: {path}")
    return epochs, donors


def bin_time_axis(values: np.ndarray, times: np.ndarray, start: float, stop: float, width: float):
    """Average the last axis into fixed, non-overlapping bins (the last bin includes `stop`)."""
    n_bins = int(round((stop - start) / width))
    edges = start + np.arange(n_bins + 1, dtype=float) * width
    output = np.full((*values.shape[:-1], n_bins), np.nan)
    for index in range(n_bins):
        upper = times <= edges[index + 1] if index == n_bins - 1 else times < edges[index + 1]
        output[..., index] = np.nanmean(values[..., (times >= edges[index]) & upper], axis=-1)
    return output, (edges[:-1] + edges[1:]) / 2


def channel_power(data_uv, valid, multiplicity, times, sfreq, frequencies, cycles, config):
    """Linear total, evoked and spectral power for one region and intensity, both weightings.

    data_uv: epochs x 32 channels x samples (microvolts). valid: True where a channel holds its
    own signal. multiplicity: how many stored channels carry this channel's signal in an epoch.
    Each original contact is transformed once; the copies weighting reuses it with multiplicity.
    """
    n_events, n_channels, n_times = data_uv.shape
    counts = valid.sum(0)
    available = counts > 0
    if not available.any():
        raise ValueError("No clean channel in this region")
    batch = config["power"]["epochs_per_batch"]
    window = config["spectrum"]["window"]
    in_window = (times >= window[0]) & (times <= window[1])
    total = np.zeros((2, len(frequencies), n_times))
    spectrum = None
    channel_means = []
    for channel in np.flatnonzero(available):
        events = np.flatnonzero(valid[:, channel])
        channel_means.append(data_uv[events, channel].mean(0))
        for start in range(0, len(events), batch):
            ids = events[start:start + batch]
            x = data_uv[ids, channel:channel + 1]
            z = tfr_array_morlet(x, sfreq, frequencies, n_cycles=cycles, zero_mean=True,
                                 output="complex", n_jobs=1, verbose="ERROR")
            power = np.abs(z[:, 0]) ** 2
            total[0] += power.sum(0) / counts[channel] / available.sum()
            total[1] += np.einsum("e,eft->ft", multiplicity[ids, channel], power) / n_events / n_channels
            psd, psd_frequencies = psd_array_multitaper(
                x[:, :, in_window], sfreq, fmin=config["spectrum"]["fit_range"][0],
                fmax=config["spectrum"]["fit_range"][1], bandwidth=config["spectrum"]["bandwidth"],
                adaptive=False, low_bias=True, normalization="full", n_jobs=1, verbose="ERROR")
            psd = psd[:, 0]
            if spectrum is None:
                spectrum = np.zeros((2, len(psd_frequencies)))
            spectrum[0] += psd.sum(0) / counts[channel] / available.sum()
            spectrum[1] += np.einsum("e,ef->f", multiplicity[ids, channel], psd) / n_events / n_channels
    # Waveforms: per-contact average (original) or the plain average of the stored channels (copies).
    waveforms = (np.stack(channel_means), data_uv.mean(0))
    evoked = np.stack([tfr_array_morlet(w[None], sfreq, frequencies, n_cycles=cycles, zero_mean=True,
                                        output="avg_power", n_jobs=1, verbose="ERROR").mean(0)
                       for w in waveforms])
    traces = np.stack([w.mean(0) for w in waveforms])
    return total, evoked, traces, spectrum, psd_frequencies


def summarize(total, evoked, times, frequencies, scalar_indices, config):
    """Scalar endpoints and binned maps from linear total and evoked power."""
    evoked = np.minimum(evoked, total)
    induced = np.maximum(total - evoked, 0.0)
    scalar_frequencies = frequencies[scalar_indices]
    notch = np.zeros(len(scalar_frequencies), dtype=bool)
    for low, high in config["power"]["notches"]:
        notch |= (scalar_frequencies >= low) & (scalar_frequencies <= high)
    band = config["power"]["band"]
    in_band = (scalar_frequencies >= band[0]) & (scalar_frequencies <= band[1]) & ~notch
    start, stop = config["power"]["window"]
    in_time = (times >= start) & (times <= stop)
    width = config["power"]["map_bin_width"]
    out = {}
    for name, values in (("total", total), ("evoked", evoked), ("induced", induced)):
        log_power = np.log10(values + TINY)
        out[name] = np.mean(log_power[:, scalar_indices][:, in_band][:, :, in_time], axis=(1, 2))
        if name == "total":
            out["map_total"], map_times = bin_time_axis(log_power, times, start, stop, width)
    fraction = np.clip(np.divide(evoked, total, out=np.zeros_like(total), where=total > 0), 0, 1)
    out["fraction_map"], _ = bin_time_axis(fraction, times, start, stop, width)
    out["evoked_fraction"] = (evoked[:, scalar_indices][:, in_band][:, :, in_time].mean((1, 2))
                              / total[:, scalar_indices][:, in_band][:, :, in_time].mean((1, 2)))
    return out, map_times


def recording_features(path: Path, config: dict) -> dict[str, np.ndarray]:
    """All features of one recording; arrays are weighting x intensity x region x ..."""
    conditions, regions = config["design"]["conditions"], config["design"]["regions"]
    epochs, donors = load_epochs(path, regions)
    epochs.crop(tmax=config["epochs"]["analysis_window"][1])
    data = epochs.get_data(copy=False)
    frequencies, scalar_indices, map_indices = cfg.frequency_grid(config)
    cycles = cfg.cycles(frequencies)
    times, sfreq = epochs.times, epochs.info["sfreq"]
    # Every tested time point must have its complete wavelet inside the epoch.
    support = np.max(5 * cycles / (2 * np.pi * frequencies))
    step = np.median(np.diff(times))
    if (config["power"]["window"][0] - support < times[0] - step
            or config["power"]["window"][1] + support > times[-1] + step):
        raise ValueError("Analysis window is inside the wavelet edge region")
    trace_window = config["epochs"]["trace_window"]
    in_trace = (times >= trace_window[0]) & (times <= trace_window[1])
    arrays: dict[str, np.ndarray] = {}
    channel_counts = np.zeros((2, 3, 3), dtype=int)
    for ci, condition in enumerate(conditions):
        chosen = epochs.events[:, 2] == epochs.event_id[condition]
        for ri, region in enumerate(regions):
            own = np.array([i for i, name in enumerate(epochs.ch_names) if name.startswith(region)])
            regional = data[chosen][:, own] * 1e6
            sources = donors[chosen][:, own]
            valid = sources == own
            multiplicity = np.stack([(sources == c).sum(1) for c in own], axis=1)
            total, evoked, traces, spectrum, psd_frequencies = channel_power(
                regional, valid, multiplicity, times, sfreq, frequencies, cycles, config)
            summary, map_times = summarize(total, evoked, times, frequencies, scalar_indices, config)
            values = {
                **{k: summary[k] for k in ("total", "evoked", "induced", "evoked_fraction")},
                "traces": traces[:, in_trace], "spectrum": spectrum,
                "map_total": summary["map_total"][:, map_indices],
                "fraction_map": summary["fraction_map"][:, scalar_indices],
            }
            for name, value in values.items():
                arrays.setdefault(name, np.empty((2, 3, 3, *value.shape[1:])))[:, ci, ri] = value
            channel_counts[:, ci, ri] = (int(valid.any(0).sum()), 32)
    arrays.update(
        channel_counts=channel_counts,
        event_counts=np.array([int((epochs.events[:, 2] == epochs.event_id[c]).sum()) for c in conditions]),
        scalar_frequencies=frequencies[scalar_indices], map_frequencies=frequencies[map_indices],
        map_times=map_times, trace_times=times[in_trace], spectrum_frequencies=psd_frequencies,
    )
    return arrays


def _extract(path: str, target: str, config_path: str) -> str:
    if not Path(target).exists():
        np.savez_compressed(target, **recording_features(Path(path), cfg.load(config_path)))
    return target


def extract_all(config: dict, config_path: Path, workers: int = 6) -> None:
    """Compute and cache the features of every recording (the slow step, about 40 min on 6 cores)."""
    sources = recordings(config["paths"]["epochs"])
    if not sources:
        raise FileNotFoundError(f"No recordings below {config['paths']['epochs']}")
    cache = config["paths"]["work"] / "features"
    cache.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(_extract, str(p), str(cache / f"{p.stem}.npz"), str(config_path)) for p in sources]
        for done, job in enumerate(as_completed(jobs), 1):
            print(f"features {done}/{len(jobs)}: {Path(job.result()).name} ({time.time() - started:.0f} s)", flush=True)
