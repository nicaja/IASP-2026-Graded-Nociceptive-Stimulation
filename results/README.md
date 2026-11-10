# Results

Every number in the poster's figures, the interactive page and the article comes from these files. `primary/` is the
reported analysis; the other three folders are the article's sensitivity analyses
(`with_copies`: stored repaired channels averaged as they are; `with_animal13_acc`: animal 13's ACC
recordings put back; `with_copies_and_animal13_acc`: both). Each folder holds the same files.

| File | Contents |
|---|---|
| `scalar_features.csv` | One row per sequence, intensity and region: `total`, `evoked` and `induced` power (mean log10 power over 35–120 Hz and 0–400 ms), `evoked_fraction` (mean evoked ÷ mean total power over the same band and window, in linear units), `n_events`, `n_channels` and the standardised recording order `run_order_z` |
| `aperiodic_features.csv` | FOOOF fit of each sequence's static 0–550 ms spectrum: `aperiodic_offset`, `aperiodic_exponent`, `adjusted_power` (35–120 Hz power above the fitted background), `fit_r_squared`, `fit_error`, `fit_ok` |
| `contrasts.csv` | Mixed-model contrasts for every outcome, region and contrast: `estimate` (higher minus lower intensity; for the power outcomes a log10 ratio, so 10^estimate is the power ratio), `standard_error`, Wald interval, `statistic_z`, `p_value`, `p_holm` (Holm over the nine region-by-contrast tests of the outcome), animal-bootstrap interval, `n_animals`, `n_blocks` |
| `animal_maps.npz` | `maps`: animal-averaged log10 total power, animals × intensities × regions × 30 frequencies × 40 time bins (NaN where excluded); `contrasts`: the same per contrast (higher minus lower intensity); `frequencies`, `times`, `subjects` |
| `tfce_maps.npz` | Per contrast and region (3 × 3 × 30 × 40): `effect` (mean within-animal log10 difference), `statistic` (TFCE), `p_within` (sign-flip P within the map), `p_global` (Bonferroni over the nine maps, min(9 × p_within, 1)), `mask` (p_global < 0.05) and `maximum_mask` from the maximum-\|t\| procedure |
| `maximum_maps.npz` | The sensitivity procedure: observed `statistic` (t per bin), `p_global`, and the 4096 `null_maximum` values |
| `map_tests.csv` | One row per map: smallest corrected P and number of surviving bins under each procedure (`tfce_p`, `tfce_bins`, `maximum_p`, `maximum_bins`) and the map's `mean_effect` |
| `figure_data.npz` (primary only) | Animal-level averages for the descriptive figures: `traces` (animals × intensities × regions × samples, µV), `fraction_maps`, `spectrum_observed` and `spectrum_background` (log10), with their time and frequency axes and `subjects` |
| `correlations.npz` (primary only) | The poster's correlation matrix: Spearman correlations (`spearman`, 2 contrasts × 21 × 21 measures), their `labels`, the `animal_differences` behind them and the 17 `subjects` with data in all three regions |

`software_versions.json` lists the package versions of the run. The `statistics` stage also writes the
article's supplementary tables to `tables/` (kept out of the repository until the article is published).

## Checks against the reported run

Before release, this code was run on the same data and every output was compared with the run reported in the article:

- Features of all 154 sequences agree to floating-point rounding (relative differences below 2 × 10⁻¹³).
- The corrected time–frequency maps, permutation null distributions and corrected masks are identical.
- Power estimates agree within 10⁻¹⁰ and their P values within 10⁻⁷. The aperiodic estimates agree within 2 × 10⁻⁸ (their spectral fits are slightly more sensitive to rounding). Every Holm decision is unchanged in all four analyses.
- The supplementary tables come out identical to the article's.
- `preprocessing/clean_epochs.py` reproduces the cleaned epochs of all 154 sequences bit for bit. Re-filtering a raw recording with `make_epochs.py` on a CPU differs from the original GPU-filtered epochs by at most 0.0001 µV.

`pytest` (installed with `pip install -e .[test]`) checks the committed results for internal consistency: Holm adjustments, confidence intervals and the map correction.
