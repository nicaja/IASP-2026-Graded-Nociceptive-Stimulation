"""Data for the interactive page (docs/data/page.json) and the animal-by-animal GIF, drawn from results/ only.

The change in each animal is the paper's animal-level response (as in Supplementary Figure S7): the
high-minus-low difference in log10 power within each sequence, averaged within animal.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402

from .correlations import animal_differences  # noqa: E402
from .figures import colour_limit, linear_edges, log_edges, remove_mains  # noqa: E402

# The IASP 2026 poster palette.
PAPER, INK, MUTED, FAINT, SHADE = "#F4F1EA", "#22211E", "#6B675F", "#ABA597", "#EAE5DA"
INTENSITY = {"2x MT": "#D3A15F", "10x MT": "#B8582F", "20x MT": "#6E1F2B"}
COMPONENT = {"total": "#22211E", "evoked": "#1F6F78", "induced": "#B58A55"}
REGIONS = ("S1", "PFC", "ACC")
CONDITIONS = ("2x MT", "10x MT", "20x MT")
LABELS = {"10x-2x": "10× vs 2× MT", "20x-2x": "20× vs 2× MT", "20x-10x": "20× vs 10× MT"}
RATIO_LIMITS = (0.75, 3.0)


def load(results: Path, config: dict) -> dict:
    folder = results / "primary"
    with np.load(folder / "figure_data.npz") as source:
        times = source["trace_times"]
        traces = remove_mains(source["traces"], times)
        trace_subjects = [str(s) for s in source["subjects"]]
    # Display at 2-ms resolution: means of four consecutive samples.
    usable = times.size // 4 * 4
    trace_ms = times[:usable].reshape(-1, 4).mean(axis=1) * 1000
    traces = traces[..., :usable].reshape(*traces.shape[:-1], -1, 4).mean(axis=-1)
    with np.load(folder / "tfce_maps.npz") as tfce, np.load(folder / "animal_maps.npz") as animals:
        effect, mask = tfce["effect"], tfce["mask"]
        frequencies, map_ms = animals["frequencies"], animals["times"] * 1000
    scalar = pd.read_csv(folder / "scalar_features.csv", dtype={"subject": str}, float_precision="round_trip")
    aperiodic = pd.read_csv(folder / "aperiodic_features.csv", dtype={"subject": str}, float_precision="round_trip")
    changes = animal_differences(scalar, aperiodic, config)
    changes = changes.loc[changes.measure.isin(COMPONENT)]
    subjects = sorted(trace_subjects, key=int)
    order = [trace_subjects.index(s) for s in subjects]
    return {"subjects": subjects, "trace_ms": trace_ms, "traces": traces[order], "changes": changes,
            "effect": effect, "mask": mask, "frequencies": frequencies, "map_ms": map_ms,
            "contrasts": pd.read_csv(folder / "contrasts.csv"), "design": config["design"]["contrasts"]}


def change_table(data: dict) -> dict:
    """{contrast: {region: {component: [log10 change per animal, None where missing]}}}"""
    table = {}
    for contrast, _, _ in data["design"]:
        rows = data["changes"].loc[data["changes"].contrast == contrast]
        table[contrast] = {region: {component: [
            None if pd.isna(v) else round(float(v), 5)
            for v in rows.loc[(rows.region == region) & (rows.measure == component)]
            .set_index("subject")["difference"].reindex(data["subjects"])]
            for component in COMPONENT} for region in REGIONS}
    return table


def model_table(data: dict) -> dict:
    rows = data["contrasts"].set_index(["outcome", "region", "contrast"])
    return {contrast: {region: {component: [round(float(10 ** rows.loc[(component, region, contrast), k]), 4)
                                            for k in ("estimate", "wald_ci_low", "wald_ci_high")]
                                + [float(f"{rows.loc[(component, region, contrast), 'p_holm']:.3g}")]
                                for component in COMPONENT} for region in REGIONS}
            for contrast, _, _ in data["design"]}


def write_json(data: dict, target: Path) -> None:
    traces = data["traces"]
    n = np.isfinite(traces[:, 0, :, 0]).sum(axis=0)
    rounded = np.round(np.moveaxis(traces, 2, 1), 1)   # animal, region, intensity, time
    page = {
        "regions": list(REGIONS), "conditions": list(CONDITIONS), "animals": data["subjects"],
        "contrasts": [[c, LABELS[c], CONDITIONS.index(high), CONDITIONS.index(low)] for c, high, low in data["design"]],
        "n": [int(x) for x in n],
        "change": change_table(data), "model": model_table(data),
        "trace": {"t": np.round(data["trace_ms"], 1).tolist(),
                  "animal": [[None if np.isnan(rounded[a, r]).all() else rounded[a, r].tolist()
                              for r in range(3)] for a in range(len(data["subjects"]))],
                  "mean": np.round(np.moveaxis(np.nanmean(traces, axis=0), 1, 0), 2).tolist(),
                  "se": np.round(np.moveaxis(np.nanstd(traces, axis=0, ddof=1) / np.sqrt(n)[None, :, None], 1, 0),
                                 2).tolist()},
        "map": {"f": np.round(data["frequencies"], 2).tolist(), "t": np.round(data["map_ms"], 1).tolist(),
                "fEdges": np.round(log_edges(data["frequencies"]), 3).tolist(),
                "tEdges": np.round(linear_edges(data["map_ms"]), 3).tolist(),
                "effect": np.round(data["effect"], 4).tolist(), "mask": data["mask"].astype(int).tolist(),
                "limit": colour_limit(data["effect"])},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(page, separators=(",", ":")), encoding="utf-8")


def write_gif(data: dict, target: Path, contrast: str = "20x-2x") -> None:
    """One animal at a time: its 2x and 20x MT waveforms and where its power change falls among the others."""
    plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "text.color": INK, "axes.edgecolor": FAINT,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED})
    _, high, low = next(d for d in data["design"] if d[0] == contrast)
    pair = (CONDITIONS.index(low), CONDITIONS.index(high))
    changes, model = change_table(data)[contrast], model_table(data)[contrast]
    subjects, t_ms, traces = data["subjects"], data["trace_ms"], data["traces"]
    figure = plt.figure(figsize=(8.2, 5.6), facecolor=PAPER)
    grid = figure.add_gridspec(3, 2, width_ratios=[1.35, 1], left=0.07, right=0.985, top=0.86, bottom=0.09,
                               hspace=0.42, wspace=0.2)
    jitter = np.linspace(-0.16, 0.16, len(subjects))[np.argsort(np.random.default_rng(3).permutation(len(subjects)))]
    rows = []
    for r, region in enumerate(REGIONS):
        wave = figure.add_subplot(grid[r, 0], facecolor=PAPER)
        strip = figure.add_subplot(grid[r, 1], facecolor=PAPER)
        wave.axvspan(t_ms[0], 0, color=SHADE, lw=0)
        wave.axhline(0, color=FAINT, lw=0.6)
        values = traces[:, list(pair), r]
        low_y, high_y = np.nanmin(values), np.nanmax(values)
        wave.set_ylim(low_y - 0.06 * (high_y - low_y), high_y + 0.06 * (high_y - low_y))
        wave.set_xlim(t_ms[0], t_ms[-1])
        wave.set_xticks([0, 200, 400] if r == 2 else [])
        wave.set_ylabel("µV")
        lines = [wave.plot([], [], color=INTENSITY[CONDITIONS[c]], lw=1.3)[0] for c in pair]
        note = wave.text(0.5, 0.5, "", transform=wave.transAxes, ha="center", va="center", color=MUTED, fontsize=8.5)
        strip.axhline(1, color=FAINT, lw=0.8, ls=(0, (2, 3)))
        strip.set_yscale("log")
        strip.set_ylim(*RATIO_LIMITS)
        strip.set_yticks([0.8, 1, 1.5, 2, 3], ["0.8", "1", "1.5", "2", "3"])
        strip.minorticks_off()
        strip.set_xlim(-0.5, 2.75)
        strip.set_xticks([0, 1, 2], ["Total", "Evoked", "Induced"] if r == 2 else [])
        for axis in (wave, strip):
            for side in ("top", "right"):
                axis.spines[side].set_visible(False)
            axis.tick_params(length=2.5, labelsize=8)
        wave.add_patch(plt.Rectangle((0.0, 1.07), 0.016, 0.13, transform=wave.transAxes, clip_on=False,
                                     color={"S1": "#3E7F62", "PFC": "#2F7DAB", "ACC": "#795098"}[region]))
        wave.text(0.028, 1.07, region, transform=wave.transAxes, fontsize=10, fontweight="semibold", va="bottom")
        ratios = np.array([[np.nan if v is None else 10 ** v for v in changes[region][k]] for k in COMPONENT])
        clipped = np.clip(ratios, *RATIO_LIMITS)
        dots = [strip.scatter([], [], s=13, color=COMPONENT[k], alpha=0.5, lw=0) for k in COMPONENT]
        beyond = [strip.scatter([], [], s=22, marker="^", color=COMPONENT[k], alpha=0.6, lw=0) for k in COMPONENT]
        current = strip.plot([], [], color=INK, lw=1.1, marker="o", ms=4.5, mfc=PAPER, mec=INK, mew=1.2)[0]
        last_wave = wave
        rows.append({"lines": lines, "note": note, "dots": dots, "beyond": beyond, "ratios": ratios,
                     "mean": np.nanmean(values, axis=0), "current": current, "clipped": clipped,
                     "values": values, "strip": strip, "region": region})
    figure.text(0.07, 0.95, f"Each animal, {LABELS[contrast]}", fontsize=11, fontweight="semibold", color=INK)
    counter = figure.text(0.07, 0.912, "", fontsize=9, color=MUTED)
    for i, c in enumerate(pair):
        x = 0.36 + i * 0.09
        figure.add_artist(plt.Line2D([x, x + 0.022], [0.958, 0.958], color=INTENSITY[CONDITIONS[c]], lw=2,
                                     transform=figure.transFigure))
        figure.text(x + 0.028, 0.958, CONDITIONS[c].replace("x", "×"), fontsize=9, va="center")
    figure.text(0.585, 0.95, f"Power ratio {high.split()[0]} / {low.split()[0]} MT, one dot per animal".replace("x", "×"),
                fontsize=9, color=MUTED)
    last_wave.set_xlabel("Time from stimulation (ms)", fontsize=9)
    summary = []

    def draw(frame):
        shown = min(frame + 1, len(subjects))
        final = frame >= len(subjects)
        counter.set_text("Mean of all animals · squares: model estimate and 95% CI, filled where Holm P < 0.05"
                         if final else f"Animal {int(subjects[frame])}  ({shown} of {len(subjects)})")
        for row in rows:
            animal = min(frame, len(subjects) - 1)
            trace = row["mean"] if final else row["values"][animal]
            has_data = bool(np.isfinite(trace).all())
            for line, values in zip(row["lines"], trace):
                line.set_data(t_ms, values) if has_data else line.set_data([], [])
            row["note"].set_text("" if has_data else f"{row['region']} excluded for this animal")
            for k in range(3):
                points, raw = row["clipped"][k, :shown], row["ratios"][k, :shown]
                for artist, keep in ((row["dots"][k], np.isfinite(raw) & (raw <= RATIO_LIMITS[1])),
                                     (row["beyond"][k], np.isfinite(raw) & (raw > RATIO_LIMITS[1]))):
                    artist.set_offsets(np.c_[k + jitter[:shown][keep], points[keep]] if keep.any() else np.empty((0, 2)))
            point = row["clipped"][:, animal]
            if final or not np.isfinite(point).all():
                row["current"].set_data([], [])
            else:
                row["current"].set_data(np.arange(3) + jitter[animal], point)
            if final and not summary:
                for k, component in enumerate(COMPONENT):
                    ratio, ci_low, ci_high, p = model[row["region"]][component]
                    row["strip"].plot([k + 0.38] * 2, np.clip([ci_low, ci_high], *RATIO_LIMITS), color=COMPONENT[component], lw=1.6)
                    row["strip"].plot(k + 0.38, ratio, marker="s", ms=5.5, color=COMPONENT[component],
                                      mfc=COMPONENT[component] if p < 0.05 else PAPER, mew=1.4)
        if final:
            summary.append(True)
        return []

    target.parent.mkdir(parents=True, exist_ok=True)
    frames = list(range(len(subjects))) + [len(subjects)] * 8
    FuncAnimation(figure, draw, frames=frames, blit=False).save(target, writer=PillowWriter(fps=2.5), dpi=100,
                                                                savefig_kwargs={"facecolor": PAPER})
    plt.close(figure)


def make(config: dict) -> None:
    data = load(config["paths"]["results"], config)
    docs = config["paths"]["figures"].parent
    write_json(data, docs / "data" / "page.json")
    write_gif(data, config["paths"]["figures"] / "each-animal.gif")
