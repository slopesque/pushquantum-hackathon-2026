"""Tests de la boucle active H1 (``h1.loop.h1_fm``) et de la CLI ``h1.run``."""

from __future__ import annotations

import itertools
import sys
import types

import numpy as np
import pytest
from h0.harness import run_method

from h1.loop import h1_fm, quantum_round_selected
from h1.samplers import SampleBatch

FAST = {"epochs_init": 100, "epochs_round": 20, "sa_reads": 50}


def test_quantum_round_selected():
    assert not quantum_round_selected("none", 0)
    assert all(quantum_round_selected("all", r) for r in range(4))
    assert [quantum_round_selected("first:2", r) for r in range(4)] == [True, True, False, False]
    assert [quantum_round_selected("every:3", r) for r in range(5)] == [
        True, False, False, True, False,
    ]  # fmt: skip
    with pytest.raises(ValueError):
        quantum_round_selected("bogus:1", 0)


def test_network05_finds_optimum():
    rec = run_method(
        "h1", "h1_sa_fm", h1_fm, "network05", 0, params=FAST, time_limit_s=60, write=False
    )
    assert rec["score"] == 65_500
    assert rec["lp_calls"] <= rec["budget"]["lp_calls"] == 500
    assert rec["backend"] == "none" and rec["n_quantum_rounds"] == 0


def test_budget_never_exceeded_network12():
    from h1.run import main

    (rec,) = main(
        ["--instance", "network12", "--seed", "0", "--max-lp-calls", "300", "--no-write",
         "--epochs-init", "100", "--epochs-round", "20", "--sa-reads", "50"]
    )  # fmt: skip
    assert rec["lp_calls"] <= 300
    assert rec["score"] is not None
    assert rec["n_rounds"] >= 1
    assert rec["score_after_n0"] >= rec["score"]
    traj = rec["trajectory"]
    assert traj and traj[-1][1] == rec["score"]
    assert all(a[0] <= b[0] and a[1] > b[1] for a, b in itertools.pairwise(traj))


def test_fake_quantum_sampler_used_on_selected_rounds(monkeypatch):
    calls: list[int] = []

    def make_pce_sampler(**kwargs):
        assert kwargs == {"use_cloud": False, "population": 3}

        def sample(bqm, seed):
            calls.append(int(seed))
            rng = np.random.default_rng(seed)
            bits = rng.integers(0, 2, size=(30, bqm.num_variables), dtype=np.uint8)
            probs = np.full(30, 1 / 30)
            return SampleBatch(bits, probs, n_circuits=7, n_qubits=5, backend="maestro_local")

        return sample

    try:
        from h1 import pce

        monkeypatch.setattr(pce, "make_pce_sampler", make_pce_sampler)
    except ImportError:
        fake = types.ModuleType("h1.pce")
        fake.make_pce_sampler = make_pce_sampler  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "h1.pce", fake)

    seed = 1
    params = FAST | {"quantum": {"use_cloud": False, "population": 3}, "quantum_rounds": "every:2"}
    rec = run_method(
        "h1", "h1_pce_fm", h1_fm, "network12", seed, params=params, max_lp_calls=400, write=False
    )
    rounds = [s - seed * 1_000_003 for s in calls]
    assert rounds and all(r % 2 == 0 for r in rounds)
    assert rec["n_quantum_rounds"] == len(calls) == (rec["n_rounds"] + 1) // 2
    assert rec["n_circuits"] == 7 * len(calls)
    assert rec["max_qubits"] == 5
    assert rec["backend"] == "maestro_local"
    assert rec["lp_calls"] <= 400
    assert 0.0 <= rec["feasible_mass"] <= 1.0


def test_diagnostics_with_testset(monkeypatch, tmp_path):
    import json

    from h0.instances import load_demand

    from h1 import loop
    from hackathon.referee import qt

    demand = load_demand("network05")
    rng = np.random.default_rng(123)
    topos = [qt.random_topology(5, rng) for _ in range(30)]
    scores = [qt.route_min_congestion(demand, sorted(t)).objective for t in topos]
    path = tmp_path / "network05.json"
    path.write_text(json.dumps({"arcs": [[list(a) for a in t] for t in topos], "score": scores}))
    monkeypatch.setattr(loop, "TESTSET_DIR", tmp_path)
    params = FAST | {"diag_instance": "network05"}
    rec = run_method(
        "h1", "h1_sa_fm", h1_fm, "network05", 0, params=params, max_lp_calls=60, write=False
    )
    for key in ("spearman_rho", "spearman_rho_init", "spearman_rho_kit"):
        assert rec[key] is None or -1.0 <= rec[key] <= 1.0
    assert rec["spearman_rho_kit"] is not None and rec["spearman_rho_init"] is not None
