"""Prépare et dépose les .sol network sur le stockage aqora, par étapes (leaderboard Qoro × PushQuantum).

Le leaderboard ne garde que le meilleur score par instance : on dépose de la moins bonne à la meilleure
solution, et l'utilisateur clique « Submit » sur la page web entre deux étapes.

    PYTHONPATH=src/network-experiments uv run python scripts/aqora_stage_network.py --stage 1           # prépare
    PYTHONPATH=src/network-experiments uv run python scripts/aqora_stage_network.py --stage 1 --upload  # + dépôt

Chaque .sol est reconstruit depuis la meilleure topologie (``best_arcs``) du run choisi dans
``results/network/bench/<hyp>/<méthode>.jsonl``, routé en entier, vérifié par l'arbitre, puis copié dans
``results/network/aqora/stage<k>/``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from h0.harness import BENCH_DIR, read_jsonl
from h0.instances import n_nodes

from hackathon.referee import qt
from hackathon.utils import RESULTS_DIR

FOLDER = "pushquantum-2026-qoro"
OUT = RESULTS_DIR / "network" / "aqora"

# (instance, hypothèse, méthode, seed, filtre budget LP ou None, qubits, description)
STAGES: dict[int, list[tuple]] = {
    1: [
        (
            "network05",
            "h4",
            "h4_qaoa_dicke",
            0,
            None,
            20,
            (
                "H4: QAOA p=2, Dicke state per row + row XY mixer (feasible out-degrees by construction), "
                "repair + routing LP"
            ),
        ),
        (
            "network12",
            "h1",
            "h1_sa_fm",
            1,
            None,
            0,
            (
                "H1: FMQA, factorization machine learned online from the routing LP + kit prior, SA, repair, "
                "5000 LP"
            ),
        ),
        (
            "network24",
            "h1",
            "h1_pce_fm",
            1,
            None,
            33,
            (
                "H1: FMQA loop with PCE (PolyEncoding, 33 qubits, Qoro cloud MPS) replacing SA every 10 rounds, "
                "repair + routing LP"
            ),
        ),
    ],
    2: [
        (
            "network05",
            "h1",
            "h1_sa_fm",
            0,
            None,
            0,
            "H1: FMQA, factorization machine learned online from the routing LP + kit prior, SA",
        ),
        (
            "network24",
            "h1",
            "h1_sa_fm",
            0,
            10_000,
            0,
            "H1: FMQA, factorization machine learned online from the routing LP + kit prior, SA, 10000 LP",
        ),
    ],
    3: [
        (
            "network05",
            "h2",
            "h2_fm_phys",
            0,
            None,
            0,
            "H2+H1: QUBO with 2-hop routing terms as prior of an online factorization machine (FMQA), SA",
        ),
        (
            "network12",
            "h2",
            "h2_fm_phys",
            2,
            None,
            0,
            (
                "H2+H1: QUBO with 2-hop routing terms as prior of an online factorization machine (FMQA), SA, "
                "5000 LP"
            ),
        ),
        (
            "network24",
            "h2",
            "h2_fm_phys",
            0,
            10_000,
            0,
            (
                "H2+H1: QUBO with 2-hop routing terms as prior of an online factorization machine (FMQA), SA, "
                "10000 LP"
            ),
        ),
    ],
}


def pick(hyp: str, method: str, instance: str, seed: int, lp: int | None) -> dict:
    recs = [
        r
        for r in read_jsonl(hyp, method)
        if r["instance"] == instance
        and r["seed"] == seed
        and r.get("best_arcs")
        and (lp is None or r["lp_calls"] == lp)
    ]
    if not recs:
        raise SystemExit(f"aucun run {hyp}/{method} {instance} seed {seed} dans {BENCH_DIR}")
    return min(recs, key=lambda r: r["score"])


def build(stage: int) -> list[tuple[Path, Path, dict]]:
    out_dir = OUT / f"stage{stage}"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for instance, hyp, method, seed, lp, qubits, desc in STAGES[stage]:
        rec = pick(hyp, method, instance, seed, lp)
        n = n_nodes(instance)
        demand = qt.load_network_demand(n)
        routing = qt.route_integral(demand, [tuple(a) for a in rec["best_arcs"]])
        sol = out_dir / f"{instance}.sol"
        qt.write_network_solution(sol, n, routing)
        valid, score, msg = qt.check_network_solution(sol, n, demand)
        assert valid and score == rec["score"], f"{sol}: {msg}, {score} != {rec['score']}"
        meta = {"qubits": qubits, "method": f"{desc} (seed {seed})"}
        js = sol.with_suffix(".json")
        js.write_text(json.dumps(meta))
        print(
            f"stage {stage} {instance}: {score} ({hyp}/{method}, seed {seed}, {qubits} qubits) → {sol}"
        )
        files.append((sol, js, meta))
    return files


def upload(files: list[tuple[Path, Path, dict]]) -> None:
    import aqora

    store = aqora.Store()
    for sol, js, _ in files:
        store.put(f"{FOLDER}/{sol.name}", sol.read_bytes())
        store.put(f"{FOLDER}/{js.name}", js.read_bytes(), content_type="application/json")
        back = store.get(f"{FOLDER}/{sol.name}")
        assert back == sol.read_bytes(), f"relecture différente pour {sol.name}"
        print(f"déposé : {FOLDER}/{sol.name} (+ .json)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=int, choices=sorted(STAGES), required=True)
    p.add_argument("--upload", action="store_true")
    args = p.parse_args()
    files = build(args.stage)
    if args.upload:
        upload(files)


if __name__ == "__main__":
    main()
