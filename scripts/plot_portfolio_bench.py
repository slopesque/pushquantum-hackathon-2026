"""Retrace les graphes d'un ou plusieurs benchmarks, par exemple pour comparer deux runs (piste P3).

Exemples ::

    # Retracer un run
    uv run scripts/plot_portfolio_bench.py results/portfolio/bench/20261121T170000Z_dev

    # Comparer deux runs dans les mêmes graphes
    uv run scripts/plot_portfolio_bench.py results/portfolio/bench/*_baseline results/portfolio/bench/*_p4 \\
        --out results/portfolio/bench/compare_baseline_p4 --label "baseline vs P4"

Quand deux runs contiennent une méthode du même nom, elle est renommée ``méthode (dossier)`` pour que
les deux restent distinctes. Seuls les cas présents dans tous les runs sont gardés avec ``--common``.

Avec ``--all``, tous les runs de ``results/portfolio/bench/`` sont réunis : une méthode garde le même nom
(donc la même couleur et le même symbole) quel que soit le run, et si un même cas a été exécuté plusieurs
fois (même instance, λ, méthode et seed), seule l'exécution la plus récente est gardée ::

    uv run scripts/plot_portfolio_bench.py --all
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from hackathon.solvers.portfolio.benchmark import Run, read_csv
from hackathon.solvers.portfolio.plots import METRICS, plot_all, plot_size_vs_metric
from hackathon.utils import RESULTS_DIR

BENCH_DIR = RESULTS_DIR / "portfolio" / "bench"


def load_all() -> list[Run]:
    """Tous les runs de ``BENCH_DIR``, sans renommage ; la dernière exécution de chaque cas l'emporte."""
    latest: dict[tuple, Run] = {}
    for csv_path in sorted(BENCH_DIR.glob("*/runs.csv")):  # noms horodatés : ordre chronologique
        for r in read_csv(csv_path):
            latest[r.instance, r.lam, r.method, r.seed] = r
    return list(latest.values())


def load(dirs: list[Path]) -> list[Run]:
    per_dir = [(d, read_csv(d / "runs.csv")) for d in dirs]
    counts: dict[str, int] = {}
    for _, runs in per_dir:
        for m in {r.method for r in runs}:
            counts[m] = counts.get(m, 0) + 1
    merged = []
    for d, runs in per_dir:
        tag = d.name.split("_", 1)[-1]
        merged += [
            replace(r, method=f"{r.method} ({tag})") if counts[r.method] > 1 else r for r in runs
        ]
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("dirs", nargs="*", type=Path, help="dossiers de benchmark (avec runs.csv)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="réunir tous les runs de results/portfolio/bench/ (graphes taille × temps / gap)",
    )
    parser.add_argument("--out", type=Path, help="dossier de sortie")
    parser.add_argument("--label", default="", help="sous-titre des graphes")
    parser.add_argument(
        "--common", action="store_true", help="ne garder que les cas communs à tous"
    )
    args = parser.parse_args()

    if args.all:
        if args.dirs:
            parser.error("--all et une liste de dossiers sont incompatibles")
        out = args.out or BENCH_DIR / "all"
        out.mkdir(parents=True, exist_ok=True)
        runs = load_all()
        label = args.label or "tous les runs"
        paths = [plot_size_vs_metric(runs, out / f"size_vs_{m}.png", m, label) for m in METRICS]
    else:
        if not args.dirs:
            parser.error("donner au moins un dossier, ou --all")
        if args.out is None:
            if len(args.dirs) != 1:
                parser.error("--out est obligatoire pour comparer plusieurs runs")
            args.out = args.dirs[0]
        runs = load(args.dirs)
        if args.common:
            per_dir = [{r.case for r in read_csv(d / "runs.csv")} for d in args.dirs]
            common = set.intersection(*per_dir)
            runs = [r for r in runs if r.case in common]
        paths = plot_all(runs, args.out, args.label or args.out.name)
    for p in paths:
        print(f"graphe : {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
