"""Tests H0 (rapides, network05)."""

from __future__ import annotations

import json

import numpy as np
import pytest

import hackathon.utils
from h0 import harness
from h0.baselines import b0_random, b1_sa_kit, b1_topologies
from h0.instances import load_demand
from h0.report import aggregate, markdown_table
from h0.scorer import BudgetExhausted, Scorer
from h0.testset import build_testset, load_testset
from hackathon.referee import qt

N5 = 5
SCHEMA_KEYS = {
    "hypothesis", "method", "instance", "seed", "params", "budget", "score", "best_known", "gap",
    "lp_calls", "wall_time_s", "n_circuits", "backend", "n_vars", "max_qubits", "feasible_mass",
    "score_raw", "score_after_ls", "spearman_rho", "top10_precision",
}  # fmt: skip


@pytest.fixture(scope="module")
def demand5() -> np.ndarray:
    return load_demand("network05")


@pytest.fixture(scope="module")
def b1_record() -> dict:
    return harness.run_method(
        "h0", "b1_sa_kit", b1_sa_kit, "network05", 0, time_limit_s=60.0, write=False
    )


def test_scorer_matches_referee_and_cache(demand5):
    rng = np.random.default_rng(0)
    scorer = Scorer(demand5)
    topos = []
    while len(topos) < 3:
        t = qt.random_topology(N5, rng)
        if frozenset(t) not in {frozenset(x) for x in topos}:
            topos.append(t)
    for t in topos:
        assert scorer.score(t) == qt.route_min_congestion(demand5, t).objective
    assert scorer.lp_calls == 3
    scorer.score(list(reversed(topos[0])))
    assert scorer.lp_calls == 3


def test_budget_exhausted(demand5):
    scorer = Scorer(demand5, max_lp_calls=2)
    rng = np.random.default_rng(1)
    with pytest.raises(BudgetExhausted):
        for _ in range(1000):
            scorer.score(qt.random_topology(N5, rng))
    assert scorer.lp_calls == 2


def test_b1_finds_optimum_network05(b1_record):
    assert b1_record["score"] == 65_500
    assert b1_record["gap"] == 0.0
    assert 0.0 <= b1_record["feasible_mass"] <= 1.0
    assert b1_record["params"]["n_batches"] >= 1


def test_b0_runs_network05():
    rec = harness.run_method("h0", "b0_random", b0_random, "network05", 0, write=False)
    assert rec["score"] is not None and rec["lp_calls"] <= 500
    assert "stalled" in rec["params"]


def test_record_schema(b1_record):
    assert SCHEMA_KEYS <= set(b1_record)
    assert b1_record["n_vars"] == 20 and b1_record["max_qubits"] == 0
    assert b1_record["backend"] == "none"
    json.dumps(b1_record)


def test_save_solution(b1_record, monkeypatch, tmp_path):
    monkeypatch.setattr(hackathon.utils, "RESULTS_DIR", tmp_path)
    path = harness.save_solution(b1_record)
    assert path.parent == tmp_path / "network" and path.name.endswith("network05.sol")
    valid, max_flow, _ = qt.check_network_solution(path, N5, load_demand("network05"))
    assert valid and max_flow == 65_500
    meta = json.loads(path.with_suffix(".json").read_text())
    assert meta["score"] == 65_500 and "best_arcs" not in meta


def test_b1_topologies_distinct_valid(demand5):
    topos = b1_topologies(demand5, 0, 10)
    assert 1 <= len(topos) <= 10
    assert len({frozenset(t) for t in topos}) == len(topos)
    assert all(qt.is_valid_topology(N5, t) for t in topos)


def test_testset_roundtrip(tmp_path):
    path = build_testset("network05", seed=12345, n_random=5, n_b1=3, out_dir=tmp_path)
    assert path == tmp_path / "network05.json"
    topos, scores = load_testset("network05", out_dir=tmp_path)
    assert len(topos) == len(scores) == 8
    assert len({frozenset(t) for t in topos}) == 8
    demand = load_demand("network05")
    for t, s in zip(topos[:2], scores[:2]):
        assert s == qt.route_min_congestion(demand, t).objective


def _fake(seed: int, score: int, method: str = "b0_random") -> dict:
    return {
        "instance": "network05", "method": method, "seed": seed, "score": score,
        "best_known": 65_500, "lp_calls": 100 * (seed + 1), "wall_time_s": 1.0 + seed,
        "max_qubits": 0, "backend": "none",
    }  # fmt: skip


def test_report_aggregate():
    recs = [_fake(0, 99_999), _fake(0, 70_000), _fake(1, 65_500), _fake(2, 80_000)]
    agg = aggregate(recs)[("network05", "b0_random")]
    assert agg["seeds"] == [0, 1, 2]
    assert (agg["min"], agg["median"], agg["max"]) == (65_500, 70_000, 80_000)
    assert agg["gap_min"] == 0.0
    assert agg["gap_median"] == pytest.approx(4_500 / 65_500)
    assert agg["lp_calls"] == 200 and agg["wall_time_s"] == 2.0
    assert agg["best_record"]["seed"] == 1
    table = markdown_table(aggregate(recs))
    assert "| network05 | b0_random |" in table and "+6.87 %" in table
