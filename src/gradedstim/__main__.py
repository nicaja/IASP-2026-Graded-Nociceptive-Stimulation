"""Command line: python -m gradedstim {features,statistics,figures,page,all}."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

from . import config as cfg


def main() -> None:
    parser = argparse.ArgumentParser(prog="gradedstim", description=__doc__)
    parser.add_argument("stage", choices=("features", "statistics", "figures", "page", "all"))
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--epochs", type=Path, help="override paths.epochs in the config")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    config = cfg.load(args.config)
    if args.epochs:
        config["paths"]["epochs"] = args.epochs.resolve()
    if args.stage in ("features", "all"):
        from .features import extract_all
        extract_all(config, args.config.resolve(), args.workers)
    if args.stage in ("statistics", "all"):
        from .pipeline import statistics
        statistics(config, args.workers)
    if args.stage in ("figures", "all"):
        from .figures import make_all
        make_all(config)
    if args.stage in ("page", "all"):
        from .page import make
        make(config)


if __name__ == "__main__":
    main()
