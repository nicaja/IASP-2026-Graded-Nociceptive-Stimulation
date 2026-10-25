# Preprocessing

These two steps turn the BIDS recordings into the cleaned epochs that the analysis reads.

1. **`make_epochs.py`**: for each sequence, the S1/PFC file (`acq-sp`) and the ACC file (`acq-acc`)
   are notch-filtered (50, 100, 150 Hz), band-passed 0.5-200 Hz, and cut into epochs from -0.2 to
   1.0 s around each stimulus at about 2000 Hz.
2. **`clean_epochs.py`**: the two files are joined into one 96-channel recording, the recorded bad
   channels are applied, and each remaining channel is screened epoch by epoch with fixed technical
   rules (flat lines, plateaus, extreme values, abrupt steps). An unusable channel-epoch is filled with
   a copy of a usable contact from the same region and epoch; a sidecar file records which contact
   every sample came from, so the analysis counts each physical contact once.

`qc_decisions.json` lists the bad channels of each of the 154 analysed sequences. They were found by an
automated detector and confirmed by visual review; they are applied here exactly as recorded.

```
python preprocessing/make_epochs.py --bids <BIDS root> --out <epochs folder>
python preprocessing/clean_epochs.py --epochs <epochs folder> --out <cleaned epochs folder>
```
