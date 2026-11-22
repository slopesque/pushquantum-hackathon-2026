"""CLI des runs H4 (QAOA Dicke-XY, QAOA à pénalités, boucle par blocs de lignes).

Exemple ::

    PYTHONPATH=src/network-experiments uv run python -m h4.run \
        --instance network05 --seed 0 1 2 --method h4_qaoa_dicke --time-limit 1200

Attention : le plafond de temps du harnais inclut la simulation QAOA. Sur network05 (120 s), un
QAOA p=2, population 20, 10 itérations (201 circuits de 20 qubits) prend ~260 s en local : sans
``--time-limit`` plus large, aucun LP n'est résolu (score ``None``).
"""

from __future__ import annotations

import argparse
from typing import Any

from h0.harness import run_method, save_solution

from .methods import h4_qaoa_dicke, h4_qaoa_penalty, h4_rows_q, h4_rows_sa

METHODS = {
    "h4_qaoa_dicke": h4_qaoa_dicke,
    "h4_qaoa_penalty": h4_qaoa_penalty,
    "h4_rows_q": h4_rows_q,
    "h4_rows_sa": h4_rows_sa,
}


def build_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {"lam": args.lam, "top_k": args.top_k}
    if args.method == "h4_rows_sa":
        params |= {"rows_per_block": args.rows_per_block, "sa_reads": args.sa_reads}
    else:
        params |= {
            "layers": args.layers,
            "population": args.population,
            "iterations": args.iterations,
            "shots": args.shots,
            "use_cloud": args.cloud,
            "mps_bond_dim": args.mps_bond_dim,
        }
        if args.method == "h4_rows_q":
            params["rows_per_block"] = args.rows_per_block
    if args.max_sweeps is not None and args.method.startswith("h4_rows"):
        params["max_sweeps"] = args.max_sweeps
    return params


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="h4.run", description=__doc__.splitlines()[0])
    p.add_argument("--instance", required=True)
    p.add_argument("--seed", type=int, nargs="+", default=[0])
    p.add_argument("--method", choices=tuple(METHODS), default="h4_qaoa_dicke")
    p.add_argument("--layers", type=int, default=2)
    p.add_argument("--population", type=int, default=20)
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--shots", type=int, default=10_000)
    p.add_argument("--lam", type=float, default=1.0)
    p.add_argument("--rows-per-block", type=int, default=2)
    p.add_argument("--top-k", type=int, default=100)
    p.add_argument("--sa-reads", type=int, default=100, help="h4_rows_sa : lectures SA par bloc")
    p.add_argument("--max-sweeps", type=int, default=None, help="h4_rows_* : plafond de balayages")
    p.add_argument("--cloud", action="store_true", help="QAOA sur le cloud Qoro (crédits !)")
    p.add_argument("--mps-bond-dim", type=int, default=None, help="cloud : simulation MPS")
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
            "h4",
            args.method,
            METHODS[args.method],
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
            f"lp={rec['lp_calls']} t={rec['wall_time_s']}s circuits={rec['n_circuits']} "
            f"qubits={rec['max_qubits']} E1={_fmt(rec.get('feasible_mass'))} "
            f"outdeg={_fmt(rec.get('outdeg_mass'))} p_opt={_fmt(rec.get('p_opt'))} "
            f"rank_best={rec.get('rank_best')} sweeps={rec.get('n_sweeps')}",
            flush=True,
        )
        if args.save_sol and rec["best_arcs"]:
            print(f"  .sol → {save_solution(rec)}")
        records.append(rec)
    return records


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.4f}"


if __name__ == "__main__":
    main()
