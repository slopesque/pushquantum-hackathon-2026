"""Q4 · sonde cloud : UN appel PCE sur le QUBO du kit d'une instance, pour mesurer latence, circuits et
crédits avant de lancer la consolidation cloud.

``PYTHONPATH=src/network-experiments uv run python -m h1.cloud_probe --instance network24 \\
    --population 4 --iterations 1 --mps-bond-dim 32``

Écrit une ligne dans ``results/network/bench/h1/cloud_probe.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import math
import time

from h0.harness import append_jsonl
from h0.instances import best_known, load_demand

from hackathon.referee import qt
from hackathon.utils import git_hash

from .pce import make_pce_sampler, pce_n_qubits


def _balance(service) -> float | None:
    try:
        bal = service.get_credit_balance()
        return float(bal.get("balance", math.nan)) if isinstance(bal, dict) else float(bal)
    except Exception as err:  # noqa: BLE001 - sonde : on note et on continue
        print("solde illisible :", err)
        return None


def main(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(prog="h1.cloud_probe")
    p.add_argument("--instance", default="network24")
    p.add_argument("--population", type=int, default=4)
    p.add_argument("--iterations", type=int, default=1)
    p.add_argument("--layers", type=int, default=2)
    p.add_argument("--encoding", default="poly")
    p.add_argument("--mps-bond-dim", type=int, default=32)
    p.add_argument("--shots", type=int, default=10_000)
    p.add_argument("--max-retries", type=int, default=400)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    from divi.backends import QoroService

    service = QoroService()
    before = _balance(service)
    demand = load_demand(args.instance)
    n = len(demand)
    obj, pen, arcs = qt.build_network_qubo(demand)
    bqm = obj + pen
    sampler = make_pce_sampler(
        use_cloud=True,
        encoding=args.encoding,
        n_layers=args.layers,
        population=args.population,
        iterations=args.iterations,
        shots=args.shots,
        mps_bond_dim=args.mps_bond_dim,
        max_retries=args.max_retries,
    )
    t0 = time.perf_counter()
    error = None
    batch = None
    try:
        batch = sampler(bqm, args.seed)
    except Exception as err:  # noqa: BLE001 - on veut l'erreur dans le JSONL
        error = f"{type(err).__name__}: {err}"
    wall = time.perf_counter() - t0
    after = _balance(service)
    rec: dict = {
        "hypothesis": "h1",
        "method": "cloud_probe_pce_kit",
        "instance": args.instance,
        "seed": args.seed,
        "params": vars(args),
        "n_vars": n * (n - 1),
        "expected_qubits": pce_n_qubits(n * (n - 1), args.encoding),
        "wall_time_s": round(wall, 1),
        "credits_before": before,
        "credits_after": after,
        "credits_used": None if before is None or after is None else round(before - after, 4),
        "error": error,
        "git": git_hash(),
    }
    if batch is not None:
        scores = []
        for row in batch.samples[:20]:
            topo = qt.repair_topology(n, qt.decode_topology(row, arcs), demand)
            scores.append(qt.route_min_congestion(demand, topo).objective)
        best = min(scores) if scores else math.inf
        rec |= {
            "n_circuits": batch.n_circuits,
            "max_qubits": batch.n_qubits,
            "backend": batch.backend,
            "n_samples": len(batch.samples),
            "feasible_mass": float(
                sum(
                    pr
                    for row, pr in zip(batch.samples, batch.probs)
                    if qt.is_valid_topology(n, qt.decode_topology(row, arcs))
                )
            )
            if batch.probs is not None
            else None,
            "best_score_top20_repaired": None if math.isinf(best) else int(best),
            "best_known": best_known(args.instance),
        }
    append_jsonl("h1", "cloud_probe", rec)
    print(json.dumps(rec, indent=1, default=str))
    return rec


if __name__ == "__main__":
    main()
