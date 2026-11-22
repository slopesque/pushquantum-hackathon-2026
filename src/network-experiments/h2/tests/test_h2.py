"""Tests H2 : substitut, règles de λ, énumération network05, méthodes, crochet h1."""

from __future__ import annotations

import numpy as np
from h0.harness import run_method
from h0.instances import load_demand
from h1.fm import FactorizationMachine, learned_qubo

from h2.diagnostics import enumerate_valid_topologies
from h2.methods import h2_sa_phys
from h2.surrogate import lambda_rule, physics_objective, physics_qubo
from hackathon.referee import qt


def _vec(bqm, n_vars):
    lin = np.array([bqm.get_linear(v) for v in range(n_vars)])
    return lin, dict(bqm.quadratic)


def test_kit_recovered_with_beta2_zero():
    d = load_demand("network12")
    kit = qt.build_network_qubo(d)[0]
    h2 = physics_objective(d, alpha=1.0, beta2=0.0, gamma=0.0)
    lk, qk = _vec(kit, 132)
    lh, qh = _vec(h2, 132)
    assert not qh and not qk
    np.testing.assert_allclose(lh * np.abs(lk).max(), lk, atol=1e-12)


def test_normalisation_and_order():
    d = load_demand("network08")
    for b2, g in ((0.5, 0.0), (2.0, 0.5)):
        bqm = physics_objective(d, 1.0, b2, g)
        assert set(bqm.variables) == set(range(56))
        lin = np.abs(list(bqm.linear.values()))
        quad = np.abs(list(bqm.quadratic.values()))
        assert np.isclose(max(lin.max(), quad.max()), 1.0)
        assert bqm.offset == 0.0
    # Couplage 2 sauts (0→1, 1→2) présent, pas de couplage (0→1, 1→0).
    idx = {a: v for v, a in enumerate(qt.all_arcs(8))}
    bqm = physics_objective(d, 1.0, 0.5, 0.0)
    assert bqm.get_quadratic(idx[0, 1], idx[1, 2]) < 0
    assert (idx[0, 1], idx[1, 0]) not in bqm.quadratic


def test_penalty_zero_on_valid_topology():
    d = load_demand("network12")
    full, obj = physics_qubo(d, 1.0, 0.5, 0.0, lam=3.0)
    topo = qt.random_topology(12, np.random.default_rng(0))
    arcs = set(topo)
    sample = {v: int(a in arcs) for v, a in enumerate(qt.all_arcs(12))}
    assert np.isclose(full.energy(sample), obj.energy(sample))


def test_lambda_rules():
    obj = physics_objective(load_demand("network12"), 1.0, 0.5, 0.0)
    assert lambda_rule(obj, "unit") == 1.0
    assert lambda_rule(obj, "ayodele") >= 1.0
    lin = np.abs(list(obj.linear.values())).sum()
    quad = np.abs(list(obj.quadratic.values())).sum()
    assert lambda_rule(obj, "broesamle") > lin + quad - 1e-9


def test_216_valid_topologies_network05():
    topos = enumerate_valid_topologies(5)
    assert len(topos) == 216
    assert len({frozenset(t) for t in topos}) == 216
    assert all(qt.is_valid_topology(5, t) for t in topos)


def test_h2_sa_phys_finds_optimum_network05():
    rec = run_method("h2", "h2_sa_phys", h2_sa_phys, "network05", 0, time_limit_s=60, write=False)
    assert rec["score"] == 65_500
    assert rec["lp_calls"] <= 500
    assert 0.0 <= rec["feasible_mass"] <= 1.0


def test_h2_fm_phys_budget_network12():
    from h2.run import main

    (rec,) = main(
        ["--instance", "network12", "--seed", "0", "--method", "h2_fm_phys", "--max-lp-calls",
         "300", "--no-write", "--epochs-init", "100", "--epochs-round", "20", "--sa-reads", "50"]
    )  # fmt: skip
    assert rec["lp_calls"] <= 300
    assert rec["score"] is not None
    assert rec["n_rounds"] >= 1


def test_learned_qubo_hook_default_unchanged():
    d = load_demand("network05")
    fm = FactorizationMachine(20, rank=4, seed=0)
    fm.fit(np.random.default_rng(0).integers(0, 2, (30, 20)), np.arange(30.0), epochs=5)
    kit = qt.build_network_qubo(d)[0]
    for beta in (0.0, 0.5):
        a_full, a_obj = learned_qubo(fm, d, 2.0, beta)
        b_full, b_obj = learned_qubo(fm, d, 2.0, beta, prior_bqm=kit)
        assert a_full == b_full and a_obj == b_obj
    c_full, _ = learned_qubo(fm, d, 2.0, 0.5, prior_bqm=physics_objective(d, 1.0, 0.5))
    assert c_full != a_full
