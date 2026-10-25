"""Step 1: filter and epoch the raw BIDS recordings.

Each sequence was acquired as two files: acq-sp (S1 and PFC surface arrays, 64 channels) and
acq-acc (ACC depth array, 32 channels). For every file listed in qc_decisions.json this script
notch-filters at 50, 100 and 150 Hz, band-passes 0.5-200 Hz (FIR), and cuts epochs from -0.2 to
1.0 s around each stimulus, decimated to about 2000 Hz, linearly detrended and mean-corrected
over -0.2 to -0.05 s.

    python preprocessing/make_epochs.py --bids <BIDS root> --out <folder for the epochs>
"""

from __future__ import annotations

import argparse
import json
from math import ceil, floor
from pathlib import Path

import mne

TARGET_RATE = 2000
TMIN, TMAX = -0.2, 1.0
EVENT_IDS = {"2x MT": 2, "10x MT": 10, "20x MT": 20}


def epoch_grid(rate: float):
    """Integer decimation factor and a zero-aligned sample grid inside [TMIN, TMAX]."""
    decim = max(1, int(round(rate / TARGET_RATE)))
    actual = rate / decim
    first, last = ceil(TMIN * actual - 1e-9), floor(TMAX * actual + 1e-9)
    return decim, first / actual, last / actual, last - first + 1


def make_epochs(raw_path: Path, n_jobs=1) -> mne.Epochs:
    raw = mne.io.read_raw_fif(raw_path, preload=True, verbose="error")
    events = mne.read_events(raw_path.with_name(raw_path.name.replace("_ieeg.fif", "_events.fif")))
    decim, tmin, tmax, samples = epoch_grid(raw.info["sfreq"])
    raw.notch_filter([50, 100, 150], filter_length="auto", notch_widths=1, method="fir", n_jobs=n_jobs,
                     verbose="error")
    raw.filter(0.5, 200, l_trans_bandwidth="auto", h_trans_bandwidth="auto", method="fir", n_jobs=n_jobs,
               verbose="error")
    epochs = mne.Epochs(raw, events, event_id=EVENT_IDS, tmin=tmin, tmax=tmax, preload=True,
                        baseline=(None, -0.05), detrend=1, decim=decim, verbose="error")
    if len(epochs.times) != samples:
        raise RuntimeError(f"Unexpected epoch length for {raw_path.name}")
    return epochs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bids", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n-jobs", default=1, help='CPU workers, or "cuda"')
    args = parser.parse_args()
    n_jobs = args.n_jobs if args.n_jobs == "cuda" else int(args.n_jobs)
    decisions = json.loads((Path(__file__).with_name("qc_decisions.json")).read_text(encoding="utf-8"))
    for recording in decisions:
        subject, task, run = recording.split("_")
        for acq in ("sp", "acc"):
            name = f"{subject}_{task}_acq-{acq}_{run}"
            target = args.out / subject / "ieeg" / f"{name}_epo.fif"
            if target.exists():
                continue
            epochs = make_epochs(args.bids / subject / "ieeg" / f"{name}_ieeg.fif", n_jobs)
            target.parent.mkdir(parents=True, exist_ok=True)
            epochs.save(target, verbose="error")
            print(f"{target.name}: {len(epochs)} epochs", flush=True)


if __name__ == "__main__":
    main()
