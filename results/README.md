# Results

Every number in the figures, tables and the interactive page comes from these files. `primary/` is the
reported analysis; the other three folders are the sensitivity analyses of Supplementary Table S6
(`with_copies`: stored repaired channels averaged as they are; `with_animal13_acc`: animal 13's ACC
recordings put back; `with_copies_and_animal13_acc`: both). Each folder holds the same files.

| File | Contents |
|---|---|
| `scalar_features.csv` | One row per sequence, intensity and region: `total`, `evoked` and `induced` power (log10, 35–120 Hz, 0–400 ms), `evoked_fraction` (evoked ÷ total in linear power), `n_events`, `n_channels` and the standardised recording order `run_order_z` |
| `aperiodic_features.csv` | FOOOF fit of each sequence's static 0–550 ms spectrum: `aperiodic_offset`, `aperiodic_exponent`, `adjusted_power` (35–120 Hz power above the fitted background), `fit_r_squared`, `fit_error`, `fit_ok` |
| `contrasts.csv` | Mixed-model contrasts for every outcome, region and contrast: `estimate` (log10 ratio; 10^estimate is the power ratio), `standard_error`, Wald interval, `statistic_z`, `p_value`, `p_holm` (Holm over the nine region-by-contrast tests of the outcome), animal-bootstrap interval, `n_animals`, `n_blocks` |
| `animal_maps.npz` | `maps`: animal-averaged log10 total power, animals × intensities × regions × 30 frequencies × 40 time bins (NaN where excluded); `contrasts`: the same per contrast (higher minus lower intensity); `frequencies`, `times`, `subjects` |
| `tfce_maps.npz` | Per contrast and region (3 × 3 × 30 × 40): `effect` (mean within-animal log10 difference), `statistic` (TFCE), `p_within` (sign-flip P within the map), `p_global` (Bonferroni over the nine maps, min(9 × p_within, 1)), `mask` (p_global < 0.05) and `maximum_mask` from the maximum-\|t\| procedure |
| `maximum_maps.npz` | The sensitivity procedure: observed `statistic` (t per bin), `p_global`, and the 4096 `null_maximum` values |
| `map_tests.csv` | One row per map: smallest corrected P and number of surviving bins under each procedure (`tfce_p`, `tfce_bins`, `maximum_p`, `maximum_bins`) and the map's `mean_effect` |
| `figure_data.npz` (primary only) | Animal-level averages for the descriptive figures: `traces` (animals × intensities × regions × samples, µV), `fraction_maps`, `spectrum_observed` and `spectrum_background` (log10), with their time and frequency axes and `subjects` |
| `correlations.npz` (primary only) | Figure S7: Spearman correlations (`spearman`, 2 contrasts × 21 × 21 measures), their `labels`, the `animal_differences` behind them and the 17 `subjects` with data in all three regions |

`tables/` holds Supplementary Tables S1–S6 as LaTeX (S5 and S6 also as CSV), and `software_versions.json`
the package versions of the run.
