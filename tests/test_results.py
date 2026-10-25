"""Quick checks that need no recordings: helper functions and the consistency of results/."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests

from gradedstim.features import bin_time_axis
from gradedstim.figures import remove_mains

RESULTS = Path(__file__).resolve().parents[1] / "results"
VARIANTS = ["primary", "with_copies", "with_animal13_acc", "with_copies_and_animal13_acc"]


def test_time_bins_cover_every_sample_once():
    times = np.arange(-0.1, 0.5, 1 / 2000)
    ones = np.ones((2, len(times)))
    counts, centers = bin_time_axis(np.cumsum(ones, axis=1), times, 0.0, 0.4, 0.01)
    assert counts.shape == (2, 40)
    np.testing.assert_allclose(centers, np.arange(0.005, 0.4, 0.01))
    edges = np.arange(41) * 0.01
    inside = [((times >= lo) & ((times < hi) if i < 39 else (times <= hi))) for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:]))]
    assert sum(mask.sum() for mask in inside) == ((times >= 0) & (times <= 0.4)).sum()


def test_mains_removal_keeps_the_response():
    times = np.arange(-0.15, 0.55, 1 / 2034.5)
    response = np.where(times > 0, np.sin(2 * np.pi * 8 * times), 0.0)
    trace = response + 0.5 * np.sin(2 * np.pi * 50.1 * times + 0.3)
    cleaned = remove_mains(trace[None], times)[0]
    assert np.max(np.abs(cleaned - response)) < 0.01


@pytest.mark.parametrize("variant", VARIANTS)
def test_holm_and_wald_intervals(variant):
    table = pd.read_csv(RESULTS / variant / "contrasts.csv")
    for _, rows in table.groupby("outcome"):
        assert len(rows) == 9
        np.testing.assert_allclose(rows.p_holm, multipletests(rows.p_value, method="holm")[1])
    np.testing.assert_allclose(table.wald_ci_low, table.estimate - 1.96 * table.standard_error)
    np.testing.assert_allclose(table.wald_ci_high, table.estimate + 1.96 * table.standard_error)


@pytest.mark.parametrize("variant", VARIANTS)
def test_map_correction(variant):
    with np.load(RESULTS / variant / "tfce_maps.npz") as tfce, np.load(RESULTS / variant / "maximum_maps.npz") as maximum:
        np.testing.assert_array_equal(tfce["p_global"], np.minimum(9 * tfce["p_within"], 1))
        np.testing.assert_array_equal(tfce["mask"], tfce["p_global"] < 0.05)
        np.testing.assert_array_equal(tfce["maximum_mask"], maximum["p_global"] < 0.05)
