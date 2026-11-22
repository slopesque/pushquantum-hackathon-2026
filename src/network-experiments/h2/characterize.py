"""Characterization Service (Divi, cloud : **consomme des crédits**) sur le QUBO H2.

Comme ``references/02_network_design.ipynb`` §1.2 : objectif H2 + contraintes de degré
(``LinearConstraint``, poids de pénalité λ = 1) → ``characterize_and_validate`` avec la meilleure
topologie connue comme état de référence. Affiche le λ recommandé, le job_id, le temps et les crédits
consommés, et ajoute une ligne à ``results/network/bench/h2/characterization.jsonl``.

    PYTHONPATH=src/network-experiments uv run python -m h2.characterize --instance network05
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from h0.harness import BENCH_DIR
from h0.instances import load_demand, n_nodes

from hackathon.referee import qt
from hackathon.utils import git_hash

from .surrogate import physics_objective

OUT = BENCH_DIR / "h2" / "characterization.jsonl"


def reference_arcs(instance: str) -> tuple[list[tuple[int, int]], float | None]:
    """Meilleure topologie connue : énumération (n ≤ 6) ou meilleur ``best_arcs`` des JSONL bench."""
    n = n_nodes(instance)
    if n <= 6:
        from .diagnostics import all_topologies_scored

        topos, scores = all_topologies_scored(n)
        k = int(scores.argmin())
        return topos[k], float(scores[k])
    best: tuple[float, list] | None = None
    for path in BENCH_DIR.glob("*/*.jsonl"):
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            ok = rec.get("instance") == instance and rec.get("score") and rec.get("best_arcs")
            if ok and (best is None or rec["score"] < best[0]):
                best = (rec["score"], rec["best_arcs"])
    if best is None:
        raise SystemExit(f"aucune topologie de référence pour {instance} dans {BENCH_DIR}")
    return [tuple(a) for a in best[1]], float(best[0])


def _balance(service) -> Any:
    bal = service.get_credit_balance()
    return bal.get("balance", bal) if isinstance(bal, dict) else bal


def characterize(
    instance: str, alpha: float, beta2: float, gamma: float, lam: float, layers: int
) -> dict[str, Any]:
    from divi.backends import QoroService
    from divi.backends.characterization import CharacterizationOptions, characterize_and_validate
    from divi.qprog.problems import BinaryOptimizationProblem, LinearConstraint

    n = n_nodes(instance)
    demand = load_demand(instance)
    arcs = qt.all_arcs(n)
    objective = physics_objective(demand, alpha, beta2, gamma)
    constraints = []
    for node in range(n):
        out = {v: 1 for v, (i, _) in enumerate(arcs) if i == node}
        inn = {v: 1 for v, (_, j) in enumerate(arcs) if j == node}
        constraints.append(LinearConstraint(out, "==", 2))
        constraints.append(LinearConstraint(inn, "==", 2))
    problem = BinaryOptimizationProblem(objective, constraints=constraints, penalty_weight=lam)
    ref, ref_score = reference_arcs(instance)
    ref_set = set(ref)
    ref_bits = "".join("1" if a in ref_set else "0" for a in arcs)

    service = QoroService()
    before = _balance(service)
    t0 = time.perf_counter()
    report = characterize_and_validate(
        problem,
        reference_states=[ref_bits],
        service=service,
        options=CharacterizationOptions(ansatz={"layers": layers}),
    )
    wall = time.perf_counter() - t0
    after = _balance(service)
    try:
        spent = float(before) - float(after)
    except (TypeError, ValueError):
        spent = None
    record = {
        "instance": instance,
        "n_vars": len(arcs),
        "alpha": alpha,
        "beta2": beta2,
        "gamma": gamma,
        "penalty_weight": lam,
        "layers": layers,
        "job_id": report.job_id,
        "recommended_lambda": report.recommended_lambda,
        "penalty": report.penalty,
        "recommended_layers": report.recommended_layers,
        "gap_closed": report.gap_closed,
        "reference_score": ref_score,
        "references": report.references,
        "credits_before": before,
        "credits_after": after,
        "credits_spent": spent,
        "wall_time_s": round(wall, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git": git_hash(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    return record


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    p = argparse.ArgumentParser(prog="h2.characterize", description=__doc__.splitlines()[0])
    p.add_argument("--instance", nargs="+", required=True)
    p.add_argument("--alpha", type=float, default=1.0)
    p.add_argument("--beta2", type=float, default=0.5)
    p.add_argument("--gamma", type=float, default=0.0)
    p.add_argument("--lam", type=float, default=1.0, help="poids de pénalité envoyé")
    p.add_argument("--layers", type=int, default=2)
    args = p.parse_args(argv)
    out = []
    for inst in args.instance:
        rec = characterize(inst, args.alpha, args.beta2, args.gamma, args.lam, args.layers)
        print(
            f"{inst}: job_id={rec['job_id']} recommended_lambda={rec['recommended_lambda']} "
            f"layers={rec['recommended_layers']} t={rec['wall_time_s']}s "
            f"credits {rec['credits_before']} → {rec['credits_after']} "
            f"(spent {rec['credits_spent']})"
        )
        print(f"  penalty: {rec['penalty']}")
        out.append(rec)
    return out


if __name__ == "__main__":
    main()
