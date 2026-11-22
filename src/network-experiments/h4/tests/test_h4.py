"""Tests H4 (locaux, < 3 min) : Dicke par blocs, mixer XY, ordre des bits, network05, boucle SA."""

from __future__ import annotations

import warnings
from collections import Counter

import dimod
import numpy as np
import pytest

from h4.circuits import (
    DickeRowsProblem,
    DickeRowsState,
    in_degree_penalty,
    out_degree_penalty,
    row_blocks,
)

warnings.filterwarnings("ignore", category=SyntaxWarning)


def _probs_of(qc) -> dict[str, float]:
    """Probabilités exactes, clé = bits dans l'ordre des qubits (qubit 0 en premier)."""
    from qiskit.quantum_info import Statevector

    return {k[::-1]: v for k, v in Statevector(qc).probabilities_dict().items() if v > 1e-12}


def test_dicke_rows_state_uniform():
    probs = _probs_of(DickeRowsState(row_blocks(2, 4), 2).build(range(8)))
    assert len(probs) == 36
    for bits, p in probs.items():
        assert bits[:4].count("1") == 2 and bits[4:].count("1") == 2
        assert p == pytest.approx(1 / 36, abs=1e-9)


def test_dicke_rows_state_uneven_blocks_order():
    # Blocs de tailles différentes : vérifie aussi que le bloc 0 est sur les premiers qubits.
    probs = _probs_of(DickeRowsState([[0, 1, 2], [3, 4, 5, 6, 7]], 2).build(range(8)))
    assert len(probs) == 3 * 10
    assert all(b[:3].count("1") == 2 and b[3:].count("1") == 2 for b in probs)


def test_degree_penalties_zero_on_valid():
    from hackathon.referee import qt

    n = 5
    rng = np.random.default_rng(0)
    arcs = qt.all_arcs(n)
    topo = set(qt.random_topology(n, rng))
    x = {v: int(a in topo) for v, a in enumerate(arcs)}
    assert in_degree_penalty(n).energy(x) == 0
    assert out_degree_penalty(n).energy(x) == 0
    x[0] = 1 - x[0]
    assert in_degree_penalty(n).energy(x) == 1 and out_degree_penalty(n).energy(x) == 1


def _run_qaoa(problem, layers=1, population=4, iterations=2, seed=0, shots=20_000):
    from divi.qprog.algorithms import QAOA
    from divi.qprog.optimizers import MonteCarloOptimizer

    from hackathon.utils import make_backend

    q = QAOA(
        problem,
        n_layers=layers,
        optimizer=MonteCarloOptimizer(population_size=population),
        max_iterations=iterations,
        backend=make_backend(shots=shots),
        seed=seed,
    )
    q.run()
    return q.get_top_solutions(n=0)


@pytest.mark.parametrize("blocks", [row_blocks(2, 4), [[0, 1, 2], [3, 4, 5, 6, 7]]])
def test_xy_mixer_preserves_row_weight(blocks):
    rng = np.random.default_rng(1)
    lin = {v: float(rng.normal()) for v in range(8)}
    quad = {(u, v): float(rng.normal()) for u in range(8) for v in range(u + 1, 8)}
    bqm = dimod.BinaryQuadraticModel(lin, quad, 0.0, dimod.BINARY)
    tops = _run_qaoa(DickeRowsProblem(bqm, blocks), layers=1, population=4, iterations=2)
    w = Counter()
    for s in tops:
        w[tuple(s.bitstring[b[0] : b[-1] + 1].count("1") for b in blocks)] += s.prob
    assert w[(2, 2)] == pytest.approx(1.0, abs=1e-9)
    assert len(tops) > 1  # le mixer mélange vraiment


def test_bit_order_by_energy():
    """Champ fort sur la variable 0 et 5 : l'échantillon le plus probable les met à 1."""
    from h4.sampling import qaoa_dicke_bqm

    lin = {v: 1.0 for v in range(8)}
    lin[0] = lin[5] = -3.0
    lin[1] = lin[6] = -2.0
    bqm = dimod.BinaryQuadraticModel(lin, {}, 0.0, dimod.BINARY)
    batch = qaoa_dicke_bqm(bqm, 2, 4, layers=2, population=10, iterations=5, shots=5_000, seed=0)
    energies = [bqm.energy(dict(enumerate(s))) for s in batch.samples]
    exp_energy = float(np.dot(batch.probs, energies))
    # Si l'ordre était inversé, la même distribution aurait une énergie bien plus haute.
    rev = [bqm.energy(dict(enumerate(s[::-1]))) for s in batch.samples]
    assert exp_energy < float(np.dot(batch.probs, rev))
    assert exp_energy < 0.5 * min(energies) + 0.5 * max(energies)


def test_network05_dicke_vs_penalty():
    from h4.metrics import all_valid_scores, feasibility_metrics
    from h4.sampling import qaoa_dicke, qaoa_penalty
    from hackathon.referee import qt

    n = 5
    demand = qt.load_network_demand(n)
    all_scores = all_valid_scores(n, demand)
    assert len(all_scores) == 216
    assert min(all_scores.values()) == 65_500
    obj, _, _ = qt.build_network_qubo(demand)
    kw = {"layers": 1, "population": 4, "iterations": 2, "shots": 5_000, "seed": 0}
    d = qaoa_dicke(obj, n, **kw)
    p = qaoa_penalty(obj, n, **kw)
    assert d.n_circuits == p.n_circuits and d.n_qubits == p.n_qubits == 20
    md = feasibility_metrics(d.samples, d.probs, n, demand, all_scores)
    mp = feasibility_metrics(p.samples, p.probs, n, demand, all_scores)
    assert md["outdeg_mass"] == pytest.approx(1.0, abs=1e-9)
    assert md["feasible_mass"] > mp["feasible_mass"]


def test_rows_sa_network12_runs():
    from h0.harness import run_method

    from h4.methods import h4_rows_sa

    rec = run_method("h4", "h4_rows_sa", h4_rows_sa, "network12", 0, params={},
                     max_lp_calls=100, write=False)  # fmt: skip
    assert rec["lp_calls"] == 100
    assert rec["score"] is not None
    assert rec["feasible_mass"] is not None
