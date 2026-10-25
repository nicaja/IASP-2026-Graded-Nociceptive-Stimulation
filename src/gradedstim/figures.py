"""Figures 3-6 and Supplementary Figures S1-S7, drawn from the files in results/ only."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter  # noqa: E402

REGIONS = ("S1", "PFC", "ACC")
CONDITIONS = ("2x MT", "10x MT", "20x MT")
CONTRASTS = ("10x-2x", "20x-2x", "20x-10x")
TIMES = "\N{MULTIPLICATION SIGN}"
CONDITION_LABELS = {c: c.replace("x", TIMES) for c in CONDITIONS}
CONTRAST_LABELS = {"10x-2x": f"10{TIMES} vs 2{TIMES} MT", "20x-2x": f"20{TIMES} vs 2{TIMES} MT",
                   "20x-10x": f"20{TIMES} vs 10{TIMES} MT"}

WHITE, INK, MUTED, GRID, BORDER = "#FFFFFF", "#15191E", "#5F6872", "#E4E4E4", "#969A9D"
CONDITION_COLORS = {"2x MT": "#188DC1", "10x MT": "#BE8117", "20x MT": "#D14E67"}
OUTCOME_COLORS = {"total": "#242A31", "evoked": "#087F8C", "induced": "#BB713F"}
OUTCOME_MARKERS = {"total": "o", "evoked": "s", "induced": "^"}
APERIODIC_COLORS = {"aperiodic_exponent": "#246D91", "aperiodic_offset": "#746582", "adjusted_power": "#B97524"}
EFFECT_CMAP = sns.color_palette("icefire", as_cmap=True)
FRACTION_CMAP = mpl.colormaps["magma"]
MAP_CONTOUR = "#F5F7F8"
ROW_POSITIONS = np.asarray([10.0, 9.0, 8.0, 6.0, 5.0, 4.0, 2.0, 1.0, 0.0])
ROW_LOOKUP = dict(zip([(r, c) for r in REGIONS for c in CONTRASTS], ROW_POSITIONS))


# ----------------------------------------------------------------------------- figure data

def remove_mains(traces: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Subtract a 50-Hz sinusoid fitted to each trace's prestimulus samples (display only).

    The frequency is searched over 49.5-50.5 Hz in 0.05-Hz steps; the fit includes an offset and a
    linear trend, but only the sinusoid is removed. A notch filter would ring across the short baseline.
    """
    times = np.asarray(times, dtype=float)
    baseline = times < -0.002
    designs = [np.c_[np.sin(2 * np.pi * f * times), np.cos(2 * np.pi * f * times), np.ones_like(times), times]
               for f in np.arange(49.5, 50.51, 0.05)]
    cleaned = np.array(traces, dtype=float)
    for index in np.ndindex(cleaned.shape[:-1]):
        trace = cleaned[index]
        if np.isnan(trace).any():
            continue
        fits = [np.linalg.lstsq(d[baseline], trace[baseline], rcond=None) for d in designs]
        best = int(np.argmin([((trace[baseline] - d[baseline] @ f[0]) ** 2).sum() for d, f in zip(designs, fits)]))
        cleaned[index] = trace - designs[best][:, :2] @ fits[best][0][:2]
    return cleaned


def write_figure_data(features: dict, spectral: pd.DataFrame, folder: Path, config: dict) -> None:
    """Animal-level averages for the descriptive figures (primary weighting, exclusions applied)."""
    subjects = features["subjects"]
    ids = np.asarray(sorted(np.unique(subjects), key=int))
    data = {"subjects": ids, "trace_times": features["trace_times"], "map_times": features["map_times"],
            "scalar_frequencies": features["scalar_frequencies"],
            "spectrum_frequencies": features["spectrum_frequencies"]}
    for output, field in (("traces", "traces"), ("fraction_maps", "fraction_map")):
        means = np.stack([features[field][subjects == animal].mean(axis=0) for animal in ids])
        for subject, region in config["design"]["excluded"]:
            means[ids == subject.zfill(2), :, REGIONS.index(region)] = np.nan
        data[output] = means
    fits = spectral.loc[spectral.fit_ok]
    fit_ids = sorted(fits.subject.unique(), key=int)
    frequencies = features["spectrum_frequencies"]
    observed = np.full((len(fit_ids), 3, 3, len(frequencies)), np.nan)
    background = np.full_like(observed, np.nan)
    for s, subject in enumerate(fit_ids):
        for c, condition in enumerate(CONDITIONS):
            for r, region in enumerate(REGIONS):
                rows = fits.loc[(fits.subject == subject) & (fits.intensity == condition) & (fits.region == region)]
                if rows.empty:
                    continue
                observed[s, c, r] = np.log10(features["spectrum"][rows.block_index.to_numpy(), c, r]).mean(axis=0)
                background[s, c, r] = (rows.aperiodic_offset.to_numpy()[:, None]
                                       - rows.aperiodic_exponent.to_numpy()[:, None] * np.log10(frequencies)).mean(axis=0)
    data.update(spectrum_observed=observed, spectrum_background=background)
    np.savez_compressed(folder / "figure_data.npz", **data)


# ----------------------------------------------------------------------------- shared style

def configure() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 9.5, "axes.labelsize": 8.5,
        "axes.linewidth": 0.6, "axes.edgecolor": BORDER, "axes.labelcolor": INK, "axes.titlecolor": INK,
        "text.color": INK, "xtick.color": "#343B43", "ytick.color": "#343B43", "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0, "figure.facecolor": WHITE, "axes.facecolor": WHITE, "savefig.facecolor": WHITE,
        "pdf.fonttype": 42, "axes.unicode_minus": False, "legend.frameon": False, "legend.markerscale": 0.85,
        "lines.solid_capstyle": "butt",
    })


def save(figure, folder: Path, stem: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for suffix, dpi in (("pdf", 400), ("png", 200)):
        figure.savefig(folder / f"{stem}.{suffix}", dpi=dpi, bbox_inches="tight", pad_inches=0.035)
    plt.close(figure)


def style_axis(axis, *, grid_axis: str | None = None) -> None:
    for side, spine in axis.spines.items():
        spine.set_visible(side in ("left", "bottom"))
        spine.set_color(BORDER)
        spine.set_linewidth(0.6)
    axis.tick_params(length=2.5, width=0.6, color="#73777A")
    if grid_axis:
        axis.grid(axis=grid_axis, color=GRID, linewidth=0.4, alpha=0.65)
        axis.set_axisbelow(True)


def title(axis, panel: str, text: str) -> None:
    axis.set_title(rf"$\mathbf{{{panel}}}$   {text}", loc="left", pad=9)


def linear_edges(centers):
    centers = np.asarray(centers, dtype=float)
    middle = (centers[:-1] + centers[1:]) / 2
    return np.concatenate(([2 * centers[0] - middle[0]], middle, [2 * centers[-1] - middle[-1]]))


def log_edges(centers):
    centers = np.asarray(centers, dtype=float)
    middle = np.sqrt(centers[:-1] * centers[1:])
    return np.concatenate(([centers[0] ** 2 / middle[0]], middle, [centers[-1] ** 2 / middle[-1]]))


def log_frequency_axis(axis, ticks, top) -> None:
    axis.set_yscale("log")
    axis.set_ylim(20.0, top)
    axis.yaxis.set_major_locator(FixedLocator(ticks))
    axis.set_yticklabels([f"{t:g}" for t in ticks])
    axis.minorticks_off()


def draw_outline(axis, time_edges, frequency_edges, mask, *, linewidth=0.85, linestyle="solid") -> None:
    """Outline the corrected bins along the native bin edges."""
    segments = []
    n_f, n_t = mask.shape
    for f, t in zip(*np.nonzero(mask)):
        x0, x1, y0, y1 = time_edges[t], time_edges[t + 1], frequency_edges[f], frequency_edges[f + 1]
        if t == 0 or not mask[f, t - 1]:
            segments.append([(x0, y0), (x0, y1)])
        if t == n_t - 1 or not mask[f, t + 1]:
            segments.append([(x1, y0), (x1, y1)])
        if f == 0 or not mask[f - 1, t]:
            segments.append([(x0, y0), (x1, y0)])
        if f == n_f - 1 or not mask[f + 1, t]:
            segments.append([(x0, y1), (x1, y1)])
    if segments:
        axis.add_collection(LineCollection(segments, colors=MAP_CONTOUR, linewidths=linewidth,
                                           linestyles=linestyle, zorder=8))


def forest_labels(n_panels: int, *, height: float, top: float, bottom: float, label_width: float):
    """Shared region and contrast labels to the left of one or more forest panels."""
    figure = plt.figure(figsize=(7.2, height))
    grid = figure.add_gridspec(1, n_panels + 1, width_ratios=[label_width] + [1] * n_panels,
                               left=0.015, right=0.985, bottom=bottom, top=top, wspace=0.12)
    labels = figure.add_subplot(grid[0])
    labels.set_ylim(-0.65, 11.55)
    labels.set_axis_off()
    labels.text(0.02, 1.04, f"Intensity ({TIMES} MT)", transform=labels.transAxes, fontsize=8, color=MUTED)
    for region, y in zip(REGIONS, [11, 7, 3]):
        labels.text(0.02, y, region, transform=labels.get_yaxis_transform(), fontsize=9.5, fontweight="bold", va="center")
    for (region, contrast), y in ROW_LOOKUP.items():
        labels.text(0.12, y, CONTRAST_LABELS[contrast].removesuffix(" MT").replace(TIMES, ""),
                    transform=labels.get_yaxis_transform(), fontsize=8.5, va="center")
    return figure, [figure.add_subplot(grid[i + 1]) for i in range(n_panels)]


def finish_forest(axis) -> None:
    axis.set_ylim(-0.65, 11.55)
    style_axis(axis, grid_axis="x")
    axis.spines["left"].set_visible(False)
    axis.tick_params(axis="y", left=False, labelleft=False)
    for y in (7.45, 3.45):
        axis.axhline(y, color=GRID, linewidth=0.5)


def matrix_labels(figure, axes, columns, *, ylabel: str) -> None:
    for index, text in enumerate(columns):
        box = axes[0, index].get_position()
        figure.text((box.x0 + box.x1) / 2, 0.945, text, ha="center", fontsize=10, fontweight="bold")
    for row, region in enumerate(REGIONS):
        box = axes[row, 0].get_position()
        figure.text(0.025, (box.y0 + box.y1) / 2, region, rotation=90, ha="center", va="center",
                    fontsize=10, fontweight="bold")
    figure.text(0.072, 0.965, ylabel, fontsize=8, color=MUTED, va="top")
    for index, axis in enumerate(axes.flat):
        axis.text(0, 1.035, chr(65 + index), transform=axis.transAxes, ha="left", va="bottom",
                  fontsize=8.5, fontweight="bold")


def holm_legend(figure, **kwargs) -> None:
    figure.legend(handles=[
        Line2D([0], [0], color=INK, marker="o", markerfacecolor=WHITE, linewidth=1.1, label="Estimate and 95% Wald interval"),
        Line2D([0], [0], color=INK, marker="o", markerfacecolor=INK, linewidth=0, label="Filled: survives Holm correction"),
    ], ncol=2, **kwargs)


# ----------------------------------------------------------------------------- waveforms

def waveform_limits(traces, region_index):
    values = traces[:, :, region_index]
    mean = np.nanmean(values, axis=0)
    sem = np.nanstd(values, axis=0, ddof=1) / np.sqrt(np.isfinite(values).sum(axis=0))
    lower, upper = min(0.0, float(np.nanmin(mean - sem))), max(0.0, float(np.nanmax(mean + sem)))
    padding = max((upper - lower) * 0.09, 0.5)
    return lower - padding, upper + padding


def fig_waveforms(data, folder) -> None:
    traces = remove_mains(data["traces"], data["trace_times"])
    times_ms = data["trace_times"] * 1000
    figure, axes = plt.subplots(3, 1, figsize=(7.2, 5.65), sharex=True)
    figure.subplots_adjust(left=0.105, right=0.975, bottom=0.095, top=0.91, hspace=0.48)
    for r, (axis, region) in enumerate(zip(axes, REGIONS)):
        values = traces[:, :, r]
        mean = np.nanmean(values, axis=0)
        sem = np.nanstd(values, axis=0, ddof=1) / np.sqrt(np.isfinite(values).sum(axis=0))
        axis.axvspan(float(times_ms[0]), 0, color="#F0F2F4", lw=0, zorder=0)
        for c, condition in enumerate(CONDITIONS):
            axis.fill_between(times_ms, mean[c] - sem[c], mean[c] + sem[c], color=CONDITION_COLORS[condition],
                              alpha=0.20, linewidth=0, zorder=1)
            axis.plot(times_ms, mean[c], color=CONDITION_COLORS[condition], linewidth=1.1, zorder=3)
        axis.axvline(0.0, color="#737D88", linewidth=0.85, linestyle=":", zorder=5)
        axis.axhline(0.0, color="#8E969F", linewidth=0.65, zorder=2)
        axis.set_xlim(float(times_ms[0]), float(times_ms[-1]))
        axis.set_ylim(*waveform_limits(traces, r))
        axis.set_xticks([-150, 0, 100, 200, 300, 400, 550])
        axis.set_ylabel(r"Amplitude ($\mu$V)")
        style_axis(axis, grid_axis="x")
        title(axis, chr(65 + r), region)
        axis.text(1, 1.035, f"n = {int(np.isfinite(values[:, 0, 0]).sum())}", transform=axis.transAxes,
                  ha="right", va="bottom", fontsize=8, color=MUTED)
    axes[-1].set_xlabel("Time from stimulation (ms)", labelpad=6)
    figure.legend(handles=[Line2D([0], [0], color=CONDITION_COLORS[c], linewidth=1.8, label=CONDITION_LABELS[c])
                           for c in CONDITIONS],
                  loc="upper center", bbox_to_anchor=(0.54, 1.005), ncol=3, fontsize=8.5, handlelength=2.6,
                  columnspacing=3.0)
    save(figure, folder, "fig3_waveforms")


def fig_individual_waveforms(data, folder) -> None:
    traces = remove_mains(data["traces"], data["trace_times"])
    times_ms = data["trace_times"] * 1000
    subjects = data["subjects"]
    figure = plt.figure(figsize=(7.2, 7.5))
    grid = figure.add_gridspec(3, 3, left=0.10, right=0.87, top=0.93, bottom=0.075, hspace=0.23, wspace=0.12)
    cmap = mpl.colormaps["RdBu_r"].copy()
    cmap.set_bad("#E0E3E6")
    for r, region in enumerate(REGIONS):
        limits = waveform_limits(traces, r)
        limit = float(np.nanmax(np.abs(traces[:, :, r])))
        for c, condition in enumerate(CONDITIONS):
            sub = grid[r, c].subgridspec(2, 1, height_ratios=[0.45, 1], hspace=0.06)
            axis = figure.add_subplot(sub[0])
            heat = figure.add_subplot(sub[1], sharex=axis)
            values = traces[:, c, r]
            mean = np.nanmean(values, axis=0)
            sem = np.nanstd(values, axis=0, ddof=1) / np.sqrt(np.isfinite(values).sum(axis=0))
            axis.fill_between(times_ms, mean - sem, mean + sem, color=CONDITION_COLORS[condition], alpha=0.19, linewidth=0)
            axis.plot(times_ms, mean, color=CONDITION_COLORS[condition], linewidth=1.0)
            axis.axvline(0.0, color="#737D88", linewidth=0.8, linestyle=":")
            axis.axhline(0.0, color="#8E969F", linewidth=0.6)
            axis.set_xlim(float(times_ms[0]), float(times_ms[-1]))
            axis.set_ylim(*limits)
            axis.set_xticks([0, 200, 400])
            style_axis(axis)
            axis.tick_params(axis="x", bottom=False, labelbottom=False)
            image = heat.pcolormesh(linear_edges(times_ms), np.arange(len(subjects) + 1), np.ma.masked_invalid(values),
                                    cmap=cmap, vmin=-limit, vmax=limit, shading="flat", rasterized=True,
                                    antialiased=False, linewidth=0)
            heat.set_ylim(len(subjects), 0)
            heat.set_yticks(np.arange(len(subjects)) + 0.5, [str(s).lstrip("0") for s in subjects], fontsize=6)
            heat.tick_params(axis="y", length=0)
            heat.axvline(0, color=INK, lw=0.5, alpha=0.65)
            for spine in heat.spines.values():
                spine.set_visible(False)
            if r < 2:
                heat.tick_params(labelbottom=False)
            if r == 0:
                axis.set_title(CONDITION_LABELS[condition], fontsize=10, pad=10)
            if c:
                axis.tick_params(labelleft=False)
                heat.tick_params(labelleft=False)
            else:
                axis.set_ylabel(r"$\mu$V", fontsize=7)
                heat.set_ylabel("Animal", fontsize=7)
                box = grid[r, 0].get_position(figure)
                figure.text(0.018, (box.y0 + box.y1) / 2, region, rotation=90, fontsize=10, weight="bold", va="center")
        box = grid[r, -1].get_position(figure)
        bar = figure.colorbar(image, cax=figure.add_axes([0.905, box.y0, 0.013, box.height * 0.66]), ticks=[-limit, 0, limit])
        bar.ax.set_yticklabels([f"{-limit:.1f}", "0", f"{limit:.1f}"])
        bar.ax.tick_params(labelsize=6, length=2)
        bar.ax.set_title(r"$\mu$V", fontsize=7, pad=5)
        bar.outline.set_visible(False)
    figure.text(0.5, 0.037, "Time from stimulation (ms)", ha="center", fontsize=8.5)
    save(figure, folder, "figS4_individual_waveforms")


# ----------------------------------------------------------------------------- scalar contrasts

def fig_power_ratios(contrasts: pd.DataFrame, folder) -> None:
    figure, (axis,) = forest_labels(1, height=5.0, top=0.925, bottom=0.17, label_width=0.25)
    for outcome, offset in (("total", 0.27), ("evoked", 0.0), ("induced", -0.27)):
        color = OUTCOME_COLORS[outcome]
        for row in contrasts.loc[contrasts.outcome == outcome].itertuples():
            y = ROW_LOOKUP[(row.region, row.contrast)] + offset
            axis.plot([10 ** row.wald_ci_low, 10 ** row.wald_ci_high], [y, y], color=color, linewidth=1.25)
            axis.scatter([10 ** row.estimate], [y], marker=OUTCOME_MARKERS[outcome], s=25, linewidth=1.0, zorder=5,
                         facecolor=color if row.p_holm < 0.05 else WHITE, edgecolor=color)
    axis.axvline(1.0, color="#4B535C", linewidth=0.85, linestyle=":")
    axis.set_xscale("log")
    axis.set_xlim(0.72, 2.40)
    axis.xaxis.set_major_locator(FixedLocator([0.75, 1.0, 1.25, 1.5, 2.0]))
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    axis.xaxis.set_minor_locator(FixedLocator([]))
    finish_forest(axis)
    axis.set_title("Intensity effects on total, evoked and induced power", loc="left", pad=9)
    axis.set_xlabel("Power at higher intensity / power at lower intensity", labelpad=8)
    handles = [Line2D([0], [0], color=OUTCOME_COLORS[o], marker=OUTCOME_MARKERS[o], markerfacecolor=WHITE,
                      linewidth=1.1, label=label) for o, label in (("total", "Total"), ("evoked", "Evoked"), ("induced", "Induced"))]
    handles.append(Line2D([0], [0], color=INK, marker="o", markerfacecolor=INK, linewidth=0,
                          label="Filled: survives Holm correction"))
    figure.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.50, 0.005), ncol=4, fontsize=7.5)
    save(figure, folder, "fig4_power_ratios")


def fig_aperiodic(contrasts: pd.DataFrame, folder) -> None:
    panels = (("aperiodic_exponent", "Aperiodic exponent", "Exponent difference"),
              ("aperiodic_offset", "Aperiodic offset", "Offset difference"),
              ("adjusted_power", "Adjusted 35-120 Hz", "Log10 power difference"))
    figure, axes = forest_labels(3, height=4.9, top=0.88, bottom=0.15, label_width=0.68)
    for p, (axis, (outcome, text, xlabel)) in enumerate(zip(axes, panels)):
        rows = contrasts.loc[contrasts.outcome == outcome]
        limit = max(0.005, 1.10 * float(np.nanmax(np.abs(rows[["wald_ci_low", "wald_ci_high"]].to_numpy()))))
        color = APERIODIC_COLORS[outcome]
        for row in rows.itertuples():
            y = ROW_LOOKUP[(row.region, row.contrast)]
            axis.plot([row.wald_ci_low, row.wald_ci_high], [y, y], color=color, linewidth=1.5, zorder=3)
            axis.scatter([row.estimate], [y], s=34, linewidth=1.0, zorder=4, edgecolor=color,
                         facecolor=color if row.p_holm < 0.05 else WHITE)
        axis.axvline(0.0, color="#4B535C", linewidth=0.8, linestyle=":", zorder=2)
        axis.set_xlim(-limit, limit)
        finish_forest(axis)
        title(axis, chr(65 + p), text)
        axis.set_xlabel(xlabel)
    holm_legend(figure, loc="lower center", bbox_to_anchor=(0.50, 0.0), fontsize=7.8)
    save(figure, folder, "fig6_aperiodic")


def fig_evoked_fraction(contrasts: pd.DataFrame, folder) -> None:
    rows = contrasts.loc[contrasts.outcome == "evoked_fraction"]
    limit = max(1.0, 1.10 * float(np.nanmax(np.abs(100 * rows[["wald_ci_low", "wald_ci_high"]].to_numpy()))))
    centers = np.asarray([2.0, 1.0, 0.0])
    figure, axes = plt.subplots(1, 3, figsize=(7.2, 2.85), sharex=True, sharey=True, layout="constrained")
    color = OUTCOME_COLORS["evoked"]
    for r, (axis, region) in enumerate(zip(axes, REGIONS)):
        regional = rows.loc[rows.region == region].set_index("contrast").reindex(CONTRASTS)
        for y, row in zip(centers, regional.itertuples()):
            axis.plot([100 * row.wald_ci_low, 100 * row.wald_ci_high], [y, y], color=color, linewidth=1.5)
            axis.scatter([100 * row.estimate], [y], s=36, linewidth=1.0, zorder=5, edgecolor=color,
                         facecolor=color if row.p_holm < 0.05 else WHITE)
        axis.axvline(0.0, color="#4B535C", linewidth=0.8, linestyle=":")
        axis.set_xlim(-limit, limit)
        axis.set_ylim(-0.5, 2.5)
        axis.set_yticks(centers, [CONTRAST_LABELS[c] for c in CONTRASTS])
        style_axis(axis, grid_axis="x")
        title(axis, chr(65 + r), region)
        if r:
            axis.tick_params(labelleft=False)
    figure.supxlabel("Evoked-fraction difference (percentage points)", fontsize=8.0)
    figure.legend(handles=[
        Line2D([0], [0], color=INK, marker="o", markerfacecolor=WHITE, linewidth=1.1, label="95% Wald CI"),
        Line2D([0], [0], color=INK, marker="o", markerfacecolor=INK, linewidth=0, label="Filled: Holm-adjusted P < 0.05"),
    ], loc="outside upper center", ncol=2, fontsize=7.0)
    save(figure, folder, "figS5_evoked_fraction")


# ----------------------------------------------------------------------------- maps

def effect_map(axis, effects, mask, times_ms, frequencies, limit):
    time_edges, frequency_edges = linear_edges(times_ms), log_edges(frequencies)
    image = axis.pcolormesh(time_edges, frequency_edges, np.ma.masked_invalid(effects), shading="flat",
                            cmap=EFFECT_CMAP, norm=TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit),
                            edgecolors="none", linewidth=0.0, antialiased=False, snap=True, rasterized=True)
    if mask.any():
        draw_outline(axis, time_edges, frequency_edges, mask)
    axis.axvline(0.0, color=MAP_CONTOUR, linewidth=0.65, linestyle=":", zorder=10)
    axis.set_xlim(0, 400)
    log_frequency_axis(axis, [20, 50, 100, 200], 200.0)
    style_axis(axis)
    return image


def colour_limit(effects) -> float:
    return max(0.01, float(np.ceil(float(np.nanmax(np.abs(effects))) * 100.0) / 100.0))


def fig_corrected_maps(family, folder) -> None:
    """The four maps with a corrected region, with the map's mean across time and across frequency."""
    effects, masks = family["effects"], family["tfce"]
    times_ms, frequencies = family["times_ms"], family["frequencies"]
    selections = [(c, r) for r in range(3) for c in range(3) if masks[c, r].any()]
    limit = colour_limit(effects)
    profiles = np.concatenate([effects.mean(axis=-1).ravel(), effects.mean(axis=-2).ravel()])
    low, high = min(0.0, float(profiles.min())), max(0.0, float(profiles.max()))
    pad = 0.07 * (high - low)
    figure = plt.figure(figsize=(7.2, 6.55))
    grid = figure.add_gridspec(2, 2, left=0.09, right=0.985, bottom=0.16, top=0.93, hspace=0.36, wspace=0.42)
    image = None
    for i, (c, r) in enumerate(selections):
        sub = grid[i // 2, i % 2].subgridspec(2, 2, width_ratios=[1, 0.29], height_ratios=[1, 0.31], wspace=0.10, hspace=0.14)
        axis = figure.add_subplot(sub[0, 0])
        time_axis = figure.add_subplot(sub[1, 0], sharex=axis)
        frequency_axis = figure.add_subplot(sub[0, 1], sharey=axis)
        image = effect_map(axis, effects[c, r], masks[c, r], times_ms, frequencies, limit)
        axis.set_xticks([0, 100, 200, 300, 400])
        axis.tick_params(axis="x", bottom=False, labelbottom=False)
        axis.set_ylabel("Frequency (Hz)", labelpad=4, fontsize=7.5)
        title(axis, chr(65 + i), f"{REGIONS[r]}   {CONTRAST_LABELS[CONTRASTS[c]]}")
        axis.title.set_fontsize(8.5)
        axis.tick_params(labelsize=7)
        across_frequency, across_time = effects[c, r].mean(axis=-2), effects[c, r].mean(axis=-1)
        time_axis.fill_between(times_ms, 0, across_frequency, color="#D7E6E8", lw=0)
        frequency_axis.fill_betweenx(frequencies, 0, across_time, color="#D7E6E8", lw=0)
        time_axis.plot(times_ms, across_frequency, color="#205B68", lw=1.1)
        frequency_axis.plot(across_time, frequencies, color="#205B68", lw=1.1)
        time_axis.set_ylim(low - pad, high + pad)
        frequency_axis.set_xlim(low - pad, high + pad)
        time_axis.set_yticks([0, 0.1])
        frequency_axis.set_xticks([0, 0.1], ["0", "0.1"])
        for profile, text in ((time_axis, "Across frequencies"), (frequency_axis, "Across time")):
            style_axis(profile)
            profile.tick_params(labelsize=6.5, length=2)
            profile.text(0.96, 0.94, text, transform=profile.transAxes, ha="right", va="top", fontsize=6.5,
                         color=MUTED, alpha=0.55, rotation=270 if profile is frequency_axis else 0)
        time_axis.spines["bottom"].set_position(("data", 0))
        frequency_axis.spines["left"].set_position(("data", 0))
        frequency_axis.spines["bottom"].set_position(("data", 20))
        time_axis.set_ylabel(r"Mean $\Delta$", fontsize=7, labelpad=2)
        frequency_axis.set_xlabel(r"Mean $\Delta$", fontsize=7, labelpad=3)
        time_axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: "" if value == 0 else f"{value:g}"))
        frequency_axis.tick_params(axis="y", left=False, labelleft=False)
        if i >= 2:
            time_axis.set_xlabel("Time from stimulation (ms)", fontsize=8, labelpad=5)
    bar = figure.colorbar(image, cax=figure.add_axes([0.21, 0.055, 0.58, 0.019]), orientation="horizontal",
                          ticks=np.linspace(-limit, limit, 5))
    bar.set_label("Mean difference in log10 power (higher minus lower intensity)", fontsize=8, labelpad=5)
    bar.outline.set_visible(False)
    figure.text(0.52, 0.985, "White outline: primary TFCE", ha="center", fontsize=8, va="top")
    save(figure, folder, "fig5_corrected_maps")


def fig_all_maps(family, folder) -> None:
    figure, axes = plt.subplots(3, 3, figsize=(7.2, 6.15), sharex=True, sharey=True, squeeze=False)
    figure.subplots_adjust(left=0.10, right=0.96, bottom=0.22, top=0.875, hspace=0.29, wspace=0.12)
    limit = colour_limit(family["effects"])
    time_edges, frequency_edges = linear_edges(family["times_ms"]), log_edges(family["frequencies"])
    image = None
    for i, (r, c) in enumerate((r, c) for r in range(3) for c in range(3)):
        axis = axes.flat[i]
        image = effect_map(axis, family["effects"][c, r], family["tfce"][c, r], family["times_ms"],
                           family["frequencies"], limit)
        axis.set_xticks([0, 200, 400])
        if family["maximum"][c, r].any():
            draw_outline(axis, time_edges, frequency_edges, family["maximum"][c, r], linewidth=0.7, linestyle=(0, (3, 2)))
    matrix_labels(figure, axes, [CONTRAST_LABELS[c] for c in CONTRASTS], ylabel="Hz")
    figure.text(0.53, 0.14, "Time from stimulation (ms)", ha="center", fontsize=8.5)
    bar = figure.colorbar(image, cax=figure.add_axes([0.22, 0.071, 0.62, 0.025]), orientation="horizontal",
                          ticks=np.linspace(-limit, limit, 5))
    bar.set_label("Mean difference in log10 power (higher minus lower intensity)", fontsize=8, labelpad=5)
    bar.ax.tick_params(labelsize=7.5, length=2)
    bar.outline.set_visible(False)
    figure.legend(handles=[Line2D([0], [0], color=INK, linewidth=1.15, label="Solid outline: TFCE"),
                           Line2D([0], [0], color=INK, linewidth=1.05, linestyle="--", label="Maximum-|t| sensitivity")],
                  loc="upper center", bbox_to_anchor=(0.53, 1.04), ncol=2, fontsize=8, handlelength=2.4)
    save(figure, folder, "figS3_all_maps")


def fig_fraction(data, folder, *, region_scales: bool) -> None:
    group = 100.0 * np.nanmean(data["fraction_maps"], axis=0)
    time_edges, frequency_edges = linear_edges(data["map_times"] * 1000), log_edges(data["scalar_frequencies"])

    def upper(values):
        return min(100.0, max(5.0, 5.0 * np.ceil(float(np.nanquantile(values, 0.995)) / 5.0)))

    figure, axes = plt.subplots(3, 3, figsize=(7.2, 5.05), sharex=True, sharey=True)
    figure.subplots_adjust(left=0.10, right=0.88 if region_scales else 0.97, bottom=0.20 if region_scales else 0.24,
                           top=0.875, hspace=0.30, wspace=0.12)
    image = None
    for r in range(3):
        top = upper(group[:, r]) if region_scales else upper(group)
        for c in range(3):
            axis = axes[r, c]
            image = axis.pcolormesh(time_edges, frequency_edges, group[c, r], shading="flat", cmap=FRACTION_CMAP,
                                    vmin=0.0, vmax=top, edgecolors="none", antialiased=False, snap=True, rasterized=True)
            axis.axhline(35.0, color=WHITE, linewidth=0.75, linestyle=(0, (4, 3)), alpha=0.8)
            axis.set_xlim(0.0, 400.0)
            axis.set_xticks([0, 200, 400])
            log_frequency_axis(axis, [20, 30, 40, 60, 90, 120], 120.0)
            style_axis(axis)
        if region_scales:
            box = axes[r, -1].get_position()
            bar = figure.colorbar(image, cax=figure.add_axes([0.905, box.y0, 0.012, box.height]), ticks=[0, top / 2, top])
            bar.ax.set_title("%", fontsize=8, pad=5)
            bar.ax.tick_params(labelsize=7.5, length=2)
            bar.outline.set_visible(False)
    if not region_scales:
        bar = figure.colorbar(image, cax=figure.add_axes([0.22, 0.075, 0.64, 0.025]), orientation="horizontal")
        bar.set_label("Phase-locked fraction of total power (%)", fontsize=8, labelpad=5)
        bar.ax.tick_params(labelsize=7.5, length=2)
        bar.outline.set_visible(False)
    matrix_labels(figure, axes, [CONDITION_LABELS[c] for c in CONDITIONS], ylabel="Hz")
    figure.text(0.53, 0.12 if region_scales else 0.16, "Time from stimulation (ms)", ha="center", fontsize=8.5)
    save(figure, folder, "figS2_fraction_region_scales" if region_scales else "figS1_fraction_common_scale")


# ----------------------------------------------------------------------------- spectra and correlations

def fig_spectra(data, folder) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(7.2, 6.1))
    figure.subplots_adjust(left=0.085, right=0.985, bottom=0.12, top=0.88, wspace=0.36)
    frequencies, observed = data["spectrum_frequencies"], data["spectrum_observed"]
    mean, background = np.nanmean(observed, axis=0), np.nanmean(data["spectrum_background"], axis=0)
    sem = np.nanstd(observed, axis=0, ddof=1) / np.sqrt(np.isfinite(observed).sum(axis=0))
    for r, (axis, region) in enumerate(zip(axes, REGIONS)):
        for c, condition in enumerate(CONDITIONS):
            color = CONDITION_COLORS[condition]
            axis.plot(frequencies, mean[c, r], color=color, lw=1.0)
            axis.fill_between(frequencies, mean[c, r] - sem[c, r], mean[c, r] + sem[c, r], color=color, alpha=0.15, lw=0)
            axis.plot(frequencies, background[c, r], color=color, lw=0.85, ls="--")
        for start, stop in ((48, 52), (98, 102)):
            axis.axvspan(start, stop, color="#E9E9E9", zorder=0, lw=0)
        axis.set_xscale("log")
        axis.set_xticks([20, 40, 80, 120], ["20", "40", "80", "120"])
        axis.minorticks_off()
        axis.set_xlim(20, 120)
        low = min(float(np.min(mean[:, r] - sem[:, r])), float(np.min(background[:, r])))
        high = max(float(np.max(mean[:, r] + sem[:, r])), float(np.max(background[:, r])))
        axis.set_ylim(low - 0.04 * (high - low), high + 0.04 * (high - low))
        axis.set_xlabel("Frequency (Hz)")
        if r == 0:
            axis.set_ylabel(r"Log10 PSD ($\mu$V$^2$/Hz)")
        axis.tick_params(labelsize=7.5)
        style_axis(axis)
        title(axis, chr(65 + r), region)
    handles = [Line2D([], [], color=CONDITION_COLORS[c], lw=1.4, label=CONDITION_LABELS[c]) for c in CONDITIONS]
    handles.append(Line2D([], [], color=INK, ls="--", lw=0.9, label="Fitted aperiodic background"))
    figure.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.52, 0.985), ncol=4, fontsize=7.5)
    save(figure, folder, "figS6_spectra")


def fig_correlations(correlations, folder) -> None:
    matrices, labels = correlations["spearman"], correlations["labels"]
    n = len(labels)
    figure, axes = plt.subplots(1, 2, figsize=(10.4, 5.2))
    figure.subplots_adjust(left=0.13, right=0.99, bottom=0.30, top=0.93, wspace=0.55)
    image = None
    for p, (axis, contrast) in enumerate(zip(axes, correlations["contrasts"])):
        image = axis.imshow(matrices[p], cmap="RdBu_r", vmin=-1, vmax=1, interpolation="nearest")
        axis.set_xticks(range(n), labels, rotation=55, ha="right", fontsize=7.5)
        axis.set_yticks(range(n), labels, fontsize=7.5)
        for edge in (6.5, 13.5):
            axis.axhline(edge, color=WHITE, lw=1.2)
            axis.axvline(edge, color=WHITE, lw=1.2)
        axis.tick_params(length=0)
        for spine in axis.spines.values():
            spine.set_visible(False)
        axis.set_title(rf"$\mathbf{{{chr(65 + p)}}}$   {CONTRAST_LABELS[str(contrast)]}", loc="left", pad=8)
    bar = figure.colorbar(image, cax=figure.add_axes([0.38, 0.07, 0.30, 0.022]), orientation="horizontal",
                          ticks=[-1, -0.5, 0, 0.5, 1])
    bar.set_label("Spearman correlation", fontsize=8.5)
    bar.ax.tick_params(labelsize=7.5)
    bar.outline.set_visible(False)
    save(figure, folder, "figS7_correlations")


# ----------------------------------------------------------------------------- all figures

def make_all(config: dict) -> None:
    configure()
    results, folder = config["paths"]["results"] / "primary", config["paths"]["figures"]
    contrasts = pd.read_csv(results / "contrasts.csv")
    with np.load(results / "figure_data.npz") as source:
        data = {k: source[k] for k in source.files}
    with np.load(results / "tfce_maps.npz") as tfce, np.load(results / "animal_maps.npz") as animals:
        family = {"effects": tfce["effect"], "tfce": tfce["mask"], "maximum": tfce["maximum_mask"],
                  "times_ms": animals["times"] * 1000, "frequencies": animals["frequencies"]}
    with np.load(results / "correlations.npz") as source:
        correlations = {k: source[k] for k in source.files}
    fig_waveforms(data, folder)
    fig_power_ratios(contrasts, folder)
    fig_corrected_maps(family, folder)
    fig_aperiodic(contrasts, folder)
    fig_fraction(data, folder, region_scales=False)
    fig_fraction(data, folder, region_scales=True)
    fig_all_maps(family, folder)
    fig_individual_waveforms(data, folder)
    fig_evoked_fraction(contrasts, folder)
    fig_spectra(data, folder)
    fig_correlations(correlations, folder)
