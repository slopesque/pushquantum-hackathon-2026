"""Tests de la FM (h1/fm.py) et des diagnostics F1/F2 (h1/diagnostics.py).

Lancer avec ``PYTHONPATH=src/network-experiments uv run pytest src/network-experiments/h1/tests/test_fm.py``.
"""

from __future__ import annotations

import numpy as np

from h1.diagnostics import (
    kit_objective,
    qubo_energies,
    spearman_rho,
    surrogate_metrics,
    top10_precision,
)
from h1.fm import FactorizationMachine, X_to_arcs, learned_qubo, make_target, topologies_to_X
from hackathon.referee import qt

N_NODES = 5  # network05 : 20 variables, données téléchargées une fois (pas de LP dans ces tests)


def _demand(n: int = N_NODES) -> np.ndarray:
    return qt.load_network_demand(n)


def test_topologies_roundtrip():
    rng = np.random.default_rng(0)
    topos = [qt.random_topology(N_NODES, rng) for _ in range(10)]
    X = topologies_to_X(topos, N_NODES)
    assert X.shape == (10, N_NODES * (N_NODES - 1)) and X.dtype == np.uint8
    assert (X.sum(axis=1) == 2 * N_NODES).all()
    for row, arcs in zip(X, topos, strict=True):
        assert sorted(X_to_arcs(row, N_NODES)) == sorted(arcs)


def test_make_target_monotone():
    rng = np.random.default_rng(1)
    s = rng.normal(size=50) * 1e5 + 3e5
    s[3] = s[7]  # ex aequo
    order = np.argsort(s)
    for mode in ("rank", "zscore", "minmax"):
        t = make_target(s, mode)
        assert np.all(np.diff(t[order]) >= -1e-12), mode
        assert t[3] == t[7]
    r = make_target(s, "rank")
    assert r.min() == 0.0 and r.max() == 1.0


def _synthetic(n=30, k=4, m=3000, seed=0):
    rng = np.random.default_rng(seed)
    w = rng.normal(size=n)
    V = rng.normal(scale=0.5, size=(n, k))
    Q = np.triu(V @ V.T, 1)
    X = (rng.random((m, n)) < 0.3).astype(np.uint8)
    y = 1.0 + X @ w + np.einsum("bi,ij,bj->b", X, Q, X)
    return X, y


def test_fm_learns_quadratic():
    X, y = _synthetic()
    Xtr, ytr, Xte, yte = X[:2500], y[:2500], X[2500:], y[2500:]
    fm = FactorizationMachine(30, rank=4, seed=0, lr=0.02, l2=1e-6, init_std=0.1)
    fm.fit(Xtr, ytr, epochs=150, batch_size=128)
    pred = fm.predict(Xte)
    r2 = 1 - ((pred - yte) ** 2).sum() / ((yte - yte.mean()) ** 2).sum()
    assert r2 > 0.9, r2


def test_fit_deterministic_and_warm_start():
    X, y = _synthetic(m=300)
    a = FactorizationMachine(30, rank=4, seed=3).fit(X, y, epochs=5)
    b = FactorizationMachine(30, rank=4, seed=3).fit(X, y, epochs=5)
    assert np.array_equal(a.predict(X), b.predict(X))
    mse0 = ((a.predict(X) - y) ** 2).mean()
    a.fit(X, y, epochs=20)  # warm start : continue à baisser
    assert ((a.predict(X) - y) ** 2).mean() < mse0


def test_to_bqm_energy_equals_predict():
    rng = np.random.default_rng(2)
    fm = FactorizationMachine(20, rank=3, seed=0, init_std=0.5)
    fm.w = rng.normal(size=20)
    fm.w0 = 1.7
    X = (rng.random((40, 20)) < 0.5).astype(np.uint8)
    assert np.allclose(qubo_energies(fm.to_bqm(), X), fm.predict(X))


def test_learned_qubo_penalty_and_scale():
    n = N_NODES
    rng = np.random.default_rng(4)
    fm = FactorizationMachine(n * (n - 1), rank=3, seed=0, init_std=0.3)
    fm.w = rng.normal(size=n * (n - 1))
    fm.w0 = 5.0
    full, objective = learned_qubo(fm, _demand(), lam=3.0)
    lin, (_, _, quad), off = objective.to_numpy_vectors(variable_order=list(range(n * (n - 1))))
    assert off == 0.0
    assert np.isclose(max(np.abs(lin).max(), np.abs(quad).max()), 1.0)
    X = topologies_to_X([qt.random_topology(n, rng) for _ in range(5)], n)
    assert np.allclose(qubo_energies(full, X), qubo_energies(objective, X))  # pénalité nulle
    bad = X[:1].copy()
    bad[0, np.flatnonzero(bad[0])[0]] = 0
    assert qubo_energies(full, bad)[0] > qubo_energies(objective, bad)[0]


def test_top10_precision_and_spearman():
    rng = np.random.default_rng(5)
    s = rng.normal(size=200)
    assert top10_precision(s, s) == 1.0
    assert np.isclose(spearman_rho(s, s), 1.0)
    rand = [top10_precision(rng.normal(size=200), s) for _ in range(300)]
    assert abs(np.mean(rand) - 0.1) < 0.02


def test_surrogate_metrics_kit():
    n = N_NODES
    rng = np.random.default_rng(6)
    topos = [qt.random_topology(n, rng) for _ in range(30)]
    obj = kit_objective(_demand())
    e = qubo_energies(obj, topologies_to_X(topos, n))
    out = surrogate_metrics(obj, topos, e, n)  # scores == énergies → métriques parfaites
    assert np.isclose(out["spearman_rho"], 1.0) and out["top10_precision"] == 1.0
