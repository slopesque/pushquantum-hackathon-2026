"""CLI des runs H1 (boucle FMQA, SA ou PCE).

Exemple ::

    PYTHONPATH=src/network-experiments uv run python -m h1.run \
        --instance network12 --seed 0 1 2 --method h1_sa_fm
"""

from __future__ import annotations

import argparse
from typing import Any

from h0.harness import run_method, save_solution

from .loop import h1_fm

METHODS = ("h1_sa_fm", "h1_pce_fm")


def build_params(args: argparse.Namespace) -> dict[str, Any]:
    """Paramètres (JSON-sérialisables) passés à ``h1_fm`` et enregistrés dans le JSONL."""
    params: dict[str, Any] = {
        "rank": args.rank,
        "lam": args.lam,
        "target": args.target,
        "n0_frac": args.n0_frac,
        "sa_reads": args.sa_reads,
        "epochs_init": args.epochs_init,
        "epochs_round": args.epochs_round,
        "lr": args.lr,
        "l2": args.l2,
        "quantum": None,
        "quantum_rounds": "none",
        "diag_instance": args.instance,
    }
    if args.method == "h1_pce_fm":
        params["quantum"] = {
            "use_cloud": args.cloud,
            "encoding": args.pce_encoding,
            "n_layers": args.pce_layers,
            "population": args.pce_population,
            "iterations": args.pce_iterations,
            "top_n": args.pce_top_n,
        }
        params["quantum_rounds"] = args.quantum_rounds
    return params


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="h1.run", description=__doc__.splitlines()[0])
    p.add_argument("--instance", required=True)
    p.add_argument("--seed", type=int, nargs="+", default=[0])
    p.add_argument("--method", choices=METHODS, default="h1_sa_fm")
    p.add_argument("--rank", type=int, default=8)
    p.add_argument("--lam", type=float, default=1.0)
    p.add_argument("--target", default="rank")
    p.add_argument("--n0-frac", type=float, default=0.2)
    p.add_argument("--sa-reads", type=int, default=100)
    p.add_argument("--epochs-init", type=int, default=300)
    p.add_argument("--epochs-round", type=int, default=50)
    p.add_argument("--lr", type=float, default=0.01)
    p.add_argument("--l2", type=float, default=1e-4)
    p.add_argument("--quantum-rounds", default="every:5")
    p.add_argument("--pce-population", type=int, default=20)
    p.add_argument("--pce-iterations", type=int, default=5)
    p.add_argument("--pce-layers", type=int, default=2)
    p.add_argument("--pce-encoding", default="poly")
    p.add_argument("--pce-top-n", type=int, default=100)
    p.add_argument("--cloud", action="store_true", help="PCE sur le cloud Qoro (crédits !)")
    p.add_argument("--max-lp-calls", type=int, default=None, help="essai : remplace le budget")
    p.add_argument("--time-limit", type=float, default=None, help="essai : remplace le plafond")
    p.add_argument("--no-write", action="store_true", help="ne pas écrire la ligne JSONL")
    p.add_argument("--save-sol", action="store_true", help="save_run du .sol (vérifié arbitre)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    args = parse_args(argv)
    params = build_params(args)
    records = []
    for seed in args.seed:
        rec = run_method(
            "h1",
            args.method,
            h1_fm,
            args.instance,
            seed,
            params=params,
            max_lp_calls=args.max_lp_calls,
            time_limit_s=args.time_limit,
            write=not args.no_write,
        )
        gap = rec["gap"]
        print(
            f"{args.method} {args.instance} seed={seed} score={rec['score']} "
            f"best_known={rec['best_known']} gap={'—' if gap is None else f'{gap:+.2%}'} "
            f"lp={rec['lp_calls']} t={rec['wall_time_s']}s rounds={rec.get('n_rounds')} "
            f"q_rounds={rec.get('n_quantum_rounds')} explore={rec.get('n_explore')} "
            f"E1={_fmt(rec.get('feasible_mass'))} rho={_fmt(rec.get('spearman_rho'))} "
            f"rho_kit={_fmt(rec.get('spearman_rho_kit'))}",
            flush=True,
        )
        if args.save_sol and rec["best_arcs"]:
            print(f"  .sol → {save_solution(rec)}")
        records.append(rec)
    return records


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


if __name__ == "__main__":
    main()
