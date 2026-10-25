"""LaTeX versions of the supplementary tables (the CSV files in results/ hold the same numbers)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import label

from . import config as cfg

TITLES = {"total": "Total power", "evoked": "Evoked power", "induced": "Induced power",
          "evoked_fraction": "Evoked fraction", "aperiodic_exponent": "Aperiodic exponent",
          "aperiodic_offset": "Aperiodic offset", "adjusted_power": "Aperiodic-adjusted power"}


def p_text(value: float) -> str:
    return f"{value:.4f}" if value >= 0.0001 else f"{value:.2g}"


def contrast_tex(contrast: str) -> str:
    return contrast.replace("x", r"$\times$").replace("-", "--")


def contrast_table(frame: pd.DataFrame, outcomes: list[str]) -> str:
    primary = outcomes == ["total"]
    extra = " & Animal bootstrap CI" if primary else ""
    header = r"Region & Contrast & Estimate & 95\% Wald CI" + extra + r" & Raw $P$ & Holm $P$ \\"
    columns = "llrrrrr" if primary else "llrrrr"
    lines = [r"\begin{longtable}{" + columns + "}", r"\toprule", header, r"\midrule", r"\endfirsthead",
             r"\toprule", header, r"\midrule", r"\endhead"]
    for outcome in outcomes:
        lines.append(r"\multicolumn{" + str(len(columns)) + r"}{l}{\textbf{" + TITLES[outcome] + r"}} \\")
        for row in frame[frame.outcome == outcome].itertuples():
            extra = f" & [{row.bootstrap_ci_low:.4f}, {row.bootstrap_ci_high:.4f}]" if primary else ""
            lines.append(f"{row.region} & {contrast_tex(row.contrast)} & {row.estimate:.4f} & "
                         f"[{row.wald_ci_low:.4f}, {row.wald_ci_high:.4f}]{extra} & {p_text(row.p_value)} & "
                         f"{p_text(row.p_holm)} " + r"\\")
        lines.append(r"\addlinespace")
    return "\n".join(lines + [r"\bottomrule", r"\end{longtable}", ""])


def map_table(tests: pd.DataFrame, config: dict) -> str:
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Region & Contrast & TFCE corrected $P$ & TFCE bins & Maximum-$|t|$ corrected $P$ & Maximum-$|t|$ bins \\",
             r"\midrule"]
    order = [(r, c[0]) for r in config["design"]["regions"] for c in config["design"]["contrasts"]]
    for row in tests.set_index(["region", "contrast"]).loc[order].reset_index().itertuples():
        lines.append(f"{row.region} & {contrast_tex(row.contrast)} & {row.tfce_p:.4f} & {row.tfce_bins} & "
                     f"{row.maximum_p:.4f} & {row.maximum_bins} \\\\")
    return "\n".join(lines + [r"\bottomrule", r"\end{tabular}", ""])


def map_components(folder: Path, config: dict) -> pd.DataFrame:
    """Each connected corrected region: its size, sampled frequency span, time span and mean effect."""
    with np.load(folder / "tfce_maps.npz") as tfce, np.load(folder / "animal_maps.npz") as animals:
        masks = {"tfce": tfce["mask"], "maximum": tfce["maximum_mask"]}
        effects, frequencies, times_ms = tfce["effect"], animals["frequencies"], animals["times"] * 1000
    rows = []
    for method, mask_family in masks.items():
        for ri, region in enumerate(config["design"]["regions"]):
            for ci, (contrast, _, _) in enumerate(config["design"]["contrasts"]):
                labelled, count = label(mask_family[ci, ri])
                for component in range(1, count + 1):
                    mask = labelled == component
                    f, t = np.where(mask)
                    rows.append({"method": method, "region": region, "contrast": contrast, "component": component,
                                 "bins": int(mask.sum()), "frequency_low": frequencies[f].min(),
                                 "frequency_high": frequencies[f].max(), "time_low_ms": times_ms[t].min() - 5,
                                 "time_high_ms": times_ms[t].max() + 5, "mean_effect": effects[ci, ri][mask].mean()})
    return pd.DataFrame(rows)


def components_table(components: pd.DataFrame) -> str:
    lines = [r"\begin{tabular}{lllrrrrr}", r"\toprule",
             r"Method & Region & Contrast & Part & Bins & Frequency (Hz) & Time (ms) & Mean effect \\", r"\midrule"]
    for row in components.itertuples():
        method = "TFCE" if row.method == "tfce" else r"Max-$|t|$"
        lines.append(f"{method} & {row.region} & {contrast_tex(row.contrast)} & {row.component} & {row.bins} & "
                     f"{row.frequency_low:.1f}--{row.frequency_high:.1f} & {row.time_low_ms:.0f}--{row.time_high_ms:.0f} & "
                     f"{row.mean_effect:.4f} " + r"\\")
    return "\n".join(lines + [r"\bottomrule", r"\end{tabular}", ""])


def sensitivity_table(results: Path, config: dict) -> tuple[pd.DataFrame, str]:
    keys = ["outcome", "region", "contrast"]
    merged = None
    for name in cfg.variants(config):
        frame = pd.read_csv(results / name / "contrasts.csv")[keys + ["p_holm"]].rename(columns={"p_holm": name})
        merged = frame if merged is None else merged.merge(frame, on=keys, validate="one_to_one")
    lines = [r"\begin{longtable}{llrrrr}", r"\toprule",
             r"Region & Contrast & Accepted & Stored & Accepted, ACC 18 & Stored, ACC 18 \\",
             r"\midrule", r"\endhead"]
    names = list(cfg.variants(config))
    for outcome, title in TITLES.items():
        lines.append(r"\multicolumn{6}{l}{\textbf{" + title + r"}} \\*")
        rows = merged[merged.outcome == outcome]
        for index, row in enumerate(rows.itertuples(index=False)):
            values = " & ".join(p_text(getattr(row, n)) for n in (names[0], names[1], names[2], names[3]))
            lines.append(f"{row.region} & {contrast_tex(row.contrast)} & {values} " + (r"\\*" if index < 8 else r"\\"))
        lines.append(r"\addlinespace")
    return merged, "\n".join(lines + [r"\bottomrule", r"\end{longtable}", ""])


def write_all(results: Path, config: dict) -> None:
    out = results / "tables"
    out.mkdir(exist_ok=True)
    primary = pd.read_csv(results / "primary" / "contrasts.csv")
    for filename, outcomes in (("tableS1_total_power.tex", ["total"]),
                               ("tableS2_evoked_induced.tex", ["evoked", "induced", "evoked_fraction"]),
                               ("tableS3_aperiodic.tex", ["aperiodic_exponent", "aperiodic_offset", "adjusted_power"])):
        (out / filename).write_text(contrast_table(primary, outcomes), encoding="utf-8")
    (out / "tableS4_corrected_maps.tex").write_text(
        map_table(pd.read_csv(results / "primary" / "map_tests.csv"), config), encoding="utf-8")
    components = map_components(results / "primary", config)
    components.to_csv(out / "tableS5_map_components.csv", index=False)
    (out / "tableS5_map_components.tex").write_text(components_table(components), encoding="utf-8")
    merged, text = sensitivity_table(results, config)
    merged.to_csv(out / "tableS6_sensitivity.csv", index=False)
    (out / "tableS6_sensitivity.tex").write_text(text, encoding="utf-8")
