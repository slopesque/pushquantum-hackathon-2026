"""Réglage sans LP du substitut H2 : grille (α, β₂, γ) → F1, F2 (network12, jeu de test) et F3
(network05, 216 topologies énumérées ; seul LP : le cache ``network05_all.json``, une fois).

    PYTHONPATH=src/network-experiments uv run python -m h2.tune --grid
"""

from __future__ import annotations

import argparse

from h0.instances import load_demand
from h1.diagnostics import kit_objective

from .diagnostics import f1_f2_testset, f3_ref_percentile
from .surrogate import lambda_rule, physics_objective

DEFAULT_BETA2 = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)
DEFAULT_GAMMA = (0.0, 0.5)


def evaluate(objective_12, objective_05, instance: str = "network12") -> dict:
    f12 = f1_f2_testset(objective_12, instance)
    f3 = f3_ref_percentile(objective_05, 5)
    return {
        "F1": f12["spearman_rho"],
        "F2": f12["top10_precision"],
        "F3": f3["percentile"],
        "F3_ties": f3["n_ties"],
        "rho05": f3["spearman_rho"],
        "lam_ayodele": lambda_rule(objective_12, "ayodele"),
        "lam_broesamle": lambda_rule(objective_12, "broesamle"),
    }


def grid(alphas, betas, gammas, instance: str = "network12") -> list[dict]:
    d12, d05 = load_demand(instance), load_demand("network05")
    rows = [{"alpha": "kit", "beta2": "", "gamma": ""} | evaluate(
        kit_objective(d12), kit_objective(d05), instance
    )]  # fmt: skip
    for a in alphas:
        for g in gammas:
            for b in betas:
                obj12 = physics_objective(d12, a, b, g)
                obj05 = physics_objective(d05, a, b, g)
                rows.append({"alpha": a, "beta2": b, "gamma": g} | evaluate(obj12, obj05, instance))
    return rows


def print_table(rows: list[dict]) -> None:
    head = (
        f"{'alpha':>5} {'beta2':>5} {'gamma':>5} | {'F1 rho':>7} {'F2 top10':>8} | "
        f"{'F3 pct':>6} {'ties':>4} {'rho05':>6} | {'lam_ayo':>7} {'lam_broe':>8}"
    )
    print(head)
    print("-" * len(head))
    for r in rows:
        print(
            f"{r['alpha']!s:>5} {r['beta2']!s:>5} {r['gamma']!s:>5} | {r['F1']:7.3f} "
            f"{r['F2']:8.3f} | {r['F3']:6.1f} {r['F3_ties']:4d} {r['rho05']:6.3f} | "
            f"{r['lam_ayodele']:7.3f} {r['lam_broesamle']:8.1f}"
        )


def main(argv: list[str] | None = None) -> list[dict]:
    p = argparse.ArgumentParser(prog="h2.tune", description=__doc__.splitlines()[0])
    p.add_argument("--grid", action="store_true", help="grille par défaut")
    p.add_argument("--instance", default="network12", help="jeu de test F1/F2")
    p.add_argument("--alpha", type=float, nargs="+", default=[1.0])
    p.add_argument("--beta2", type=float, nargs="+", default=list(DEFAULT_BETA2))
    p.add_argument("--gamma", type=float, nargs="+", default=list(DEFAULT_GAMMA))
    args = p.parse_args(argv)
    rows = grid(args.alpha, args.beta2, args.gamma, args.instance)
    print_table(rows)
    return rows


if __name__ == "__main__":
    main()
