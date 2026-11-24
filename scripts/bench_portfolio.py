"""Lance un benchmark de méthodes sur le problème de portefeuille (piste P3).

Exemples ::

    uv run scripts/bench_portfolio.py --set dev --methods empty
    uv run scripts/bench_portfolio.py --set known --methods ls ls-pairs --seeds 5 --time 30 --label p4
    uv run scripts/bench_portfolio.py --set a400 --methods ls-pairs --save-sol

Sorties dans ``results/portfolio/bench/<date>_<label>/`` :

* ``runs.csv``     une ligne par exécution (cas, méthode, seed, score, gap, temps) ;
* ``summary.md``   tableau par cas et par méthode (meilleur, médiane, gap) ;
* ``meta.json``    arguments, commit git, durée totale ;
* ``*.png``        les graphes (voir ``hackathon.solvers.portfolio.plots``).

Avec ``--save-sol``, la meilleure solution de chaque cas est validée par l'arbitre officiel (seul usage
de l'arbitre ici), puis enregistrée dans ``results/portfolio/`` avec ``save_run``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore", category=SyntaxWarning)  # docstrings bruyantes de dépendances

from hackathon.solvers.portfolio.benchmark import (
    METHODS,
    SETS,
    Case,
    Run,
    summarize,
    write_csv,
)
from hackathon.solvers.portfolio.benchmark import run_benchmark as _run
from hackathon.solvers.portfolio.plots import plot_all
from hackathon.solvers.portfolio.problem import PortfolioProblem
from hackathon.utils import RESULTS_DIR, git_hash, save_run

BENCH_DIR = RESULTS_DIR / "portfolio" / "bench"


def fmt_gap(g: float | None) -> str:
    return "—" if g is None else f"{100 * g:+.2f} %"


def summary_markdown(runs: list[Run]) -> str:
    lines = [
        (
            "| Cas | Variables (entier / QUBO) | Méthode | Meilleur | Médiane | Meilleur connu "
            "| Gap (meilleur) | Gap (médiane) | Faisables | Temps moyen |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in summarize(runs):
        bkv = "—" if s.best_known is None else str(s.best_known)
        lines.append(
            f"| {s.case.label} | {s.case.n_vars_int} / {s.case.n_vars_qubo} | {s.method} "
            f"| {s.best if s.best is not None else '—'} "
            f"| {s.median if s.median is not None else '—'} | {bkv} "
            f"| {fmt_gap(s.gap_best)} | {fmt_gap(s.gap_median)} "
            f"| {s.n_feasible}/{s.n_runs} | {s.time_mean:.2f} s |"
        )
    return "\n".join(lines) + "\n"


def validate_and_save(
    case: Case, problem: PortfolioProblem, v: np.ndarray, run: Run, args, out_dir: Path
) -> None:
    """Valide la solution avec l'arbitre officiel, puis l'enregistre avec ``save_run``."""
    from hackathon.referee import qt

    text = problem.solution_text(v, comment=f"{run.method} seed={run.seed} ({out_dir.name})")
    tmp = out_dir / problem.solution_filename
    tmp.write_text(text)
    header, positions = qt.read_portfolio_solution(tmp)
    model = qt.PortfolioModel(
        qt.load_portfolio_instance(header["instance"]),
        budget=int(header["budget"]),
        lam=header["lambda"],
    )
    official = model.score(positions)
    if not official.feasible or official.objective != run.objective:
        raise RuntimeError(
            f"{case.label} : l'arbitre ne confirme pas la solution "
            f"(notre score {run.objective}, arbitre {official})"
        )
    saved = save_run(
        "portfolio",
        problem.solution_filename,
        text,
        {
            "instance": case.instance,
            "budget": case.budget,
            "lambda": case.lam,
            "n_vars": case.n_vars_qubo,
            "n_vars_int": case.n_vars_int,
            "max_qubits": 0,  # méthodes classiques pour l'instant
            "score": run.objective,
            "best_known": run.best_known,
            "method": run.method,
            "params": {"time_limit": args.time},
            "seed": run.seed,
            "bench_dir": str(out_dir.relative_to(RESULTS_DIR.parent)),
        },
    )
    tmp.unlink()
    print(f"    validé par l'arbitre et enregistré : {saved.relative_to(RESULTS_DIR.parent)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--set", default="dev", choices=sorted(SETS), help="jeu de cas (défaut : dev)"
    )
    parser.add_argument(
        "--methods", nargs="+", default=["empty"], help=f"méthodes parmi {sorted(METHODS)}"
    )
    parser.add_argument("--seeds", type=int, default=3, help="nombre de seeds par cas (défaut : 3)")
    parser.add_argument(
        "--time", type=float, default=10.0, help="limite de temps par exécution, en s (défaut : 10)"
    )
    parser.add_argument("--label", default="", help="nom du run (dossier et titre des graphes)")
    parser.add_argument(
        "--save-sol",
        action="store_true",
        help="valider avec l'arbitre et enregistrer la meilleure solution de chaque cas",
    )
    parser.add_argument("--no-plot", action="store_true", help="ne pas produire les graphes")
    args = parser.parse_args()

    label = args.label or "-".join(args.methods) + f"_{args.set}"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = BENCH_DIR / f"{stamp}_{label}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = SETS[args.set]
    print(
        f"{len(cases)} cas × {len(args.methods)} méthode(s) × {args.seeds} seed(s), "
        f"limite {args.time:g} s → {out_dir.relative_to(RESULTS_DIR.parent)}"
    )

    best: dict[Case, tuple[int, PortfolioProblem, np.ndarray, Run]] = {}

    def on_run(run: Run, problem: PortfolioProblem, v: np.ndarray) -> None:
        flag = "" if run.feasible else "  INFAISABLE"
        print(
            f"  {run.case.label:<28} {run.method:<14} seed {run.seed}  {run.objective:>10}  "
            f"gap {fmt_gap(run.gap):>10}  {run.time_s:7.2f} s{flag}"
        )
        if run.feasible and (run.case not in best or run.objective < best[run.case][0]):
            best[run.case] = (run.objective, problem, v.copy(), run)

    start = time.perf_counter()
    runs = _run(cases, args.methods, range(args.seeds), args.time, on_run=on_run)
    total = time.perf_counter() - start

    write_csv(runs, out_dir / "runs.csv")
    summary = summary_markdown(runs)
    (out_dir / "summary.md").write_text(summary)
    meta = {
        "set": args.set,
        "methods": args.methods,
        "seeds": args.seeds,
        "time_limit": args.time,
        "label": label,
        "git": git_hash(),
        "timestamp": stamp,
        "total_time_s": round(total, 2),
        "n_runs": len(runs),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print("\n" + summary)

    if not args.no_plot:
        for p in plot_all(runs, out_dir, label):
            print(f"graphe : {p.relative_to(RESULTS_DIR.parent)}")

    if args.save_sol:
        print("\nValidation par l'arbitre et sauvegarde des meilleures solutions :")
        for case, (_, problem, v, run) in best.items():
            validate_and_save(case, problem, v, run, args, out_dir)

    n_bad = sum(not r.feasible for r in runs)
    if n_bad:
        print(f"\nATTENTION : {n_bad} exécution(s) infaisable(s)")
    print(f"\nTerminé en {total:.1f} s.")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
