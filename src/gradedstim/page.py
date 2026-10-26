"""Data for the interactive page (docs/data/page.json) and the time-sweep GIF, drawn from results/ only."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

from .figures import colour_limit, linear_edges, log_edges, remove_mains  # noqa: E402

# The IASP 2026 poster palette.
PAPER, INK, MUTED, FAINT, SHADE = "#F4F1EA", "#22211E", "#6B675F", "#ABA597", "#EAE5DA"
INTENSITY = ("#D3A15F", "#B8582F", "#6E1F2B")
REGION = {"S1": "#3E7F62", "PFC": "#2F7DAB", "ACC": "#795098"}
MAP_CMAP = LinearSegmentedColormap.from_list("paper_div", [(0, "#2E6F86"), (0.25, "#9DBDC6"), (0.5, PAPER),
                                                         (2 / 3, "#E2B48F"), (5 / 6, "#B8582F"), (1, "#6E1F2B")])
REGIONS = ("S1", "PFC", "ACC")
CONTRASTS = (("10x-2x", "10× vs 2× MT"), ("20x-2x", "20× vs 2× MT"), ("20x-10x", "20× vs 10× MT"))


def load(results: Path) -> dict:
    folder = results / "primary"
    with np.load(folder / "figure_data.npz") as source:
        traces = remove_mains(source["traces"], source["trace_times"])
        trace_ms = source["trace_times"] * 1000
    with np.load(folder / "tfce_maps.npz") as tfce, np.load(folder / "animal_maps.npz") as animals:
        effect, mask = tfce["effect"], tfce["mask"]
        frequencies, map_ms = animals["frequencies"], animals["times"] * 1000
    n = np.isfinite(traces[:, 0, :, 0]).sum(axis=0)
    mean = np.nanmean(traces, axis=0)
    se = np.nanstd(traces, axis=0, ddof=1) / np.sqrt(n)[None, :, None]
    contrasts = pd.read_csv(folder / "contrasts.csv")
    return {"trace_ms": trace_ms, "mean": mean, "se": se, "n": n, "effect": effect, "mask": mask,
            "frequencies": frequencies, "map_ms": map_ms, "contrasts": contrasts}


def write_json(data: dict, target: Path) -> None:
    rows = data["contrasts"].set_index(["outcome", "region", "contrast"])
    power = [[{outcome: [round(float(10 ** rows.loc[(outcome, r, c), k]), 4) for k in ("estimate", "wald_ci_low", "wald_ci_high")]
               + [float(f"{rows.loc[(outcome, r, c), 'p_holm']:.3g}")]
               for outcome in ("total", "evoked", "induced")} for r in REGIONS] for c, _ in CONTRASTS]
    page = {
        "regions": list(REGIONS), "contrasts": [list(c) for c in CONTRASTS], "n": [int(x) for x in data["n"]],
        "trace": {"t": np.round(data["trace_ms"], 2).tolist(),
                  "mean": np.round(np.moveaxis(data["mean"], 1, 0), 2).tolist(),   # region, intensity, time
                  "se": np.round(np.moveaxis(data["se"], 1, 0), 2).tolist()},
        "map": {"f": np.round(data["frequencies"], 2).tolist(), "t": np.round(data["map_ms"], 1).tolist(),
                "fEdges": np.round(log_edges(data["frequencies"]), 3).tolist(),
                "tEdges": np.round(linear_edges(data["map_ms"]), 3).tolist(),
                "effect": np.round(data["effect"], 4).tolist(), "mask": data["mask"].astype(int).tolist(),
                "limit": colour_limit(data["effect"])},
        "power": power,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(page, separators=(",", ":")), encoding="utf-8")


def outline(mask: np.ndarray, t_edges, f_edges) -> list:
    segments = []
    n_f, n_t = mask.shape
    for f, t in zip(*np.nonzero(mask)):
        x0, x1, y0, y1 = t_edges[t], t_edges[t + 1], f_edges[f], f_edges[f + 1]
        if t == 0 or not mask[f, t - 1]:
            segments.append([(x0, y0), (x0, y1)])
        if t == n_t - 1 or not mask[f, t + 1]:
            segments.append([(x1, y0), (x1, y1)])
        if f == 0 or not mask[f - 1, t]:
            segments.append([(x0, y0), (x1, y0)])
        if f == n_f - 1 or not mask[f + 1, t]:
            segments.append([(x0, y1), (x1, y1)])
    return segments


def write_gif(data: dict, target: Path, contrast: int = 1) -> None:
    """Waveforms drawn up to a sweeping time cursor, beside the 20x vs 2x MT map revealed up to it."""
    plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "text.color": INK, "axes.edgecolor": FAINT,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED})
    t_ms, f_edges, t_edges = data["trace_ms"], log_edges(data["frequencies"]), linear_edges(data["map_ms"])
    limit = colour_limit(data["effect"])
    figure = plt.figure(figsize=(8.2, 5.4), facecolor=PAPER)
    grid = figure.add_gridspec(3, 2, width_ratios=[1.55, 1], left=0.075, right=0.985, top=0.9, bottom=0.1,
                               hspace=0.42, wspace=0.16)
    cursors, lines, images = [], [], []
    for r, region in enumerate(REGIONS):
        wave = figure.add_subplot(grid[r, 0], facecolor=PAPER)
        heat = figure.add_subplot(grid[r, 1], facecolor=PAPER)
        wave.axvspan(t_ms[0], 0, color=SHADE, lw=0)
        wave.axhline(0, color=FAINT, lw=0.6)
        drawn = []
        for c in range(3):
            wave.plot(t_ms, data["mean"][c, r], color=INTENSITY[c], lw=1.0, alpha=0.16)
            drawn.append(wave.plot([], [], color=INTENSITY[c], lw=1.3)[0])
        lines.append(drawn)
        low = np.min(data["mean"][:, r] - data["se"][:, r])
        high = np.max(data["mean"][:, r] + data["se"][:, r])
        wave.set_ylim(low - 0.08 * (high - low), high + 0.08 * (high - low))
        wave.set_xlim(t_ms[0], t_ms[-1])
        wave.set_xticks([0, 200, 400] if r == 2 else [])
        wave.set_ylabel("µV")
        image = heat.pcolormesh(t_edges, f_edges, np.ma.masked_all(data["effect"][contrast, r].shape), cmap=MAP_CMAP,
                                norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit), shading="flat", rasterized=True)
        images.append(image)
        heat.set_yscale("log")
        heat.set_ylim(20, 200)
        heat.set_yticks([20, 50, 100, 200], ["20", "50", "100", "200 Hz"])
        heat.minorticks_off()
        heat.set_xlim(0, 400)
        heat.set_xticks([0, 200, 400] if r == 2 else [])
        for axis in (wave, heat):
            for side in ("top", "right"):
                axis.spines[side].set_visible(False)
            axis.tick_params(length=2.5, labelsize=8)
        cursors += [wave.axvline(t_ms[0], color=INK, lw=0.8), heat.axvline(0, color=INK, lw=0.8)]
        wave.add_patch(plt.Rectangle((0.0, 1.07), 0.018, 0.13, transform=wave.transAxes, color=REGION[region],
                                     clip_on=False))
        wave.text(0.03, 1.07, region, transform=wave.transAxes, fontsize=10, fontweight="semibold", va="bottom")
    figure.text(0.075, 0.955, "Stimulation-locked response", fontsize=10, color=MUTED)
    figure.text(0.62, 0.955, f"Total power, {CONTRASTS[contrast][1]}", fontsize=10, color=MUTED)
    for c, label in enumerate(("2× MT", "10× MT", "20× MT")):
        x = 0.31 + c * 0.085
        figure.add_artist(plt.Line2D([x, x + 0.022], [0.962, 0.962], color=INTENSITY[c], lw=2, transform=figure.transFigure))
        figure.text(x + 0.028, 0.962, label, color=INK, fontsize=9, va="center")
    figure.axes[-2].set_xlabel("Time from stimulation (ms)", fontsize=9)
    figure.axes[-1].set_xlabel("Time (ms); outline: corrected (TFCE)", fontsize=9)
    outlines = [None, None, None]
    frames = list(np.arange(-150, 551, 10)) + [550] * 18

    def draw(now):
        for r in range(3):
            shown = t_ms <= now
            for c in range(3):
                lines[r][c].set_data(t_ms[shown], data["mean"][c, r][shown])
            revealed = np.ma.masked_where(np.broadcast_to(data["map_ms"] > now, data["effect"][contrast, r].shape),
                                          data["effect"][contrast, r])
            images[r].set_array(revealed)
            if outlines[r] is not None:
                outlines[r].remove()
            visible = data["mask"][contrast, r] & (data["map_ms"][None, :] <= now)
            outlines[r] = images[r].axes.add_collection(LineCollection(outline(visible, t_edges, f_edges),
                                                                       colors=INK, linewidths=1.1))
        for cursor in cursors:
            cursor.set_xdata([now, now])
        return []

    target.parent.mkdir(parents=True, exist_ok=True)
    FuncAnimation(figure, draw, frames=frames, blit=False).save(target, writer=PillowWriter(fps=16), dpi=100,
                                                                savefig_kwargs={"facecolor": PAPER})
    plt.close(figure)


def make(config: dict) -> None:
    data = load(config["paths"]["results"])
    docs = config["paths"]["figures"].parent
    write_json(data, docs / "data" / "page.json")
    write_gif(data, config["paths"]["figures"] / "time-sweep.gif")
