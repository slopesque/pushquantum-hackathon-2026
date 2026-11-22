"""Tests de l'adaptateur PCE (local uniquement, Maestro, < 3 min)."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from h1.pce import _ordered_copy, make_pce_sampler, pce_n_qubits
from hackathon.referee import qt

warnings.filterwarnings("ignore", category=SyntaxWarning)

BKV_NETWORK05 = 65_500


def _kit_bqm(n: int):
    demand = qt.load_network_demand(n)
    obj, pen, arcs = qt.build_network_qubo(demand)
    bqm = obj.copy()
    bqm.update(pen)
    return demand, bqm, arcs


def test_pce_n_qubits_matches_divi():
    from divi.qprog.algorithms import PCE, DenseEncoding, PolyEncoding
    from divi.qprog.optimizers import MonteCarloOptimizer
    from divi.qprog.problems import BinaryOptimizationProblem

    from hackathon.utils import make_backend

    assert pce_n_qubits(132, "poly") == 16  # notebook 02 : network12 sur 16 qubits
    assert pce_n_qubits(552, "poly") == 33
    assert pce_n_qubits(552, "dense") == 10
    _, bqm, _ = _kit_bqm(12)
    for name, enc in (("poly", PolyEncoding()), ("dense", DenseEncoding())):
        pce = PCE(  # construction seule, pas de run
            BinaryOptimizationProblem(bqm),
            encoding=enc,
            optimizer=MonteCarloOptimizer(),
            backend=make_backend(),
        )
        assert pce.n_qubits == pce_n_qubits(132, name)
    with pytest.raises(ValueError):
        pce_n_qubits(10, "onehot")


@pytest.fixture(scope="module")
def network05_batch():
    demand, bqm, arcs = _kit_bqm(5)
    sampler = make_pce_sampler(population=20, iterations=5, top_n=100)
    return demand, bqm, arcs, sampler(bqm, 0)


def test_network05_batch_shape_and_metadata(network05_batch):
    _, _, _, batch = network05_batch
    assert batch.samples.dtype == np.uint8
    assert batch.samples.ndim == 2 and batch.samples.shape[1] == 20
    assert 0 < batch.samples.shape[0] <= 100
    assert set(np.unique(batch.samples)) <= {0, 1}
    assert batch.probs is not None and batch.probs.shape == (batch.samples.shape[0],)
    assert batch.n_circuits > 0
    assert batch.n_qubits == pce_n_qubits(20, "poly") == 6
    assert batch.backend == "maestro_local"


def test_bitstring_order_matches_bqm_energy(network05_batch):
    """Les échantillons sont triés par énergie Divi croissante : vrai aussi avec bqm.energy
    calculée colonne j = variable j (un ordre inversé casserait la monotonie)."""
    _, bqm, _, batch = network05_batch
    bqm_n = _ordered_copy(bqm)
    bqm_n.normalize()
    energies = np.array([bqm_n.energy(dict(enumerate(map(int, row)))) for row in batch.samples])
    assert np.all(np.diff(energies) >= -1e-9)
    reversed_e = np.array(
        [bqm_n.energy(dict(enumerate(map(int, row[::-1])))) for row in batch.samples]
    )
    assert not np.all(np.diff(reversed_e) >= -1e-9)


def test_network05_reaches_optimum_after_repair(network05_batch):
    demand, _, arcs, batch = network05_batch
    n = len(demand)
    tops = {
        tuple(sorted(qt.repair_topology(n, qt.decode_topology(row, arcs), demand)))
        for row in batch.samples
    }
    best = min(qt.route_min_congestion(demand, list(t)).objective for t in tops)
    assert round(best) == BKV_NETWORK05


def test_local_qubit_limit_raises_before_run():
    _, bqm, _ = _kit_bqm(24)  # 552 variables, 33 qubits en poly
    with pytest.raises(ValueError, match="qubits"):
        make_pce_sampler(encoding="poly")(bqm, 0)
