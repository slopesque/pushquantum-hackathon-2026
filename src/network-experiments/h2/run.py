"""CLI des runs H2 (substitut analytique enrichi).

Exemple ::

    PYTHONPATH=src/network-experiments uv run python -m h2.run \
        --instance network12 --seed 0 1 2 --method h2_sa_phys --beta2 0.5

``--beta`` = poids de l'a priori dans la boucle H1 (``h2_fm_phys``) ; ``--beta2`` = poids des
chemins à 2 sauts du substitut H2.
"""

from __future__ import annotations

import argparse
from typing import Any

from h0.harness import run_method, save_solution

from .methods import METHODS


def build_params(args: argparse.Namespace) -> dict[str, Any]:
    """Paramètres (JSON-sérialisables) passés à la méthode et enregistrés dans le JSONL."""
    params: dict[str, Any] = {"alpha": args.alpha, "beta2": args.beta2, "gamma": args.gamma}
    if args.method == "h2_sa_phys":
        params |= {"lam": args.lam, "lam_rule": args.lam_rule, "sa_reads": args.sa_reads}
    else:
        if args.lam_rule is not None:
            raise SystemExit("--lam-rule n'est pris en charge que par h2_sa_phys")
        params |= {
            "rank": args.rank,
            "lam": args.lam,
            "beta": args.beta,
            "target": args.target,
            "n0_frac": args.n0_frac,
            "sa_reads": args.sa_reads,
            "epochs_init": args.epochs_init,
            "epochs_round": args.epochs_round,
            "lr": args.lr,
            "l2": args.l2,
            "diag_instance": args.instance,
        }
    return params


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="h2.run", description=__doc__.splitlines()[0])
    p.add_argument("--instance", required=True)
    p.add_argument("--seed", type=int, nargs="+", default=[0])
    p.add_argument("--method", choices=tuple(METHODS), default="h2_sa_phys")
    p.add_argument("--alpha", type=float, default=1.0)
    p.add_argument("--beta2", type=float, default=0.5, help="poids des chemins à 2 sauts")
    p.add_argument("--gamma", type=float, default=0.0, help="équilibrage de charge")
    p.add_argument("--lam", type=float, default=1.0)
    p.add_argument("--lam-rule", choices=("unit", "ayodele", "broesamle", "vlm", "momc"))
    p.add_argument("--sa-reads", type=int, default=100)
    # Options FM (h2_fm_phys), mêmes défauts que le réglage H1 retenu.
    p.add_argument("--rank", type=int, default=8)
    p.add_argument("--beta", type=float, default=0.5, help="poids de l'a priori H2 (boucle H1)")
    p.add_argument("--lr", type=float, default=0.003)
    p.add_argument("--l2", type=float, default=1e-2)
    p.add_argument("--target", default="rank")
    p.add_argument("--n0-frac", type=float, default=0.2)
    p.add_argument("--epochs-init", type=int, default=300)
    p.add_argument("--epochs-round", type=int, default=50)
    p.add_argument("--max-lp-calls", type=int, default=None, help="essai : remplace le budget")
    p.add_argument("--time-limit", type=float, default=None, help="remplace le plafond de temps")
    p.add_argument("--no-write", action="store_true", help="ne pas écrire la ligne JSONL")
    p.add_argument("--save-sol", action="store_true", help="save_run du .sol (vérifié arbitre)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    args = parse_args(argv)
    params = build_params(args)
    records = []
    for seed in args.seed:
        rec = run_method(
            "h2",
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
            f"lp={rec['lp_calls']} t={rec['wall_time_s']}s "
            f"lam={rec['params'].get('lam_effective', rec['params'].get('lam'))} "
            f"E1={_fmt(rec.get('feasible_mass'))} rho={_fmt(rec.get('spearman_rho'))}",
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
