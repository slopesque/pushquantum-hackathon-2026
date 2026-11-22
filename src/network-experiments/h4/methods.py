"""H4 : méthodes au format du harnais h0 (``method(demand, seed, scorer, **params) -> dict``).

- ``h4_qaoa_dicke`` / ``h4_qaoa_penalty`` : un appel QAOA (Dicke-XY ou pénalités), top-K
  échantillons par probabilité → repair → scorer LP.
- ``h4_rows_q`` / ``h4_rows_sa`` : boucle par blocs de r lignes. Solution courante = topologie
  aléatoire valide ; pour chaque bloc, BQM conditionné (autres lignes fixées) de l'objectif du kit +
  λ·pénalité des degrés entrants ; échantillonneur = QAOA Dicke-XY (r×(n−1) qubits) ou SA (même
  BQM + λ·pénalité des degrés sortants du bloc) ; top-K blocs → assemblage → repair → scorer ; la
  meilleure topologie devient la solution courante ; balayages jusqu'à épuisement du budget.
"""

from __future__ import annotations

import math
from typing import Any

import dimod
import numpy as np
from h0.scorer import BudgetExhausted, Scorer

from hackathon.referee import qt

from .circuits import in_degree_penalty, ordered_bqm, out_degree_penalty
from .metrics import all_valid_scores, feasibility_metrics
from .sampling import MAX_LOCAL_QUBITS, qaoa_dicke, qaoa_dicke_bqm, qaoa_penalty


def _score_topk(
    samples: np.ndarray, n: int, demand: np.ndarray, scorer: Scorer, top_k: int
) -> tuple[int, bool]:
    """Repair + LP des ``top_k`` premiers échantillons. Renvoie (nb notés, budget épuisé)."""
    arcs = qt.all_arcs(n)
    done = 0
    for s in samples[:top_k]:
        topo = qt.repair_topology(n, [arcs[v] for v in np.flatnonzero(s)], demand)
        try:
            scorer.score(topo)
        except BudgetExhausted:
            return done, True
        done += 1
    return done, False


def _single_qaoa(kind: str, demand, seed, scorer, **params) -> dict[str, Any]:
    n = len(demand)
    lam = float(params.get("lam", 1.0))
    top_k = int(params.get("top_k", 100))
    qparams = {
        "lam": lam,
        "layers": int(params.get("layers", 2)),
        "population": int(params.get("population", 20)),
        "iterations": int(params.get("iterations", 10)),
        "shots": int(params.get("shots", 10_000)),
        "seed": int(seed),
        "use_cloud": bool(params.get("use_cloud", False)),
        "mps_bond_dim": params.get("mps_bond_dim"),
    }
    obj, _pen, _arcs = qt.build_network_qubo(demand)
    fn = qaoa_dicke if kind == "dicke" else qaoa_penalty
    batch = fn(obj, n, **qparams)
    all_scores = all_valid_scores(n, demand) if n <= 6 else None
    m = feasibility_metrics(batch.samples, batch.probs, n, demand, all_scores)
    n_scored, _ = _score_topk(batch.samples, n, demand, scorer, top_k)
    return {
        **m,
        "n_circuits": batch.n_circuits,
        "max_qubits": batch.n_qubits,
        "backend": batch.backend,
        "qaoa_time_s": round(batch.wall_time_s, 2),
        "n_scored": n_scored,
        "qaoa_best_loss": batch.info.get("best_loss"),
        "params": {"top_k": top_k, **{k: v for k, v in qparams.items() if k != "seed"}},
    }


def h4_qaoa_dicke(demand, seed, scorer, **params) -> dict[str, Any]:
    """QAOA Dicke par ligne + mixer XY (anneau) ; coût = kit + λ·degrés entrants."""
    return _single_qaoa("dicke", demand, seed, scorer, **params)


def h4_qaoa_penalty(demand, seed, scorer, **params) -> dict[str, Any]:
    """QAOA du notebook : superposition, mixer X, kit + λ·(degrés entrants + sortants)."""
    return _single_qaoa("penalty", demand, seed, scorer, **params)


# --------------------------------------------------------------------------- boucle par blocs


def _conditioned(
    full: dimod.BinaryQuadraticModel, x: np.ndarray, block_vars: list[int]
) -> dimod.BinaryQuadraticModel:
    """BQM restreint à ``block_vars`` (renumérotées 0..m−1), les autres variables fixées à ``x``."""
    inside = set(block_vars)
    fixed = {v: int(x[v]) for v in range(len(x)) if v not in inside}
    sub = full.copy()
    sub.fix_variables(fixed)
    sub.relabel_variables({v: k for k, v in enumerate(block_vars)}, inplace=True)
    return ordered_bqm(sub)


def _topo_to_x(n: int, topo) -> np.ndarray:
    index = {a: v for v, a in enumerate(qt.all_arcs(n))}
    x = np.zeros(n * (n - 1), dtype=np.uint8)
    for a in topo:
        x[index[tuple(a)]] = 1
    return x


def _rows_loop(quantum: bool, demand, seed, scorer: Scorer, **params) -> dict[str, Any]:
    n = len(demand)
    m = n - 1
    r = int(params.get("rows_per_block", 2))
    lam = float(params.get("lam", 1.0))
    top_k = int(params.get("top_k", 100))
    layers = int(params.get("layers", 2))
    population = int(params.get("population", 20))
    iterations = int(params.get("iterations", 10))
    shots = int(params.get("shots", 10_000))
    sa_reads = int(params.get("sa_reads", 100))
    use_cloud = bool(params.get("use_cloud", False))
    mps_bond_dim = params.get("mps_bond_dim")
    max_sweeps = params.get("max_sweeps")
    if quantum and not use_cloud and r * m > MAX_LOCAL_QUBITS:
        raise ValueError(f"bloc de {r * m} qubits > {MAX_LOCAL_QUBITS} en local : --cloud requis")

    rng = np.random.default_rng(seed)
    arcs = qt.all_arcs(n)
    obj, _pen, _ = qt.build_network_qubo(demand)
    full = ordered_bqm(obj)
    p_in = in_degree_penalty(n)
    p_in.scale(lam)
    full.update(p_in)
    full_sa = full.copy()
    p_out = out_degree_penalty(n)
    p_out.scale(lam)
    full_sa.update(p_out)  # SA : degrés sortants du bloc pénalisés (les autres lignes sont fixes)

    current = qt.random_topology(n, rng)
    x = _topo_to_x(n, current)
    best_score = scorer.score(current)
    blocks = [list(range(b, min(b + r, n))) for b in range(0, n, r)]
    n_circuits, max_qubits, n_sweeps = 0, 0, 0
    masses: list[float] = []
    sa = None
    if not quantum:
        from dwave.samplers import SimulatedAnnealingSampler

        sa = SimulatedAnnealingSampler()
    call = 0
    exhausted = False
    while not exhausted and (max_sweeps is None or n_sweeps < int(max_sweeps)):
        for rows in blocks:
            bvars = [v for i in rows for v in range(i * m, (i + 1) * m)]
            call_seed = int(seed) * 100_003 + call
            call += 1
            if quantum:
                sub = _conditioned(full, x, bvars)
                batch = qaoa_dicke_bqm(
                    sub,
                    len(rows),
                    m,
                    layers=layers,
                    population=population,
                    iterations=iterations,
                    shots=shots,
                    seed=call_seed,
                    use_cloud=use_cloud,
                    mps_bond_dim=mps_bond_dim,
                )
                samples, probs = batch.samples, batch.probs
                n_circuits += batch.n_circuits
                max_qubits = max(max_qubits, batch.n_qubits)
            else:
                sub = _conditioned(full_sa, x, bvars)
                ss = sa.sample(sub, num_reads=sa_reads, seed=call_seed % (2**32))  # type: ignore[union-attr]
                pos = {v: k for k, v in enumerate(ss.variables)}
                raw = np.asarray(ss.record.sample, dtype=np.uint8)[
                    :, [pos[v] for v in range(len(bvars))]
                ]
                order = np.argsort(ss.record.energy, kind="stable")
                samples, probs = raw[order], None
            # Assemblage : blocs candidats dans la solution courante.
            full_samples = np.repeat(x[None, :], len(samples), axis=0)
            full_samples[:, bvars] = samples
            masses.append(feasibility_metrics(full_samples, probs, n, demand)["feasible_mass"])
            seen: set[bytes] = set()
            for s in full_samples:
                if len(seen) >= top_k:
                    break
                key = s.tobytes()
                if key in seen:
                    continue
                seen.add(key)
                topo = qt.repair_topology(n, [arcs[v] for v in np.flatnonzero(s)], demand)
                try:
                    sc = scorer.score(topo)
                except BudgetExhausted:
                    exhausted = True
                    break
                if sc < best_score:
                    best_score, current = sc, topo
                    x = _topo_to_x(n, current)
            if exhausted:
                break
        else:
            n_sweeps += 1
    qparams = {
        "layers": layers,
        "population": population,
        "iterations": iterations,
        "shots": shots,
        "use_cloud": use_cloud,
        "mps_bond_dim": mps_bond_dim,
    }
    return {
        "feasible_mass": float(np.mean(masses)) if masses else None,
        "n_circuits": n_circuits,
        "max_qubits": max_qubits if quantum else 0,
        "backend": ("qoro_cloud" if use_cloud else "maestro_local") if quantum else "none",
        "n_sweeps": n_sweeps,
        "n_block_calls": call,
        "current_score": None if math.isinf(best_score) else int(best_score),
        "params": {
            "rows_per_block": r,
            "lam": lam,
            "top_k": top_k,
            **(qparams if quantum else {"sa_reads": sa_reads}),
        },
    }


def h4_rows_q(demand, seed, scorer, **params) -> dict[str, Any]:
    """Boucle par blocs de lignes, QAOA Dicke-XY par bloc."""
    return _rows_loop(True, demand, seed, scorer, **params)


def h4_rows_sa(demand, seed, scorer, **params) -> dict[str, Any]:
    """Ablation : même boucle, SA (dwave) par bloc (BQM + pénalité des degrés sortants)."""
    return _rows_loop(False, demand, seed, scorer, **params)
