# Graded ulnar-nerve stimulation in pigs: S1, PFC and ACC

Analysis code for

> Atchuthan NA, Pedersen CK, Jensen W, Meijs S. *Graded peripheral nerve stimulation is associated with
> phase-locked cortical power increases in anaesthetised pigs.* Center for Neuroplasticity and Pain,
> Aalborg University.

Eighteen anaesthetised pigs received electrical ulnar-nerve stimulation at 2, 10 and 20 times motor
threshold while S1, PFC and ACC were recorded simultaneously (two 32-channel surface arrays and a
32-channel depth array). The analysis asks whether stimulus intensity changes cortical power, whether
any change sits in the phase-locked (evoked) or non-phase-locked (induced) part of the response, and
where in time and frequency it occurs.

## Contents

| Path | What it holds |
|---|---|
| `config.toml` | Every analysis parameter (frequencies, windows, seeds, permutations) |
| `src/gradedstim/features.py` | Morlet power per recording: total, evoked and induced power, maps, waveforms, spectra |
| `src/gradedstim/models.py` | Mixed models for the 35-120 Hz, 0-400 ms power endpoints and the intensity contrasts |
| `src/gradedstim/maps.py` | Animal-level time-frequency maps with TFCE and maximum-\|t\| correction |
| `src/gradedstim/aperiodic.py` | Exploratory fits of the aperiodic (1/f-like) spectral background |
| `src/gradedstim/correlations.py` | Exploratory correlations between animal-level responses (Supplementary Figure S7) |
| `src/gradedstim/figures.py`, `tables.py` | Figures 3-6, Supplementary Figures S1-S7 and Supplementary Tables S1-S6 |
| `results/` | All numbers behind the figures and tables (primary analysis and three sensitivity analyses) |
| `figures/` | The rendered figures |
| `preprocessing/` | How the cleaned epochs were made from the BIDS recordings |

`results/primary` is the analysis reported in the article. The three other folders are the sensitivity
analyses in Supplementary Table S6: averaging the stored repaired channels as they are (`with_copies`),
putting back animal 13's ACC recordings (`with_animal13_acc`), and both.

## Running it

Python 3.12 and the pinned packages in `pyproject.toml` (MNE 1.11, NumPy 1.26, statsmodels 0.14.2,
FOOOF 1.1.1):

```
pip install -e .          # or: uv sync (exact versions in uv.lock)
python -m gradedstim figures                     # redraw all figures from results/ (no recordings needed)
python -m gradedstim features --epochs <cleaned epochs folder>
python -m gradedstim statistics
```

`features` takes about 30 minutes on 6 cores and `statistics` about 10 minutes. The cleaned epochs are
made from the BIDS recordings with the two scripts in `preprocessing/`.

## Checks against the published run

Before release, this code was run on the same data and every output was compared with the run reported
in the article:

- Features of all 154 sequences agree to floating-point rounding (relative differences below 2 × 10⁻¹³).
- The corrected time-frequency maps, permutation null distributions and corrected masks are identical.
- Power estimates agree within 10⁻¹⁰ and their P values within 10⁻⁷. The aperiodic estimates agree within
  2 × 10⁻⁸ (their spectral fits are slightly more sensitive to rounding). Every Holm decision is unchanged
  in all four analyses.
- Supplementary Tables S1-S6 come out identical to the published tables.
- `preprocessing/clean_epochs.py` reproduces the cleaned epochs of all 154 sequences bit for bit.
  Re-filtering a raw recording with `make_epochs.py` on a CPU differs from the original GPU-filtered epochs
  by at most 0.0001 µV.

## Data

The BIDS-formatted recordings are being prepared for release as a separate dataset publication. Until
then they are available from the corresponding author on reasonable request.

## License

MIT
