"""H4 : QAOA Dicke-XY (faisable par construction sur les lignes) et QAOA à pénalités (notebook).

Les deux fonctions partagent couches, shots, population et itérations du ``MonteCarloOptimizer`` :
même nombre de circuits. Elles renvoient **toute** la distribution mesurée, triée par probabilité
décroissante (``get_top_solutions(n=0)``).

Ordre des bits : ``SolutionEntry.bitstring[i]`` = qubit i = variable i du BQM (le BQM est recopié
avec ses variables insérées dans l'ordre 0..N-1 et ``DickeRowsProblem`` vérifie
``variable_to_idx[v] == v``). Les tests le contrôlent avec des blocs de tailles différentes et par
l'énergie.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import dimod
import numpy as np
from h1.pce import _make_backend
from h1.samplers import SampleBatch

from .circuits import (
    Connectivity,
    DickeRowsProblem,
    in_degree_penalty,
    ordered_bqm,
    out_degree_penalty,
    row_blocks,
)

MAX_LOCAL_QUBITS = 24


@dataclass
class QAOABatch(SampleBatch):
    """``SampleBatch`` + infos du run QAOA (temps, couches, meilleurs angles)."""

    wall_time_s: float = 0.0
    info: dict[str, Any] = field(default_factory=dict)


def _cost(bqm_obj: dimod.BinaryQuadraticModel, pen: dimod.BinaryQuadraticModel, lam: float):
    cost = ordered_bqm(bqm_obj)
    p = pen.copy()
    p.scale(float(lam))
    cost.update(p)
    return ordered_bqm(cost)


def _run_qaoa(
    problem,
    *,
    n_vars: int,
    layers: int,
    population: int,
    iterations: int,
    shots: int,
    seed: int,
    use_cloud: bool,
    mps_bond_dim: int | None,
    simulator_cluster: str | None = None,
    label: str,
) -> QAOABatch:
    from divi.qprog.algorithms import QAOA
    from divi.qprog.optimizers import MonteCarloOptimizer

    if not use_cloud and n_vars > MAX_LOCAL_QUBITS:
        raise ValueError(
            f"QAOA sur {n_vars} qubits > {MAX_LOCAL_QUBITS} : interdit en local (passer au cloud)"
        )
    t0 = time.perf_counter()
    qaoa = QAOA(
        problem,
        n_layers=layers,
        optimizer=MonteCarloOptimizer(population_size=population),
        max_iterations=iterations,
        backend=_make_backend(use_cloud, shots, simulator_cluster, mps_bond_dim),
        seed=int(seed),
    )
    if qaoa.n_qubits != n_vars:
        raise RuntimeError(f"{qaoa.n_qubits} qubits pour {n_vars} variables")
    qaoa.run()
    tops = qaoa.get_top_solutions(n=0)
    if tops:
        samples = np.array([[c == "1" for c in s.bitstring] for s in tops], dtype=np.uint8)
    else:
        samples = np.zeros((0, n_vars), dtype=np.uint8)
    probs = np.array([s.prob for s in tops], dtype=float)
    best_params = getattr(qaoa, "best_params", None)
    return QAOABatch(
        samples=samples,
        probs=probs,
        n_circuits=int(qaoa.total_circuit_count),
        n_qubits=int(qaoa.n_qubits),
        backend="qoro_cloud" if use_cloud else "maestro_local",
        wall_time_s=time.perf_counter() - t0,
        info={
            "method": label,
            "layers": layers,
            "best_loss": float(qaoa.best_loss) if hasattr(qaoa, "best_loss") else None,
            "best_params": None if best_params is None else np.asarray(best_params).tolist(),
        },
    )


def qaoa_dicke_bqm(
    cost: dimod.BinaryQuadraticModel,
    n_rows: int,
    row_len: int,
    *,
    layers: int = 2,
    population: int = 20,
    iterations: int = 10,
    shots: int = 10_000,
    seed: int = 0,
    use_cloud: bool = False,
    mps_bond_dim: int | None = None,
    connectivity: Connectivity = "ring",
    normalize: bool = True,
) -> QAOABatch:
    """QAOA Dicke-XY sur un BQM quelconque à ``n_rows`` blocs contigus de ``row_len`` qubits."""
    cost = ordered_bqm(cost)
    if cost.num_variables != n_rows * row_len:
        raise ValueError(f"{cost.num_variables} variables != {n_rows}×{row_len}")
    if normalize:
        cost.normalize()
    problem = DickeRowsProblem(cost, row_blocks(n_rows, row_len), 2, connectivity)
    return _run_qaoa(
        problem,
        n_vars=cost.num_variables,
        layers=layers,
        population=population,
        iterations=iterations,
        shots=shots,
        seed=seed,
        use_cloud=use_cloud,
        mps_bond_dim=mps_bond_dim,
        label="dicke_xy",
    )


def qaoa_dicke(
    bqm_obj: dimod.BinaryQuadraticModel,
    n: int,
    *,
    lam: float = 1.0,
    layers: int = 2,
    population: int = 20,
    iterations: int = 10,
    shots: int = 10_000,
    seed: int = 0,
    use_cloud: bool = False,
    mps_bond_dim: int | None = None,
    connectivity: Connectivity = "ring",
    normalize: bool = True,
) -> QAOABatch:
    """QAOA Dicke-XY : coût = ``bqm_obj`` + λ·pénalité des degrés entrants ; n lignes de n−1."""
    cost = _cost(bqm_obj, in_degree_penalty(n), lam)
    return qaoa_dicke_bqm(
        cost,
        n,
        n - 1,
        layers=layers,
        population=population,
        iterations=iterations,
        shots=shots,
        seed=seed,
        use_cloud=use_cloud,
        mps_bond_dim=mps_bond_dim,
        connectivity=connectivity,
        normalize=normalize,
    )


def qaoa_penalty(
    bqm_obj: dimod.BinaryQuadraticModel,
    n: int,
    *,
    lam: float = 1.0,
    layers: int = 2,
    population: int = 20,
    iterations: int = 10,
    shots: int = 10_000,
    seed: int = 0,
    use_cloud: bool = False,
    mps_bond_dim: int | None = None,
    normalize: bool = True,
) -> QAOABatch:
    """QAOA du notebook : ``BinaryOptimizationProblem`` sur ``bqm_obj`` + λ·(pénalités entrantes et
    sortantes), mixer X, superposition uniforme."""
    from divi.qprog.problems import BinaryOptimizationProblem

    pen = in_degree_penalty(n)
    pen.update(out_degree_penalty(n))
    cost = _cost(bqm_obj, pen, lam)
    if normalize:
        cost.normalize()
    problem = BinaryOptimizationProblem(cost)
    return _run_qaoa(
        problem,
        n_vars=cost.num_variables,
        layers=layers,
        population=population,
        iterations=iterations,
        shots=shots,
        seed=seed,
        use_cloud=use_cloud,
        mps_bond_dim=mps_bond_dim,
        label="penalty_x",
    )
