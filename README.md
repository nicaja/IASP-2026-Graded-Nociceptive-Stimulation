# IASP 2026: Graded Nociceptive Stimulation Across S1, PFC and ACC

[![Each animal's waveforms at 2× and 20× motor threshold and its change in total, evoked and induced power](docs/figures/each-animal.gif)](https://nicaja.github.io/IASP-2026-Graded-Nociceptive-Stimulation/)

*One animal at a time: its waveforms at 2× and 20× motor threshold (MT) and its power ratio, one dot per animal.*

Code and results for poster 105 (abstract 10418) at the IASP 2026 World Congress on Pain, Bangkok, and for the accompanying article (in preparation).

[Interactive page](https://nicaja.github.io/IASP-2026-Graded-Nociceptive-Stimulation/) · [Poster (PDF)](docs/poster.pdf)

Nickolaj Ajay Atchuthan, Christian Kruse Pedersen, Winnie Jensen and Suzan Meijs. *Temporal and Spectral Signatures of Graded Nociceptive Stimulation Across S1, PFC, and ACC in a Large-Animal Intracranial Model.* Center for Neuroplasticity and Pain, Aalborg University.

## What we found

We recorded from the primary somatosensory cortex (S1), prefrontal cortex (PFC) and anterior cingulate cortex (ACC) simultaneously in 18 anaesthetised pigs while stimulating the ulnar nerve at 2, 10 and 20 times motor threshold.

- Evoked (phase-locked) power was higher at 10× and 20× than at 2× MT in all three regions. At 20× MT it was 1.25 times the 2× MT value in S1 and PFC and 1.75 times in ACC.
- No total- or induced-power contrast survived correction.
- Corrected time–frequency maps showed total-power differences in S1 and ACC within about 160 ms of stimulation.

Separating the response components revealed intensity effects that a broad power average did not.

![Total, evoked and induced power ratios for every region and contrast](docs/figures/poster-fig3-power-components.svg)

*Fig. 3 of the poster: power ratios between intensities with 95% confidence intervals. Circles: total power; squares: evoked; triangles: induced. Filled markers with an asterisk are significant after Holm correction.*

## Code

| Path | What it holds |
|---|---|
| `config.toml` | Every analysis parameter |
| `src/gradedstim/` | The analysis: power features, mixed models, time–frequency maps, aperiodic fits, correlations, figures and tables |
| `results/` | All numbers behind the figures and tables ([guide](results/README.md)) |
| `docs/` | The interactive page, the poster and its figures |
| `preprocessing/` | How the cleaned epochs were made from the BIDS recordings |

## Running it

```
pip install -e .          # or: uv sync (exact versions in uv.lock)
python -m gradedstim figures                     # the article's figures from results/ (no recordings needed)
python -m gradedstim page                        # data for the interactive page and the GIF
python -m gradedstim features --epochs <cleaned epochs folder>
python -m gradedstim statistics
```

Python 3.12 with the package versions pinned in `pyproject.toml`. `features` takes about 30 minutes on 6 cores and `statistics` about 10.

Before release, the code was rerun on the same data: every Holm decision, corrected map and supplementary table matched the run reported in the article ([details](results/README.md#checks-against-the-reported-run)). The article's figures and tables will be added once it is published.

## Data

The BIDS-formatted recordings are being prepared for release as a separate dataset publication. Until then they are available on reasonable request from the first author ([atchuthan.com](https://atchuthan.com)).

## License

MIT
