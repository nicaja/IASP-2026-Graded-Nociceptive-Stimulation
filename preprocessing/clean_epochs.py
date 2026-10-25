"""Step 2: combine the two acquisitions, apply the recorded QC decisions and repair bad channel-epochs.

1. The acq-sp and acq-acc epochs of a sequence are joined into one 96-channel file
   (S1, PFC and ACC, 32 channels each).
2. The recorded bad channels in qc_decisions.json are applied (found by an automated detector
   and confirmed by visual review).
3. Fixed technical rules screen every channel in every epoch: non-finite values, flat lines,
   plateaus of 20 ms or longer, excursions above 100 mV, and abrupt sustained steps.
4. Each unusable channel-epoch is filled with a copy of a usable contact from the same region and
   epoch (ranked by line-noise and gradient quality, then nearness on the array). The source of
   every sample is stored in a sidecar (.qc.npz), so the analysis can count each physical contact
   once. An epoch is dropped only if a whole region has no usable contact.

    python preprocessing/clean_epochs.py --epochs <output of step 1> --out <cleaned epochs folder>
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import mne
import numpy as np


def channel_epoch_mask(data: np.ndarray, sfreq: float) -> np.ndarray:
    """True where a channel-epoch passes the technical rules (data in volts)."""
    usable = np.isfinite(data).all(axis=-1)
    window = max(3, int(np.ceil(sfreq * 0.020)))
    for epoch, channel in np.ndindex(usable.shape):
        if not usable[epoch, channel]:
            continue
        trace = data[epoch, channel]
        if np.ptp(trace) <= 1e-12 or np.max(np.abs(trace)) > 0.1:
            usable[epoch, channel] = False
            continue
        difference = np.diff(trace)
        edges = np.diff(np.r_[False, np.abs(difference) <= 1e-12, False].astype(int))
        lengths = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
        if lengths.size and lengths.max() >= window:
            usable[epoch, channel] = False
            continue
        # A step: a >50 uV jump far above typical sample-to-sample change, with a >100 uV level shift.
        threshold = max(50e-6, 30 * float(np.median(np.abs(difference))))
        for index in np.flatnonzero(np.abs(difference) > threshold):
            boundary = index + 1
            if boundary < window or boundary + window > len(trace):
                continue
            if abs(float(np.median(trace[boundary:boundary + window]) - np.median(trace[boundary - window:boundary]))) > 100e-6:
                usable[epoch, channel] = False
                break
    return usable


def donor_quality(data: np.ndarray, sfreq: float):
    """Ranking evidence for donors (lower is better): gradient size and mains-dominated windows."""
    clean = np.where(np.isfinite(data), data, 0)
    gradient = np.median(np.abs(np.diff(clean, axis=-1)), axis=-1)
    size = max(8, int(round(sfreq * 0.5)))
    count = data.shape[-1] // size
    line = np.zeros(data.shape[:2])
    persistent = np.zeros(data.shape[:2], dtype=bool)
    if count:
        windows = clean[..., :count * size].reshape(*data.shape[:2], count, size)
        centered = windows - windows.mean(axis=-1, keepdims=True)
        power = np.abs(np.fft.rfft(centered * np.hanning(size), axis=-1)) ** 2
        frequencies = np.fft.rfftfreq(size, 1 / sfreq)
        broad = (frequencies >= 5) & (frequencies <= min(200, sfreq / 2))
        mains = ((np.abs(frequencies - 50) <= 2) | (np.abs(frequencies - 60) <= 2)) & broad
        fractions = power[..., mains].sum(axis=-1) / np.maximum(power[..., broad].sum(axis=-1), np.finfo(float).tiny)
        line = np.median(fractions, axis=-1)
        rms = np.sqrt(np.mean(centered ** 2, axis=-1))
        if count >= 2:
            persistent = np.mean((fractions > 0.8) & (rms > 20e-6), axis=-1) >= 0.8
    return gradient, line, persistent


def copy_bad_channel_epochs(data, usable, regions, sfreq):
    """Fill unusable channel-epochs from usable contacts of the same region and epoch."""
    repaired = np.array(data, copy=True)
    usable = np.array(usable, copy=True)
    scores = np.zeros(usable.shape)
    gradient, line, persistent = donor_quality(data, sfreq)
    usable &= ~persistent
    for region in regions:
        for epoch in range(len(data)):
            good = region[usable[epoch, region]]
            if len(good):
                reference = max(float(np.median(gradient[epoch, good])), 1e-12)
                scores[epoch, region] = 10 * line[epoch, region] + np.maximum(
                    0, np.log2(np.maximum(gradient[epoch, region], 1e-12) / reference))
    donors = np.broadcast_to(np.arange(data.shape[1]), usable.shape).copy()
    donors[~usable] = -1
    for region in regions:
        for epoch in range(len(data)):
            good_positions = np.flatnonzero(usable[epoch, region])
            if not len(good_positions):
                continue
            for position in np.flatnonzero(~usable[epoch, region]):
                nearest = min(good_positions, key=lambda p: (scores[epoch, region[p]], abs(p - position), p))
                repaired[epoch, region[position]] = data[epoch, region[nearest]]
                donors[epoch, region[position]] = region[nearest]
    return repaired, donors >= 0, donors


def natural(name: str):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def clean(sp: mne.Epochs, acc: mne.Epochs, bad_channels: list[str]):
    if len(sp) != len(acc) or not np.array_equal(sp.selection, acc.selection) \
            or not np.array_equal(sp.events[:, 2], acc.events[:, 2]):
        raise ValueError("The two acquisitions do not hold the same stimuli")
    epochs = sp.copy().add_channels([acc])
    bad = set(bad_channels)
    data = epochs.get_data(copy=True)
    regions = [np.array(sorted([i for i, ch in enumerate(epochs.ch_names) if ch.startswith(name)],
                               key=lambda i: natural(epochs.ch_names[i]))) for name in ("PFC", "S1", "ACC")]
    if any(len(r) != 32 for r in regions) or len(epochs.ch_names) != 96:
        raise ValueError("Expected 32 channels in each of S1, PFC and ACC")
    usable = channel_epoch_mask(data, epochs.info["sfreq"])
    usable[:, [i for i, ch in enumerate(epochs.ch_names) if ch in bad]] = False
    repaired, valid, donors = copy_bad_channel_epochs(data, usable, regions, epochs.info["sfreq"])
    complete = valid.all(axis=1)
    original_selection = epochs.selection.copy()
    epochs._data = repaired
    epochs = epochs[np.flatnonzero(complete)]
    epochs.info["bads"] = []
    sidecar = {"donor_channel_indices": donors, "retained_epoch_mask": complete,
               "original_selection": original_selection, "channel_names": np.asarray(epochs.ch_names)}
    return epochs, sidecar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--epochs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    decisions = json.loads((Path(__file__).with_name("qc_decisions.json")).read_text(encoding="utf-8"))
    for recording, bad_channels in decisions.items():
        subject, task, run = recording.split("_")
        target = args.out / subject / "ieeg" / f"{subject}_{task}_acq-spacc_{run}_proc-combined_ieeg.fif"
        if target.exists():
            continue
        sp, acc = (mne.read_epochs(args.epochs / subject / "ieeg" / f"{subject}_{task}_acq-{acq}_{run}_epo.fif",
                                   preload=True, verbose="error") for acq in ("sp", "acc"))
        epochs, sidecar = clean(sp, acc, bad_channels)
        target.parent.mkdir(parents=True, exist_ok=True)
        epochs.save(target, fmt="single", verbose="error")
        np.savez_compressed(target.with_suffix(".qc.npz"), **sidecar)
        print(f"{target.name}: {len(epochs)} epochs", flush=True)


if __name__ == "__main__":
    main()
